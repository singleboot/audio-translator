"""OpenAI-compatible chat translator (works with OpenAI, Azure, local proxies).

Install: pip install openai
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
class OpenAITranslator(Translator):
    id = "openai"
    display_name = "OpenAI / compatible"

    def __init__(self, cfg) -> None:
        c = cfg.get("translator.openai", {}) or {}
        self.api_key: str = c.get("api_key", "")
        self.model: str = c.get("model", "gpt-4o-mini")
        self.base_url: str = c.get("base_url", "https://api.openai.com/v1")
        self._client = None

    def _ensure(self):
        if self._client is not None or not self.api_key:
            return
        from openai import OpenAI  # type: ignore
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if not text.strip():
            return ""
        if not self.api_key:
            raise RuntimeError("OpenAI API key not set in config.yaml (translator.openai.api_key)")
        self._ensure()
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Source language code: {src_lang}\n"
                        f"Target language code: {tgt_lang}\n\n"
                        f"Text:\n{text}"
                    ),
                },
            ],
        )
        return (resp.choices[0].message.content or "").strip()
