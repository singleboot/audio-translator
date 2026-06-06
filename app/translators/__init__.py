"""Translator registry: a single function that builds any registered adapter."""

from __future__ import annotations

from typing import Dict, List, Type

from .base import Translator


_REGISTRY: Dict[str, Type[Translator]] = {}


def register(cls: Type[Translator]) -> Type[Translator]:
    _REGISTRY[cls.id] = cls
    return cls


def get_translator(translator_id: str, cfg) -> Translator:
    if translator_id not in _REGISTRY:
        raise KeyError(f"Unknown translator '{translator_id}'. Known: {list(_REGISTRY)}")
    return _REGISTRY[translator_id](cfg)


def list_translators() -> List[Dict[str, str]]:
    return [
        {"id": cls.id, "display_name": cls.display_name}
        for cls in _REGISTRY.values()
    ]


# Importing the modules triggers their @register decorator.
from . import nllb_local  # noqa: E402,F401
from . import gemini_free  # noqa: E402,F401
from . import openai_translate  # noqa: E402,F401
from . import custom_http  # noqa: E402,F401
from . import noop  # noqa: E402,F401
