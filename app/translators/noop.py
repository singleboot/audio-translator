"""No-op / identity translator: returns the source text unchanged.

Useful for testing the pipeline without a real translator,
or for cases where the target language is the same as source.
"""

from .base import Translator
from . import register


@register
class NoopTranslator(Translator):
    id = "noop"
    display_name = "Passthrough (no translation)"

    def __init__(self, cfg=None) -> None:
        pass

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        return text