"""TTS engine registry."""

from __future__ import annotations

from typing import Dict, List, Type

from .base import TTSEngine


_REGISTRY: Dict[str, Type[TTSEngine]] = {}


def register(cls: Type[TTSEngine]) -> Type[TTSEngine]:
    _REGISTRY[cls.id] = cls
    return cls


def get_engine(engine_id: str, cfg) -> TTSEngine:
    if engine_id not in _REGISTRY:
        raise KeyError(f"Unknown TTS engine '{engine_id}'. Known: {list(_REGISTRY)}")
    return _REGISTRY[engine_id](cfg)


def list_engines() -> List[Dict[str, str]]:
    return [
        {
            "id": cls.id,
            "display_name": cls.display_name,
            "supports_voice_clone": cls.supports_voice_clone,
            "requires_network": cls.requires_network,
        }
        for cls in _REGISTRY.values()
    ]


# Trigger @register on import of every engine module.
from . import k2_omnivoice  # noqa: E402,F401
from . import qwen3_tts  # noqa: E402,F401
from . import coqui_xtts  # noqa: E402,F401
from . import edge_tts  # noqa: E402,F401
from . import openai_tts  # noqa: E402,F401
from . import elevenlabs_tts  # noqa: E402,F401
from . import sarvam_tts  # noqa: E402,F401
from . import indic_parler_tts  # noqa: E402,F401
