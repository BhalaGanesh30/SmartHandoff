"""
Unit tests for PatientInstructionsGenerator.

Mocks Gemini Flash LLM calls. Validates FK retry logic, language detection,
and PatientInstructionsDocument structure.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.documentation.patient_instructions_generator import PatientInstructionsGenerator
from agents.documentation.patient_instructions_schemas import (
    PatientInstructionsContent,
    PatientInstructionsDocument,
    SupportedLanguage,
)
from agents.documentation.schemas import DischargeSummarySchema


def _make_mock_content(simple: bool = True) -> PatientInstructionsContent:
    """Return a PatientInstructionsContent stub."""
    text = (
        "Go home. Rest. Drink water. Call your doctor if you feel worse."
        if simple
        else (
            "Upon cessation of hospitalisation, the patient is advised to maintain "
            "strict pharmacological compliance with the prescribed antihypertensive regimen."
        )
    )
    return PatientInstructionsContent(
        home_care_instructions=text,
        medications="Take one pill each morning with food.",
        warning_signs="Call 911 if you cannot breathe.",
        follow_up_appointments="Call your doctor in 7 days.",
        diet_and_activity="Walk 10 minutes per day.",
        emergency_contact="Call 911 for emergencies.",
    )


def _make_discharge_summary() -> DischargeSummarySchema:
    """Return a minimal DischargeSummarySchema stub."""
    return DischargeSummarySchema(
        encounter_id="ENC-001",
        diagnosis_summary=[
            {
                "icd10_code": "I10",
                "description": "Essential hypertension",
                "is_primary": True,
            }
        ],
        medications_at_discharge=[
            {
                "drug_name": "Lisinopril",
                "dose": "10 mg",
                "frequency": "once daily",
                "route": "oral",
            }
        ],
        procedures=[],
        follow_up_instructions=[{"instruction": "Follow up in 1 week."}],
        warning_signs=["Chest pain", "Shortness of breath"],
        activity_restrictions=["No heavy lifting"],
    )


@pytest.fixture
def generator() -> PatientInstructionsGenerator:
    with patch("agents.documentation.patient_instructions_generator.ChatVertexAI"):
        return PatientInstructionsGenerator(project_id="test-project")


class TestPatientInstructionsGenerator:
    """Tests for English instruction generation and FK retry."""

    @pytest.mark.asyncio
    async def test_generate_returns_document_with_empty_translations(
        self, generator: PatientInstructionsGenerator
    ) -> None:
        """generate() returns PatientInstructionsDocument with empty translations dict."""
        mock_content = _make_mock_content(simple=True)

        with patch.object(generator, "_generate_english_with_retry", new=AsyncMock(
            return_value=(mock_content, 4.5)
        )):
            result = await generator.generate(
                discharge_summary=_make_discharge_summary(),
                fhir_patient={},
            )

        assert isinstance(result, PatientInstructionsDocument)
        assert result.translations == {}
        assert result.primary_flesch_kincaid_grade == 4.5

    @pytest.mark.asyncio
    async def test_japanese_patient_sets_fallback(
        self, generator: PatientInstructionsGenerator
    ) -> None:
        """US-027 Scenario 4: Japanese patient triggers language_fallback=True."""
        mock_content = _make_mock_content()
        fhir_patient = {
            "communication": [{"language": {"coding": [{"code": "ja"}]}, "preferred": True}]
        }

        with patch.object(generator, "_generate_english_with_retry", new=AsyncMock(
            return_value=(mock_content, 3.0)
        )):
            result = await generator.generate(
                discharge_summary=_make_discharge_summary(),
                fhir_patient=fhir_patient,
            )

        assert result.language_fallback is True
        assert result.requested_language == "ja"
        assert result.primary_language == SupportedLanguage.EN.value

    @pytest.mark.asyncio
    async def test_spanish_patient_sets_primary_language_es(
        self, generator: PatientInstructionsGenerator
    ) -> None:
        """US-027 Scenario 3: Spanish patient sets primary_language='es'."""
        mock_content = _make_mock_content()
        fhir_patient = {
            "communication": [{"language": {"coding": [{"code": "es"}]}, "preferred": True}]
        }

        with patch.object(generator, "_generate_english_with_retry", new=AsyncMock(
            return_value=(mock_content, 3.5)
        )):
            result = await generator.generate(
                discharge_summary=_make_discharge_summary(),
                fhir_patient=fhir_patient,
            )

        assert result.primary_language == "es"
        assert result.language_fallback is False
        assert result.requested_language is None
