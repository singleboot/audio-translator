"""Base interface for translator adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class Translator(ABC):
    """Translate `text` from `src_lang` to `tgt_lang`. Return the translated string."""

    id: str = "base"
    display_name: str = "Base"

    @abstractmethod
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        ...

    def supported_languages(self) -> List[str] | None:
        """Return None = 'any language' (e.g. an LLM)."""
        return None

    def close(self) -> None:
        return None
