"""Generic 'bring your own' HTTP translator.

Configure URL, method, headers, body template, and a pointer to the response
field that contains the translated text (dot-separated).
"""

from __future__ import annotations

import json
from typing import Any

from .base import Translator
from . import register


@register
class CustomHTTPTranslator(Translator):
    id = "custom_http"
    display_name = "Custom HTTP"

    def __init__(self, cfg) -> None:
        c = cfg.get("translator.custom_http", {}) or {}
        self.url: str = c.get("url", "")
        self.method: str = c.get("method", "POST").upper()
        self.headers: dict = c.get("headers", {}) or {}
        self.body_template: str = c.get(
            "body_template",
            '{"text": "{text}", "source": "{src}", "target": "{tgt}"}',
        )
        self.response_text_path: str = c.get("response_text_path", "translation")

    def _walk(self, obj: Any, path: str) -> Any:
        cur = obj
        for part in path.split("."):
            if cur is None:
                return None
            if part.isdigit():
                cur = cur[int(part)]
            else:
                cur = cur[part] if isinstance(cur, dict) and part in cur else None
        return cur

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if not text.strip():
            return ""
        if not self.url:
            raise RuntimeError("custom_http translator has no URL configured")
        import requests  # type: ignore
        body_str = self.body_template.format(text=text, src=src_lang, tgt=tgt_lang)
        try:
            payload = json.loads(body_str)
            data = None
        except json.JSONDecodeError:
            payload = None
            data = body_str
        resp = requests.request(
            self.method,
            self.url,
            headers=self.headers,
            json=payload,
            data=data,
            timeout=60,
        )
        resp.raise_for_status()
        try:
            obj = resp.json()
        except Exception:
            return resp.text.strip()
        out = self._walk(obj, self.response_text_path)
        return (out or "").strip() if isinstance(out, str) else str(out).strip()
