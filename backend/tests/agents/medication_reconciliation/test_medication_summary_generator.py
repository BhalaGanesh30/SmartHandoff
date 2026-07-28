"""Unit tests for MedicationSummaryGenerator — US-033 AC Scenarios 1 & 2.

Test matrix:
    - All four reconciliation categories present in output
    - Gemini Flash mock returns valid JSON → MedicationSummaryOutput produced
    - Brand name enrichment applied before Gemini call
    - Gemini returns invalid JSON → ValueError raised
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.medication_reconciliation.summary.generator import (
    MedicationSummaryGenerator,
)
from app.agents.medication_reconciliation.summary.schema import MedicationSummaryOutput

_RECONCILIATION_RESULT = {
    "new": [
        {"rxcui": "29046", "generic_name": "Lisinopril", "dose": "10mg"},
    ],
    "stopped": [
        {"rxcui": "41493", "generic_name": "Metoprolol", "dose": "50mg"},
    ],
    "changed": [
        {
            "rxcui": "6809",
            "generic_name": "Metformin",
            "dose": "500mg",
            "new_dose": "1000mg",
        }
    ],
    "continued": [
        {"rxcui": "2409", "generic_name": "Atorvastatin", "dose": "20mg"},
    ],
}

_VALID_GEMINI_RESPONSE = """{
    "new": [{
        "generic_name": "Lisinopril",
        "brand_name": "Prinivil",
        "dose": "10mg",
        "dosing_instructions": "Take 1 tablet (10mg) once daily",
        "purpose": "to lower your blood pressure",
        "common_side_effects": ["dry cough", "dizziness", "headache"]
    }],
    "stopped": [{
        "generic_name": "Metoprolol",
        "brand_name": "Lopressor",
        "dose": "50mg",
        "reason": "replaced by Lisinopril for better blood pressure control"
    }],
    "changed": [{
        "generic_name": "Metformin",
        "brand_name": null,
        "previous_dose": "500mg",
        "new_dose": "1000mg",
        "dosing_instructions": "Take 1 tablet (1000mg) twice daily with food",
        "reason": "dose increased to better control blood sugar"
    }],
    "continued": [{
        "generic_name": "Atorvastatin",
        "brand_name": "Lipitor",
        "dose": "20mg",
        "dosing_instructions": "Take 1 tablet (20mg) once daily at bedtime",
        "purpose": "to lower your cholesterol",
        "common_side_effects": ["muscle aches", "stomach upset"]
    }]
}"""


@pytest.fixture
def mock_enricher():
    enricher = AsyncMock()
    enricher.enrich.return_value = MagicMock(brand_name="Prinivil")
    return enricher


@pytest.mark.asyncio
async def test_all_reconciliation_categories_present(mock_enricher):
    """AC Scenario 1 — all four categories (new/stopped/changed/continued) in output."""
    with patch(
        "app.agents.medication_reconciliation.summary.generator.ChatVertexAI"
    ) as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content=_VALID_GEMINI_RESPONSE)
        mock_llm_cls.return_value = mock_llm

        generator = MedicationSummaryGenerator(
            enricher=mock_enricher, project="test-project"
        )
        result = await generator.generate(_RECONCILIATION_RESULT)

    assert isinstance(result, MedicationSummaryOutput)
    assert len(result.new) == 1
    assert len(result.stopped) == 1
    assert len(result.changed) == 1
    assert len(result.continued) == 1


@pytest.mark.asyncio
async def test_brand_name_enrichment_called_for_all_medications(mock_enricher):
    """AC Scenario 2 — brand name enricher called for each medication before LLM."""
    with patch(
        "app.agents.medication_reconciliation.summary.generator.ChatVertexAI"
    ) as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content=_VALID_GEMINI_RESPONSE)
        mock_llm_cls.return_value = mock_llm

        generator = MedicationSummaryGenerator(
            enricher=mock_enricher, project="test-project"
        )
        await generator.generate(_RECONCILIATION_RESULT)

    # 4 medications across all categories → 4 enrich calls
    assert mock_enricher.enrich.call_count == 4


@pytest.mark.asyncio
async def test_invalid_gemini_json_raises_value_error(mock_enricher):
    """ValueError raised when Gemini returns unparseable JSON."""
    with patch(
        "app.agents.medication_reconciliation.summary.generator.ChatVertexAI"
    ) as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="NOT VALID JSON")
        mock_llm_cls.return_value = mock_llm

        generator = MedicationSummaryGenerator(
            enricher=mock_enricher, project="test-project"
        )
        with pytest.raises(ValueError, match="invalid medication summary"):
            await generator.generate(_RECONCILIATION_RESULT)


@pytest.mark.asyncio
async def test_new_medication_has_required_fields(mock_enricher):
    """New medication entry contains purpose, dosing_instructions, common_side_effects."""
    with patch(
        "app.agents.medication_reconciliation.summary.generator.ChatVertexAI"
    ) as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content=_VALID_GEMINI_RESPONSE)
        mock_llm_cls.return_value = mock_llm

        generator = MedicationSummaryGenerator(
            enricher=mock_enricher, project="test-project"
        )
        result = await generator.generate(_RECONCILIATION_RESULT)

    new_med = result.new[0]
    assert new_med.generic_name == "Lisinopril"
    assert new_med.purpose
    assert new_med.dosing_instructions
    assert isinstance(new_med.common_side_effects, list)
