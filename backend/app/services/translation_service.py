"""Simple translation service wrapping Vertex AI Gemini Flash.

Provides a lightweight text translation interface for reuse across multiple agents.
Used by US-027 (patient instructions) and US-033 (medication summaries).

Design refs:
    US-027 TASK-004 — Gemini Flash translation with temperature=0.1
    US-033 TASK-005 — Reuse translation pipeline for medication summaries
    design.md §4.1  — Vertex AI Gemini 1.5 Flash for translation
"""
from __future__ import annotations

import logging

from langchain_google_vertexai import ChatVertexAI

logger = logging.getLogger(__name__)

# Language names for Gemini prompts
_LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish",
    "fr": "French",
    "zh": "Chinese (Simplified)",
    "pt": "Portuguese (Brazilian)",
}

_TRANSLATION_PROMPT_TEMPLATE = (
    "You are a professional medical translator. "
    "Translate the following text from English to {target_language}. "
    "Keep the same plain-language style. Preserve all medical information exactly. "
    "Do not add or remove any medical instructions.\n\n"
    "--- ENGLISH TEXT ---\n{text}\n--- END ---\n\n"
    "Return only the translated text in {target_language}. Do not include any English."
)


class TranslationService:
    """Simple Gemini-powered translation service for medical text.

    Uses Gemini Flash with low temperature for consistent translations.
    Supports: es, fr, zh, pt (per FR-022).

    Args:
        project: GCP project ID for Vertex AI.
        location: GCP region for Vertex AI (default: us-central1).
    """

    def __init__(self, project: str, location: str = "us-central1") -> None:
        self._llm = ChatVertexAI(
            model_name="gemini-1.5-flash",
            project=project,
            location=location,
            temperature=0.1,  # Low for consistency (US-027)
            max_output_tokens=2048,
        )

    async def translate(
        self,
        text: str,
        target_language: str,
        source_language: str = "en",
    ) -> str:
        """Translate text using Gemini Flash.

        Args:
            text: Source text to translate.
            target_language: ISO 639-1 language code (es, fr, zh, pt).
            source_language: Source language code (default: en).

        Returns:
            Translated text in target_language.

        Raises:
            ValueError: If target_language is not supported.
        """
        if source_language != "en":
            raise ValueError(f"Only English source supported, got: {source_language}")

        if target_language not in _LANGUAGE_NAMES:
            raise ValueError(
                f"Unsupported target language: {target_language}. "
                f"Supported: {list(_LANGUAGE_NAMES.keys())}"
            )

        lang_name = _LANGUAGE_NAMES[target_language]
        prompt = _TRANSLATION_PROMPT_TEMPLATE.format(
            target_language=lang_name,
            text=text,
        )

        response = await self._llm.ainvoke(prompt)
        translated = response.content.strip()

        logger.debug(
            "Translated %d chars to %s (%d chars output)",
            len(text),
            target_language,
            len(translated),
        )

        return translated
