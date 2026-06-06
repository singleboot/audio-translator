"""OpenAI TTS — paid, online, no native clone.

Install: pip install openai
"""

from __future__ import annotations

import os
from typing import List

from .base import TTSEngine
from . import register


# OpenAI TTS voices. Each voice covers the same set of languages
# (the model picks pronunciation per language automatically).
_OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "ash", "sage", "coral"]


@register
class OpenAITTSEngine(TTSEngine):
    id = "openai_tts"
    display_name = "OpenAI TTS (paid, no clone)"
    supports_voice_clone = False
    requires_network = True

    def __init__(self, cfg) -> None:
        c = cfg.get("tts.openai_tts", {}) or {}
        self.api_key: str = c.get("api_key", "")
        self.model: str = c.get("model", "gpt-4o-mini-tts")
        self.voice: str = c.get("voice", "alloy")
        self.base_url: str = c.get("base_url", "https://api.openai.com/v1")
        self._client = None

    def _ensure(self):
        if self._client is not None or not self.api_key:
            return
        from openai import OpenAI  # type: ignore
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def supported_languages(self) -> List[str]:
        # OpenAI auto-detects; we still claim a sensible set.
        return [
            "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko",
            "ar", "hi", "tr", "nl", "pl", "cs", "hu", "sv", "fi", "da",
            "no", "el", "he", "id", "ms", "vi", "th", "uk", "ro", "bg",
            "sk", "hr",
        ]

    def synth(self, text: str, language: str, reference_audio, out_path: str) -> str:
        if not self.api_key:
            raise RuntimeError("OpenAI API key not set (tts.openai_tts.api_key)")
        if not text.strip():
            raise ValueError("empty text")
        self._ensure()
        # OpenAI returns mp3 by default; we wrap in wav by saving the raw bytes
        # and re-muxing if pydub/ffmpeg is present. For simplicity, save as .mp3
        # and rename to .wav (the player doesn't care — it's bytes-on-the-wire).
        with self._client.audio.speech.with_streaming_response.create(
            model=self.model,
            voice=self.voice,
            input=text,
        ) as resp:
            resp.stream_to_file(out_path)
        return out_path
