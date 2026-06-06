"""Coqui XTTSv2 — local, 17 languages, voice clone, mature.

Install: pip install TTS
First run downloads the XTTS-v2 model (~2GB).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import List

from .base import TTSEngine
from . import register


# Coqui XTTS supports these short codes.
XTTS_LANGS = [
    "en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl",
    "cs", "ar", "zh", "ja", "hu", "ko", "hi",
]


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _trim_reference(audio_path: str, max_seconds: int) -> str:
    """Cut the reference clip to <= max_seconds so the clone is clean."""
    try:
        from pydub import AudioSegment  # type: ignore
    except Exception:
        return audio_path
    try:
        seg = AudioSegment.from_file(audio_path)
        if seg.duration_seconds <= max_seconds:
            return audio_path
        out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        out.close()
        seg[: max_seconds * 1000].export(out.name, format="wav")
        return out.name
    except Exception:
        return audio_path


@register
class CoquiXTTSEngine(TTSEngine):
    id = "coqui_xtts"
    display_name = "Coqui XTTSv2 (local, 17 langs, clone)"
    supports_voice_clone = True
    requires_network = False

    def __init__(self, cfg) -> None:
        device = cfg.get("tts.coqui_xtts.device", "auto")
        self.device = _resolve_device(device)
        self._tts = None

    def _ensure_loaded(self):
        if self._tts is not None:
            return
        from TTS.api import TTS as CoquiTTS  # type: ignore
        self._tts = CoquiTTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)

    def supported_languages(self) -> List[str]:
        return list(XTTS_LANGS)

    def synth(self, text: str, language: str, reference_audio, out_path: str) -> str:
        if not text.strip():
            raise ValueError("empty text")
        if language not in XTTS_LANGS:
            raise ValueError(f"XTTS does not support language '{language}'. Supported: {XTTS_LANGS}")
        if not reference_audio or not os.path.exists(reference_audio):
            raise RuntimeError("XTTS requires a reference audio file for voice cloning")
        self._ensure_loaded()
        ref = _trim_reference(reference_audio, max_seconds=25)
        try:
            self._tts.tts_to_file(
                text=text,
                file_path=out_path,
                speaker_wav=ref,
                language=language,
            )
        finally:
            if ref != reference_audio:
                try: os.unlink(ref)
                except Exception: pass
        return out_path
