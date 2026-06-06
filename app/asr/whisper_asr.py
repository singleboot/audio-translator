"""Local Whisper ASR via faster-whisper.

Install:  pip install faster-whisper
The first run downloads the chosen model size into the HuggingFace cache.
"""

from __future__ import annotations

import os
from typing import Optional

from . import ASR, ASRResult, register


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch  # noqa: WPS433
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


@register
class WhisperASR(ASR):
    id = "whisper"

    def __init__(self, cfg) -> None:
        wcfg = cfg.get("asr.whisper", {}) or {}
        self.model_size: str = wcfg.get("model_size", "large-v3-turbo")
        self.device: str = _resolve_device(wcfg.get("device", "auto"))
        preferred_ct = wcfg.get("compute_type", "auto")
        if preferred_ct == "auto":
            self.compute_type = "float16" if self.device == "cuda" else "int8"
        else:
            self.compute_type = preferred_ct
        self.language: Optional[str] = wcfg.get("language", "auto")
        self._model = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        from faster_whisper import WhisperModel  # type: ignore
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

    def transcribe(self, audio_path: str) -> ASRResult:
        self._ensure_loaded()
        lang = None if self.language in (None, "", "auto") else self.language
        segments_iter, info = self._model.transcribe(
            audio_path,
            language=lang,
            vad_filter=True,
        )
        segments = []
        text_parts = []
        for seg in segments_iter:
            segments.append(
                {
                    "start": float(seg.start),
                    "end": float(seg.end),
                    "text": seg.text,
                }
            )
            text_parts.append(seg.text)
        return ASRResult(
            text="".join(text_parts).strip(),
            language=info.language or (lang or "unknown"),
            segments=segments,
        )
