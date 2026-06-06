"""Sarvam.ai TTS — cloud API, Indian languages, voice cloning.

Install: pip install requests
Get API key at https://dashboard.sarvam.ai
Docs: https://api.sarvam.ai
"""

from __future__ import annotations

import json
import os
import time
from typing import List

from .base import TTSEngine
from . import register


SARVAM_LANGUAGES = [
    "hi", "hi-IN", "ta", "te", "ml", "bn", "mr", "gu", "kn", "or", "pa", "en-IN",
]


@register
class SarvamTTSEngine(TTSEngine):
    id = "sarvam_ai"
    display_name = "Sarvam.ai (cloud, Indian langs, clone)"
    supports_voice_clone = True
    requires_network = True

    def __init__(self, cfg) -> None:
        c = cfg.get("tts.sarvam_ai", {}) or {}
        self.api_key: str = c.get("api_key", "")
        self.api_url: str = c.get("api_url", "https://api.sarvam.ai/v1/text-to-speech")

    def supported_languages(self) -> List[str]:
        return list(SARVAM_LANGUAGES)

    def synth(self, text: str, language: str, reference_audio, out_path: str) -> str:
        if not self.api_key:
            raise RuntimeError("Sarvam.ai API key not set (tts.sarvam_ai.api_key)")
        if not text.strip():
            raise ValueError("empty text")
        import requests  # type: ignore

        headers = {"api-subscription-key": self.api_key}
        data = {
            "input": text,
            "target_language_code": language,
            "speaker": "default",
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.0,
            "sample_rate": 24000,
        }
        if reference_audio and os.path.exists(reference_audio):
            data["enable_voice_cloning"] = True
            with open(reference_audio, "rb") as f:
                import base64
                data["reference_audio"] = base64.b64encode(f.read()).decode("utf-8")

        resp = requests.post(self.api_url, headers=headers, json=data, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"Sarvam API error {resp.status_code}: {resp.text[:200]}")

        result = resp.json()
        audio_b64 = result.get("audio_content") or result.get("audio")
        if not audio_b64:
            raise RuntimeError(f"Sarvam: no audio in response: {json.dumps(result)[:200]}")

        import base64
        raw = base64.b64decode(audio_b64)
        with open(out_path, "wb") as f:
            f.write(raw)
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise RuntimeError("Sarvam produced no audio")
        return out_path