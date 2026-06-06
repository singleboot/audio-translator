"""Pipeline orchestrator: per-file ASR -> translate -> TTS (parallel) -> save."""

from __future__ import annotations

import concurrent.futures as cf
import os
import time
import traceback
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from .asr import get_asr
from .config import get_config
from .db import get_db
from .translators import get_translator
from .tts import get_engine


SUPPORTED_LANGS_ALL = sorted({
    "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko",
    "ar", "hi", "tr", "nl", "pl", "cs", "hu", "sv", "fi", "da",
    "no", "el", "he", "id", "ms", "vi", "th", "uk", "ro", "bg",
    "sk", "hr", "ta", "te", "ml", "bn", "mr", "gu", "kn", "or", "pa",
    "hi-IN", "en-IN", "as", "brx", "doi", "kok", "mai", "mni", "ne",
    "sa", "sat", "sd", "ur",
})


def _wav_duration_s(path: str) -> Optional[float]:
    try:
        import wave
        with wave.open(path, "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            if rate:
                return frames / float(rate)
    except Exception:
        pass
    return None


def _trim_reference_for_clone(audio_path: str, max_seconds: int) -> tuple[str, bool]:
    """Return (path, created_temp). Try to trim to <= max_seconds for cleaner cloning."""
    if max_seconds <= 0:
        return audio_path, False
    try:
        from pydub import AudioSegment  # type: ignore
        seg = AudioSegment.from_file(audio_path)
        if seg.duration_seconds <= max_seconds:
            return audio_path, False
        out = audio_path + ".refclip.wav"
        seg[: max_seconds * 1000].export(out, format="wav")
        return out, True
    except Exception:
        # If pydub/ffmpeg isn't available, just return the original.
        return audio_path, False


class Pipeline:
    """Stateless orchestrator. Holds nothing between jobs except lazy adapters."""

    def __init__(self) -> None:
        self.cfg = get_config()
        self.db = get_db()
        self._asr = None
        self._translator = None
        self._translator_id: Optional[str] = None
        self._tts_cache: Dict[str, object] = {}

    # ---- lazy adapters ------------------------------------------------
    def asr(self):
        if self._asr is None:
            asr_id = self.cfg.get("asr.engine", "whisper")
            self._asr = get_asr(asr_id, self.cfg)
        return self._asr

    def translator(self):
        tid = self.cfg.get("translator.default", "nllb_local")
        if self._translator is None or self._translator_id != tid:
            self._translator = get_translator(tid, self.cfg)
            self._translator_id = tid
        return self._translator

    def tts(self, engine_id: str):
        if engine_id not in self._tts_cache:
            self._tts_cache[engine_id] = get_engine(engine_id, self.cfg)
        return self._tts_cache[engine_id]

    # ---- main entry ---------------------------------------------------
    def process_file(self, source_path: str) -> str:
        """Process a single audio file end-to-end. Returns the job_uuid."""
        cfg = self.cfg
        out_dir = Path(cfg.get("paths.output_folder", "./outputs"))
        out_dir.mkdir(parents=True, exist_ok=True)

        source_path = os.path.abspath(source_path)
        stem = Path(source_path).stem
        job_uuid = uuid.uuid4().hex
        self.db.create_job(job_uuid, source_path, stem)

        engines: List[str] = list(cfg.get("tts.enabled", []))
        languages: List[str] = list(cfg.get("languages", []))
        self.db.update_job(
            job_uuid, status="asr", engines=engines, languages=languages
        )

        # Notify any open websocket clients.
        try:
            from .ws import broadcast
            broadcast({"type": "job_update", "job": self.db.get_job(job_uuid)})
        except Exception:
            pass

        try:
            # 1) ASR
            asr_result = self.asr().transcribe(source_path)
            self.db.update_job(
                job_uuid,
                status="translating",
                src_lang=asr_result.language,
                transcript=asr_result.text,
            )
            try:
                from .ws import broadcast
                broadcast({"type": "job_update", "job": self.db.get_job(job_uuid)})
            except Exception:
                pass

            # 2) Translate to each target language.
            translations: Dict[str, str] = {}
            tr = self.translator()
            for tgt in languages:
                if tgt == asr_result.language:
                    translations[tgt] = asr_result.text
                    continue
                try:
                    translations[tgt] = tr.translate(asr_result.text, asr_result.language, tgt)
                except Exception as e:
                    translations[tgt] = ""
                    print(f"[pipeline] translate -> {tgt} failed: {e}")
            self.db.update_job(job_uuid, status="synthesizing", translations=translations)

            # 3) TTS — for every (engine, language) pair in parallel.
            ref_clip, ref_was_temp = _trim_reference_for_clone(
                source_path, int(cfg.get("pipeline.reference_clip_seconds", 25))
            )

            tasks = []
            for eng_id in engines:
                eng = self.tts(eng_id)
                supported = set(eng.supported_languages())
                for tgt in languages:
                    if tgt not in supported:
                        continue
                    text = translations.get(tgt, "")
                    if not text:
                        continue
                    out_path = out_dir / f"{stem}_{eng_id}_{tgt}.wav"
                    tasks.append((eng_id, tgt, eng, text, out_path))

            max_par = max(1, int(cfg.get("pipeline.max_parallel_tts", 2)))
            continue_on_error = bool(cfg.get("pipeline.continue_on_error", True))
            results: List[tuple] = []

            def _one(t):
                eng_id, tgt, eng, text, out_path = t
                t0 = time.time()
                try:
                    p = eng.synth(text, tgt, ref_clip, str(out_path))
                    dur = _wav_duration_s(p)
                    self.db.add_artifact(job_uuid, eng_id, tgt, p, dur)
                    return (eng_id, tgt, "ok", time.time() - t0, None)
                except Exception as e:
                    tb = traceback.format_exc(limit=2)
                    return (eng_id, tgt, "error", time.time() - t0, f"{e}\n{tb}")

            with cf.ThreadPoolExecutor(max_workers=max_par) as pool:
                for r in pool.map(_one, tasks):
                    results.append(r)
                    if not continue_on_error and r[2] == "error":
                        break
                    # push live update per artifact
                    try:
                        from .ws import broadcast
                        broadcast({"type": "job_update", "job": self.db.get_job(job_uuid)})
                    except Exception:
                        pass

            # 4) Clean up trimmed reference.
            if ref_was_temp:
                try: os.unlink(ref_clip)
                except Exception: pass

            had_error = any(r[2] == "error" for r in results)
            self.db.update_job(
                job_uuid,
                status="error" if had_error and not results else "done",
                error=None if not had_error else "One or more engine/language combinations failed (see server log).",
            )
            try:
                from .ws import broadcast
                broadcast({"type": "job_update", "job": self.db.get_job(job_uuid)})
            except Exception:
                pass
            return job_uuid

        except Exception as e:
            tb = traceback.format_exc()
            self.db.update_job(job_uuid, status="error", error=f"{e}\n{tb}")
            try:
                from .ws import broadcast
                broadcast({"type": "job_update", "job": self.db.get_job(job_uuid)})
            except Exception:
                pass
            raise


_pipeline_singleton: Optional[Pipeline] = None


def get_pipeline() -> Pipeline:
    global _pipeline_singleton
    if _pipeline_singleton is None:
        _pipeline_singleton = Pipeline()
    return _pipeline_singleton
