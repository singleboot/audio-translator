"""k2-fsa OmniVoice — local, 600+ languages, voice clone + voice design.

Install: pip install omnivoice   (see https://github.com/k2-fsa/OmniVoice)
First run downloads the OmniVoice model weights.

The exact Python API of this library is still evolving; this adapter
uses the most common entry points and falls back gracefully.
"""

from __future__ import annotations

import os
import wave
from typing import List

from .base import TTSEngine
from . import register


# OmniVoice advertises 600+ languages. We expose a sensible default set;
# users can extend by adding codes in the UI.
DEFAULT_LANGS = [
    "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko",
    "ar", "hi", "tr", "nl", "pl", "cs", "hu", "sv", "fi", "da",
    "no", "el", "he", "id", "ms", "vi", "th", "uk", "ro", "bg",
    "sk", "hr", "fa", "bn", "ta", "ur", "sw", "sr", "sl", "lt",
    "lv", "et", "is", "mk", "af", "az", "ka", "hy", "kk", "uz",
]


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


@register
class K2OmniVoiceEngine(TTSEngine):
    id = "k2_omnivoice"
    display_name = "k2-fsa OmniVoice (local, 600+ langs, clone)"
    supports_voice_clone = True
    requires_network = False

    def __init__(self, cfg) -> None:
        device = cfg.get("tts.k2_omnivoice.device", "auto")
        self.device = _resolve_device(device)
        self._model = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        # Try the most common import paths; the library is young.
        try:
            from omnivoice import OmniVoiceModel  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "k2-fsa OmniVoice not installed. pip install omnivoice — "
                f"underlying error: {e}"
            )
        self._model = OmniVoiceModel.from_pretrained(
            "k2-fsa/OmniVoice", device=self.device
        )

    def supported_languages(self) -> List[str]:
        return list(DEFAULT_LANGS)

    def synth(self, text: str, language: str, reference_audio, out_path: str) -> str:
        if not text.strip():
            raise ValueError("empty text")
        self._ensure_loaded()
        kwargs = dict(text=text, language=language, output_path=out_path)
        if reference_audio and os.path.exists(reference_audio):
            kwargs["reference_audio"] = reference_audio
        try:
            self._model.synthesize(**kwargs)
        except TypeError:
            # Older API
            self._model(text=text, language=language, ref_audio=reference_audio, out=out_path)
        if not os.path.exists(out_path):
            raise RuntimeError("OmniVoice did not produce an output file")
        return out_path
