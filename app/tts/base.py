"""Base interface for TTS engine adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class TTSEngine(ABC):
    """Synthesise speech. `text` is already in the target language."""

    id: str = "base"
    display_name: str = "Base"
    supports_voice_clone: bool = False
    requires_network: bool = False

    @abstractmethod
    def synth(
        self,
        text: str,
        language: str,
        reference_audio: str | None,
        out_path: str,
    ) -> str:
        """Write wav/mp3 to out_path, return the path."""
        ...

    @abstractmethod
    def supported_languages(self) -> List[str]:
        ...

    def close(self) -> None:
        return None
