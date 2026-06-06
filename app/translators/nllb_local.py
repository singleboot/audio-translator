"""Local NLLB-200 translator. Free, runs on GPU/CPU.

Install: pip install transformers sentencepiece sacremoses
First run downloads the model.
"""

from __future__ import annotations

from typing import List

from .base import Translator
from . import register


# NLLB uses its own language codes (e.g. "eng_Latn", "hin_Dev").
# Map common short codes to NLLB codes.
NLLB_CODE_MAP = {
    "en": "eng_Latn", "es": "spa_Latn", "fr": "fra_Latn", "de": "deu_Latn",
    "it": "ita_Latn", "pt": "por_Latn", "ru": "rus_Cyrl", "zh": "zho_Hans",
    "ja": "jpn_Jpan", "ko": "kor_Hang", "ar": "arb_Arab", "hi": "hin_Dev",
    "tr": "tur_Latn", "nl": "nld_Latn", "pl": "pol_Latn", "cs": "ces_Latn",
    "hu": "hun_Latn", "sv": "swe_Latn", "fi": "fin_Latn", "da": "dan_Latn",
    "no": "nob_Latn", "el": "ell_Grek", "he": "heb_Hebr", "id": "ind_Latn",
    "ms": "msa_Latn", "vi": "vie_Latn", "th": "tha_Thai", "uk": "ukr_Cyrl",
    "ro": "ron_Latn", "bg": "bul_Cyrl", "sk": "slk_Latn", "hr": "hrv_Latn",
    "fa": "pes_Arab", "bn": "ben_Beng", "ta": "tam_Taml", "ur": "urd_Arab",
    "sw": "swh_Latn", "sr": "srp_Cyrl", "sl": "slv_Latn", "lt": "lit_Latn",
    "lv": "lvs_Latn", "et": "est_Latn", "is": "isl_Latn", "mk": "mkd_Cyrl",
}


def _to_nllb(code: str) -> str:
    if "_" in code:
        return code
    return NLLB_CODE_MAP.get(code.lower(), code)


@register
class NLLBLocalTranslator(Translator):
    id = "nllb_local"
    display_name = "NLLB-200 (local, free)"

    def __init__(self, cfg) -> None:
        c = cfg.get("translator.nllb_local", {}) or {}
        self.model_name: str = c.get("model", "facebook/nllb-200-distilled-600M")
        device = c.get("device", "auto")
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"
        self.device = device
        self._tok = None
        self._model = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM  # type: ignore
        self._tok = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name).to(self.device)

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if not text.strip():
            return ""
        self._ensure_loaded()
        import torch  # type: ignore
        self._tok.src_lang = _to_nllb(src_lang)
        encoded = self._tok(text, return_tensors="pt", truncation=True, max_length=1024).to(self.device)
        tgt_code = _to_nllb(tgt_lang)
        forced_bos = self._tok.convert_tokens_to_ids(tgt_code)
        with torch.no_grad():
            out = self._model.generate(
                **encoded,
                forced_bos_token_id=forced_bos,
                max_new_tokens=1024,
                num_beams=3,
            )
        return self._tok.decode(out[0], skip_special_tokens=True).strip()
