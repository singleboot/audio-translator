"""Configuration loader for Audio Translator v1."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG: Dict[str, Any] = {
    "server": {"host": "127.0.0.1", "port": 8000},
    "paths": {
        "watch_folder": "./watch",
        "output_folder": "./outputs",
        "db_path": "./jobs.db",
    },
    "asr": {
        "engine": "whisper",
        "whisper": {
            "model_size": "large-v3-turbo",
            "device": "auto",
            "compute_type": "auto",
            "language": "auto",
        },
    },
    "translator": {
        "default": "nllb_local",
        "nllb_local": {
            "model": "facebook/nllb-200-distilled-600M",
            "device": "auto",
        },
        "gemini_free": {"api_key": "", "model": "gemini-1.5-flash"},
        "openai": {
            "api_key": "",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
        },
        "custom_http": {
            "url": "",
            "method": "POST",
            "headers": {},
            "body_template": '{"text": "{text}", "source": "{src}", "target": "{tgt}"}',
            "response_text_path": "translation",
        },
    },
    "tts": {
        "enabled": [
            "qwen3_tts",
            "k2_omnivoice",
            "coqui_xtts",
            "edge_tts",
            "openai_tts",
            "elevenlabs",
            "sarvam_ai",
            "indic_parler_tts",
        ],
        "cache_dir": "./models",
        "k2_omnivoice": {"device": "auto"},
        "qwen3_tts": {"size": "1.7B", "device": "auto"},
        "coqui_xtts": {"device": "auto"},
        "edge_tts": {"voice_overrides": {}},
        "openai_tts": {
            "api_key": "",
            "model": "gpt-4o-mini-tts",
            "voice": "alloy",
            "base_url": "https://api.openai.com/v1",
        },
        "elevenlabs": {
            "api_key": "",
            "model_id": "eleven_multilingual_v2",
            "voice_id": "",
        },
        "sarvam_ai": {
            "api_key": "",
            "api_url": "https://api.sarvam.ai/v1/text-to-speech",
        },
        "indic_parler_tts": {
            "device": "auto",
            "speaker": "",
            "description": "",
            "emotion": "",
        },
    },
    "languages": [
        "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko",
        "ar", "hi", "tr", "nl", "pl", "cs", "hu", "sv", "fi", "da",
        "no", "el", "he", "id", "ms", "vi", "th", "uk", "ro", "bg",
        "sk", "hr",
    ],
    "watcher": {
        "auto_start": False,
        "settle_seconds": 2,
        "extensions": [".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"],
    },
    "pipeline": {
        "max_parallel_tts": 2,
        "reference_clip_seconds": 25,
        "continue_on_error": True,
    },
}


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge overlay into base; overlay wins on scalar conflicts."""
    out = copy.deepcopy(base)
    for k, v in overlay.items():
        if (
            k in out
            and isinstance(out[k], dict)
            and isinstance(v, dict)
        ):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class Config:
    """Holds the merged, in-memory config. Mutable so the UI can toggle things."""

    def __init__(self, path: str = "config.yaml") -> None:
        self.path = path
        self._data: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        if not isinstance(user, dict):
            raise ValueError(f"{self.path} must contain a YAML mapping at the top level")
        self._data = _deep_merge(self._data, user)

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._data, f, sort_keys=False, allow_unicode=True)

    # Convenience accessors ---------------------------------------------
    def raw(self) -> Dict[str, Any]:
        return self._data

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in dotted.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def ensure_paths(self) -> None:
        for key in ("watch_folder", "output_folder"):
            rel = self.get(f"paths.{key}")
            if rel:
                Path(rel).mkdir(parents=True, exist_ok=True)


# Module-level singleton (lazy).
_singleton: Config | None = None


def get_config(path: str = "config.yaml") -> Config:
    global _singleton
    if _singleton is None:
        _singleton = Config(path)
    return _singleton
