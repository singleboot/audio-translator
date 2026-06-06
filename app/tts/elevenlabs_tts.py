"""ElevenLabs TTS — paid, online, instant voice clone.

Install: pip install elevenlabs
"""

from __future__ import annotations

import os
from typing import List, Optional

from .base import TTSEngine
from . import register


@register
class ElevenLabsTTSEngine(TTSEngine):
    id = "elevenlabs"
    display_name = "ElevenLabs (paid, instant clone)"
    supports_voice_clone = True
    requires_network = True

    def __init__(self, cfg) -> None:
        c = cfg.get("tts.elevenlabs", {}) or {}
        self.api_key: str = c.get("api_key", "")
        self.model_id: str = c.get("model_id", "eleven_multilingual_v2")
        self.voice_id: str = c.get("voice_id", "")
        self._client = None
        self._cloned_voice_id: Optional[str] = None
        self._cloned_for: Optional[str] = None  # source audio path

    def _ensure(self):
        if self._client is not None or not self.api_key:
            return
        from elevenlabs import ElevenLabs  # type: ignore
        self._client = ElevenLabs(api_key=self.api_key)

    def supported_languages(self) -> List[str]:
        return [
            "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko",
            "ar", "hi", "tr", "nl", "pl", "cs", "hu", "sv", "fi", "da",
            "no", "el", "he", "id", "ms", "vi", "th", "uk", "ro", "bg",
            "sk", "hr", "fil", "ta", "bn", "ml", "kn",
        ]

    def _ensure_cloned_voice(self, reference_audio: str) -> str:
        """Clone the reference once per process; reuse for every language."""
        if not reference_audio or not os.path.exists(reference_audio):
            return self.voice_id  # may be empty -> user must set one in config
        if self._cloned_voice_id and self._cloned_for == reference_audio:
            return self._cloned_voice_id
        voice = self._client.voices.ivc.create(
            name=f"auto_clone_{os.path.basename(reference_audio)}",
            files=[reference_audio],
        )
        self._cloned_voice_id = voice.voice_id
        self._cloned_for = reference_audio
        return self._cloned_voice_id

    def synth(self, text: str, language: str, reference_audio, out_path: str) -> str:
        if not self.api_key:
            raise RuntimeError("ElevenLabs API key not set (tts.elevenlabs.api_key)")
        if not text.strip():
            raise ValueError("empty text")
        self._ensure()
        vid = self.voice_id or self._ensure_cloned_voice(reference_audio)
        if not vid:
            raise RuntimeError("ElevenLabs: no voice_id and no reference audio to clone from")
        audio = self._client.text_to_speech.convert(
            text=text,
            voice_id=vid,
            model_id=self.model_id,
            output_format="mp3_44100_128",
        )
        # audio is an iterator of bytes; concatenate to file.
        with open(out_path, "wb") as f:
            for chunk in audio:
                if isinstance(chunk, bytes):
                    f.write(chunk)
        return out_path
