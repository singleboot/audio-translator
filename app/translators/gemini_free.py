"""Google Gemini (free tier) translator.

Install: pip install google-generativeai
Get a free key at https://aistudio.google.com/apikey
"""

from __future__ import annotations

from .base import Translator
from . import register


SYSTEM_PROMPT = (
    "You are a translation engine. Translate the user's text into the target "
    "language. Preserve tone, formatting, and named entities. Output ONLY the "
    "translation, no commentary, no quotes, no language tags."
)


@register
class GeminiTranslator(Translator):
    id = "gemini_free"
    display_name = "Gemini (free tier)"

    def __init__(self, cfg) -> None:
        c = cfg.get("translator.gemini_free", {}) or {}
        self.api_key: str = c.get("api_key", "")
        self.model_name: str = c.get("model", "gemini-1.5-flash")
        self._model = None

    def _ensure(self):
        if self._model is not None or not self.api_key:
            return
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=SYSTEM_PROMPT,
        )

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if not text.strip():
            return ""
        if not self.api_key:
            raise RuntimeError("Gemini API key not set in config.yaml (translator.gemini_free.api_key)")
        self._ensure()
        prompt = f"Source language code: {src_lang}\nTarget language code: {tgt_lang}\n\nText:\n{text}"
        resp = self._model.generate_content(prompt)
        return (resp.text or "").strip()
