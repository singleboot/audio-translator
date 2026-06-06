"""AI4Bharat Indic-Parler-TTS — local, 21 Indic languages + English, 69 speakers.

Install: pip install git+https://github.com/huggingface/parler-tts.git
First run downloads the model weights from ai4bharat/indic-parler-tts (0.9B params).

Supports 21 languages with named speakers, emotion rendering, and
description-based voice design (pitch, speed, expressivity, etc).
Does NOT support reference-audio voice cloning — voice consistency
is achieved via speaker names in the text description.
"""

from __future__ import annotations

import os
from typing import List, Optional

from .base import TTSEngine
from . import register


# 21 official Indic-Parler-TTS languages (ISO 639-1 or custom codes).
INDIC_LANGS = [
    "as",  # Assamese
    "bn",  # Bengali
    "brx", # Bodo
    "doi", # Dogri
    "en",  # English (Indian accent available)
    "gu",  # Gujarati
    "hi",  # Hindi
    "kn",  # Kannada
    "kok", # Konkani
    "mai", # Maithili
    "ml",  # Malayalam
    "mni", # Manipuri
    "mr",  # Marathi
    "ne",  # Nepali
    "or",  # Odia
    "sa",  # Sanskrit
    "sat", # Santali
    "sd",  # Sindhi
    "ta",  # Tamil
    "te",  # Telugu
    "ur",  # Urdu
]

# Recommended speakers per language (from the model card).
# Using the first one as default for each language.
RECOMMENDED_SPEAKERS = {
    "as":  ["Amit", "Sita"],
    "bn":  ["Arjun", "Aditi"],
    "brx": ["Bikram", "Maya"],
    "doi": ["Karan"],
    "en":  ["Thoma", "Mary", "Swapna", "Meera", "Kabir"],
    "gu":  ["Yash", "Neha"],
    "hi":  ["Rohit", "Divya"],
    "kn":  ["Suresh", "Anu"],
    "kok": ["Kishor"],
    "mai": ["Rajesh"],
    "ml":  ["Anjali", "Harish"],
    "mni": ["Laishram", "Ranjit"],
    "mr":  ["Sanjay", "Sunita"],
    "ne":  ["Amrita"],
    "or":  ["Manas", "Debjani"],
    "sa":  ["Aryan"],
    "sat": ["Somali"],
    "sd":  ["Shanti"],
    "ta":  ["Jaya", "Kavitha"],
    "te":  ["Prakash", "Lalitha"],
    "ur":  ["Faisal"],
}

# Default descriptions per language group.
BASE_DESCRIPTION = (
    "A speaker delivers speech at a moderate pace with a clear voice. "
    "The recording is of very high quality with no background noise."
)


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


@register
class IndicParlerTTSEngine(TTSEngine):
    id = "indic_parler_tts"
    display_name = "Indic-Parler-TTS (local, 21 Indic langs, 69 speakers)"
    supports_voice_clone = False
    requires_network = False

    def __init__(self, cfg) -> None:
        c = cfg.get("tts.indic_parler_tts", {}) or {}
        self.device = _resolve_device(c.get("device", "auto"))
        self.speaker_override = c.get("speaker", "") or ""
        self.description_override = c.get("description", "") or ""
        self.emotion = c.get("emotion", "") or ""
        self._model = None
        self._tokenizer = None
        self._desc_tokenizer = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        try:
            from parler_tts import ParlerTTSForConditionalGeneration  # type: ignore
            from transformers import AutoTokenizer
        except ImportError:
            raise RuntimeError(
                "Indic-Parler-TTS not installed. "
                "Run: pip install git+https://github.com/huggingface/parler-tts.git"
            )
        model_id = "ai4bharat/indic-parler-tts"
        self._model = ParlerTTSForConditionalGeneration.from_pretrained(model_id)
        self._model.to(self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(model_id)
        self._desc_tokenizer = AutoTokenizer.from_pretrained(
            self._model.config.text_encoder._name_or_path
        )

    def supported_languages(self) -> List[str]:
        return list(INDIC_LANGS)

    def _build_description(self, language: str, reference_audio) -> str:
        if self.description_override:
            return self.description_override
        speakers = RECOMMENDED_SPEAKERS.get(language, [])
        speaker_name = self.speaker_override or (speakers[0] if speakers else "")
        if speaker_name:
            desc = f"{speaker_name}'s voice is clear and natural, "
        else:
            desc = "A voice that is clear and natural, "
        if self.emotion:
            desc += f"with a {self.emotion} tone, "
        desc += "delivered at a moderate pace with high recording quality."
        return desc

    def synth(self, text: str, language: str, reference_audio, out_path: str) -> str:
        if not text.strip():
            raise ValueError("empty text")
        if language not in INDIC_LANGS:
            raise ValueError(
                f"Indic-Parler-TTS does not support language '{language}'. "
                f"Supported: {INDIC_LANGS}"
            )
        self._ensure_loaded()
        description = self._build_description(language, reference_audio)
        desc_inputs = self._desc_tokenizer(description, return_tensors="pt").to(self.device)
        prompt_inputs = self._tokenizer(text, return_tensors="pt").to(self.device)
        generation = self._model.generate(
            input_ids=desc_inputs.input_ids,
            attention_mask=desc_inputs.attention_mask,
            prompt_input_ids=prompt_inputs.input_ids,
            prompt_attention_mask=prompt_inputs.attention_mask,
        )
        audio_arr = generation.cpu().numpy().squeeze()
        import soundfile as sf
        sf.write(out_path, audio_arr, self._model.config.sampling_rate)
        if not os.path.exists(out_path):
            raise RuntimeError("Indic-Parler-TTS did not produce an output file")
        return out_path
