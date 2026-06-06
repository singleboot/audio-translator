"""Qwen3-TTS — local, 10 languages, best free clone quality.

Install: pip install qwen-tts
First run downloads the Qwen3-TTS model weights.

Supports two model sizes: 0.6B and 1.7B. Both have 9 preset voices
plus voice-clone and voice-design modes.
"""

from __future__ import annotations

import os
from typing import List

from .base import TTSEngine
from . import register


# 10 official Qwen3-TTS languages.
QWEN3_LANGS = ["en", "zh", "ja", "ko", "de", "fr", "ru", "es", "it", "pt"]


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


@register
class Qwen3TTSEngine(TTSEngine):
    id = "qwen3_tts"
    display_name = "Qwen3-TTS (local, 10 langs, best clone)"
    supports_voice_clone = True
    requires_network = False

    def __init__(self, cfg) -> None:
        c = cfg.get("tts.qwen3_tts", {}) or {}
        size = c.get("size", "1.7B")
        device = c.get("device", "auto")
        self.size = size
        self.device = _resolve_device(device)
        self._model = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        # The official PyPI package is `qwen-tts`; model id is the size we want.
        from qwen_tts import Qwen3TTSModel  # type: ignore
        model_id = f"Qwen/Qwen3-TTS-12Hz-{self.size}-CustomVoice"
        # CustomVoice supports both preset voices and voice cloning via
        # voice clone prompts. The Base model variant is needed for clone.
        if self.size.endswith("B") and self._clone_only():
            model_id = f"Qwen/Qwen3-TTS-12Hz-{self.size}-Base"
        self._model = Qwen3TTSModel.from_pretrained(model_id, device_map=self.device)

    def _clone_only(self) -> bool:
        # We always want clone support; the Base variant is the right tool.
        return True

    def supported_languages(self) -> List[str]:
        return list(QWEN3_LANGS)

    def synth(self, text: str, language: str, reference_audio, out_path: str) -> str:
        if not text.strip():
            raise ValueError("empty text")
        if language not in QWEN3_LANGS:
            raise ValueError(f"Qwen3-TTS does not support language '{language}'. Supported: {QWEN3_LANGS}")
        self._ensure_loaded()
        kwargs = dict(text=text, language=language, output_path=out_path)
        if reference_audio and os.path.exists(reference_audio):
            # Reference audio for voice clone. The exact API may differ across
            # qwen-tts versions; we pass a VoiceClonePromptItem when possible.
            try:
                from qwen_tts import VoiceClonePromptItem  # type: ignore
                kwargs["voice_clone_prompt"] = [VoiceClonePromptItem(
                    ref_audio=reference_audio,
                    ref_text=None,  # let the model handle it
                )]
            except Exception:
                kwargs["ref_audio"] = reference_audio
        self._model.generate(**kwargs)
        return out_path
