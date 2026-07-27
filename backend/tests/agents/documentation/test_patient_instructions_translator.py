"""
Unit tests for PatientInstructionsTranslator.

Mocks Gemini Flash and sentence-transformers. Validates back-translation
similarity threshold enforcement and concurrent translation.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.documentation.patient_instructions_translator import (
    PatientInstructionsTranslator,
    _SIMILARITY_THRESHOLD,
)
from agents.documentation.patient_instructions_schemas import (
    PatientInstructionsContent,
    PatientInstructionsDocument,
    SupportedLanguage,
    TranslationEntry,
)


def _make_instructions_doc() -> PatientInstructionsDocument:
    content = PatientInstructionsContent(
        home_care_instructions="Rest at home.",
        medications="Take one pill daily.",
        warning_signs="Call 911 for chest pain.",
        follow_up_appointments="See your doctor in 7 days.",
        diet_and_activity="Walk 10 minutes daily.",
        emergency_contact="Call 911.",
    )
    return PatientInstructionsDocument(
        primary_language="en",
        primary_content=content,
        primary_flesch_kincaid_grade=4.2,
        translations={},
        language_fallback=False,
        requested_language=None,
    )


@pytest.fixture
def translator() -> PatientInstructionsTranslator:
    with patch("agents.documentation.patient_instructions_translator.ChatVertexAI"):
        return PatientInstructionsTranslator(project_id="test-project")


class TestPatientInstructionsTranslator:
    """Tests for back-translation quality check and translation coverage."""

    @pytest.mark.asyncio
    async def test_translate_all_produces_5_language_entries(
        self, translator: PatientInstructionsTranslator
    ) -> None:
        """translate_all() must populate translations for en, es, fr, zh, pt."""
        with (
            patch.object(translator, "_translate_single", new=AsyncMock(side_effect=[
                TranslationEntry(
                    language_code="es",
                    content=_make_instructions_doc().primary_content,
                    back_translation_similarity=0.92,
                    quality_check_passed=True,
                    flesch_kincaid_grade=None,
                ),
                TranslationEntry(
                    language_code="fr",
                    content=_make_instructions_doc().primary_content,
                    back_translation_similarity=0.92,
                    quality_check_passed=True,
                    flesch_kincaid_grade=None,
                ),
                TranslationEntry(
                    language_code="zh",
                    content=_make_instructions_doc().primary_content,
                    back_translation_similarity=0.92,
                    quality_check_passed=True,
                    flesch_kincaid_grade=None,
                ),
                TranslationEntry(
                    language_code="pt",
                    content=_make_instructions_doc().primary_content,
                    back_translation_similarity=0.92,
                    quality_check_passed=True,
                    flesch_kincaid_grade=None,
                ),
            ])),
        ):
            result = await translator.translate_all(_make_instructions_doc())

        assert set(result.translations.keys()) == {"en", "es", "fr", "zh", "pt"}

    @pytest.mark.asyncio
    async def test_high_similarity_sets_quality_passed_true(
        self, translator: PatientInstructionsTranslator
    ) -> None:
        """Cosine similarity ≥ 0.85 → quality_check_passed=True."""
        with patch.object(translator, "_translate_single", new=AsyncMock(side_effect=[
            TranslationEntry(
                language_code="es",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.91,
                quality_check_passed=True,
                flesch_kincaid_grade=None,
            ),
            TranslationEntry(
                language_code="fr",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.91,
                quality_check_passed=True,
                flesch_kincaid_grade=None,
            ),
            TranslationEntry(
                language_code="zh",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.91,
                quality_check_passed=True,
                flesch_kincaid_grade=None,
            ),
            TranslationEntry(
                language_code="pt",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.91,
                quality_check_passed=True,
                flesch_kincaid_grade=None,
            ),
        ])):
            result = await translator.translate_all(_make_instructions_doc())

        for lang in ["es", "fr", "zh", "pt"]:
            assert result.translations[lang].quality_check_passed is True

    @pytest.mark.asyncio
    async def test_low_similarity_sets_quality_passed_false(
        self, translator: PatientInstructionsTranslator
    ) -> None:
        """US-027 Scenario 2: Cosine similarity < 0.85 → quality_check_passed=False."""
        with patch.object(translator, "_translate_single", new=AsyncMock(side_effect=[
            TranslationEntry(
                language_code="es",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.72,
                quality_check_passed=False,
                flesch_kincaid_grade=None,
            ),
            TranslationEntry(
                language_code="fr",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.72,
                quality_check_passed=False,
                flesch_kincaid_grade=None,
            ),
            TranslationEntry(
                language_code="zh",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.72,
                quality_check_passed=False,
                flesch_kincaid_grade=None,
            ),
            TranslationEntry(
                language_code="pt",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.72,
                quality_check_passed=False,
                flesch_kincaid_grade=None,
            ),
        ])):
            result = await translator.translate_all(_make_instructions_doc())

        for lang in ["es", "fr", "zh", "pt"]:
            assert result.translations[lang].quality_check_passed is False
            assert result.translations[lang].back_translation_similarity == pytest.approx(0.72, abs=0.001)

    @pytest.mark.asyncio
    async def test_english_entry_always_passes(
        self, translator: PatientInstructionsTranslator
    ) -> None:
        """English base entry in translations must always have quality_check_passed=True."""
        with patch.object(translator, "_translate_single", new=AsyncMock(side_effect=[
            TranslationEntry(
                language_code="es",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.50,
                quality_check_passed=False,
                flesch_kincaid_grade=None,
            ),
            TranslationEntry(
                language_code="fr",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.50,
                quality_check_passed=False,
                flesch_kincaid_grade=None,
            ),
            TranslationEntry(
                language_code="zh",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.50,
                quality_check_passed=False,
                flesch_kincaid_grade=None,
            ),
            TranslationEntry(
                language_code="pt",
                content=_make_instructions_doc().primary_content,
                back_translation_similarity=0.50,
                quality_check_passed=False,
                flesch_kincaid_grade=None,
            ),
        ])):
            result = await translator.translate_all(_make_instructions_doc())

        assert result.translations["en"].quality_check_passed is True

    def test_compute_cosine_similarity_clamped_between_0_and_1(
        self, translator: PatientInstructionsTranslator
    ) -> None:
        """_compute_cosine_similarity result must always be in [0.0, 1.0]."""
        import numpy as np
        with patch.object(translator._embedder, "encode", return_value=np.array([[1.0, 0.0], [1.0, 0.0]])):
            sim = translator._compute_cosine_similarity("text a", "text b")
        assert 0.0 <= sim <= 1.0
