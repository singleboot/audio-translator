"""ASR registry. Currently Whisper-only, but the interface lets us add more."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Type


@dataclass
class ASRResult:
    text: str
    language: str
    segments: List[Dict]


class ASR(ABC):
    id: str = "base"

    @abstractmethod
    def transcribe(self, audio_path: str) -> ASRResult:
        ...

    def close(self) -> None:
        return None


_REGISTRY: Dict[str, Type[ASR]] = {}


def register(cls: Type[ASR]) -> Type[ASR]:
    _REGISTRY[cls.id] = cls
    return cls


def get_asr(asr_id: str, cfg) -> ASR:
    if asr_id not in _REGISTRY:
        raise KeyError(f"Unknown ASR '{asr_id}'. Known: {list(_REGISTRY)}")
    return _REGISTRY[asr_id](cfg)


def list_asr() -> List[Dict[str, str]]:
    return [{"id": c.id} for c in _REGISTRY.values()]


from . import whisper_asr  # noqa: E402,F401
