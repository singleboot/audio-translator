"""Microsoft Edge TTS — free, online, no clone. Good fallback.

Install: pip install edge-tts
Uses the public edge-tts Azure endpoint; no API key needed.
"""

from __future__ import annotations

import os
from typing import List

from .base import TTSEngine
from . import register


# Short code -> default Edge voice.
EDGE_VOICE_DEFAULTS = {
    "en": "en-US-GuyNeural",      "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",   "de": "de-DE-KatjaNeural",
    "it": "it-IT-ElsaNeural",     "pt": "pt-BR-FranciscaNeural",
    "ru": "ru-RU-SvetlanaNeural", "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",   "ko": "ko-KR-SunHiNeural",
    "ar": "ar-EG-SalmaNeural",    "hi": "hi-IN-SwaraNeural",
    "tr": "tr-TR-EmelNeural",     "nl": "nl-NL-ColetteNeural",
    "pl": "pl-PL-ZofiaNeural",    "cs": "cs-CZ-VlastaNeural",
    "hu": "hu-HU-NoemiNeural",    "sv": "sv-SE-SofieNeural",
    "fi": "fi-FI-NooraNeural",    "da": "da-DK-ChristelNeural",
    "no": "nb-NO-IselinNeural",   "el": "el-GR-AthinaNeural",
    "he": "he-IL-HilaNeural",     "id": "id-ID-GadisNeural",
    "ms": "ms-MY-YasminNeural",   "vi": "vi-VN-HoaiMyNeural",
    "th": "th-TH-PremwadeeNeural","uk": "uk-UA-PolinaNeural",
    "ro": "ro-RO-AlinaNeural",    "bg": "bg-BG-KalinaNeural",
    "sk": "sk-SK-ViktoriaNeural", "hr": "hr-HR-GabrijelaNeural",
}


def _run_edge_tts_sync(text: str, voice: str, out_path: str) -> None:
    """Use the edge-tts Python library directly (async-to-sync wrapper)."""
    import edge_tts  # type: ignore
    async def _go():
        communicate = edge_tts.Communicate(text, voice)
        # accumulate all audio chunks
        buf = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf += chunk["data"]
        return buf
    import asyncio
    buf = asyncio.run(_go())
    with open(out_path, "wb") as f:
        f.write(buf)


@register
class EdgeTTSEngine(TTSEngine):
    id = "edge_tts"
    display_name = "Edge TTS (free, no clone)"
    supports_voice_clone = False
    requires_network = True

    def __init__(self, cfg) -> None:
        self.voice_overrides: dict = cfg.get("tts.edge_tts.voice_overrides", {}) or {}

    def supported_languages(self) -> List[str]:
        return list(EDGE_VOICE_DEFAULTS.keys())

    def synth(self, text: str, language: str, reference_audio, out_path: str) -> str:
        if not text.strip():
            raise ValueError("empty text")
        voice = self.voice_overrides.get(language) or EDGE_VOICE_DEFAULTS.get(language)
        if not voice:
            # best-effort fallback to English
            voice = EDGE_VOICE_DEFAULTS["en"]
        _run_edge_tts_sync(text, voice, out_path)
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise RuntimeError("edge-tts produced no audio")
        return out_path
