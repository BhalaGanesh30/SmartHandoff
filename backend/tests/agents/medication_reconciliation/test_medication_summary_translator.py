"""Unit tests for MedicationSummaryTranslator — US-033 AC Scenario 4.

Test matrix:
    - Spanish translation translates text fields only (not drug names)
    - Stopped medication reason translated when present
    - TranslationService not called for None reason field
    - common_side_effects list items translated individually
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agents.medication_reconciliation.summary.translator import (
    MedicationSummaryTranslator,
)
from app.agents.medication_reconciliation.summary.schema import (
    ChangedMedicationEntry,
    MedicationEntry,
    MedicationSummaryOutput,
    StoppedMedicationEntry,
)


@pytest.mark.asyncio
async def test_spanish_translation_translates_text_fields():
    """Text fields translated; drug names (generic_name, brand_name, dose) unchanged."""
    mock_svc = AsyncMock()
    mock_svc.translate.return_value = "traducción"

    summary = MedicationSummaryOutput(
        new=[
            MedicationEntry(
                generic_name="Lisinopril",
                brand_name="Prinivil",
                dose="10mg",
                dosing_instructions="Take 1 tablet once daily",
                purpose="to lower your blood pressure",
                common_side_effects=["dry cough"],
            )
        ]
    )
    translator = MedicationSummaryTranslator(translation_service=mock_svc)
    result = await translator.translate(summary, target_language="es")

    new_med = result.new[0]
    # Drug names NOT translated
    assert new_med.generic_name == "Lisinopril"
    assert new_med.brand_name == "Prinivil"
    assert new_med.dose == "10mg"
    # Text fields translated
    assert new_med.dosing_instructions == "traducción"
    assert new_med.purpose == "traducción"
    assert new_med.common_side_effects == ["traducción"]


@pytest.mark.asyncio
async def test_stopped_reason_translated_when_present():
    """Stopped medication reason field translated when not None."""
    mock_svc = AsyncMock()
    mock_svc.translate.return_value = "motivo traducido"

    summary = MedicationSummaryOutput(
        stopped=[
            StoppedMedicationEntry(
                generic_name="Metoprolol",
                dose="50mg",
                reason="replaced by Lisinopril",
            )
        ]
    )
    translator = MedicationSummaryTranslator(translation_service=mock_svc)
    result = await translator.translate(summary, target_language="es")

    assert result.stopped[0].reason == "motivo traducido"


@pytest.mark.asyncio
async def test_translation_service_not_called_for_none_reason():
    """TranslationService.translate() not called for None reason field."""
    mock_svc = AsyncMock()

    summary = MedicationSummaryOutput(
        stopped=[StoppedMedicationEntry(generic_name="Metoprolol", dose="50mg", reason=None)]
    )
    translator = MedicationSummaryTranslator(translation_service=mock_svc)
    await translator.translate(summary, target_language="es")

    # translate() should not be called for None fields
    mock_svc.translate.assert_not_called()


@pytest.mark.asyncio
async def test_changed_medication_dosing_and_reason_translated():
    """Changed medication translates dosing_instructions and reason."""
    mock_svc = AsyncMock()
    mock_svc.translate.side_effect = lambda text, lang: f"{text}_es"

    summary = MedicationSummaryOutput(
        changed=[
            ChangedMedicationEntry(
                generic_name="Metformin",
                previous_dose="500mg",
                new_dose="1000mg",
                dosing_instructions="Take 2 tablets daily",
                reason="dose increased",
            )
        ]
    )
    translator = MedicationSummaryTranslator(translation_service=mock_svc)
    result = await translator.translate(summary, target_language="es")

    changed_med = result.changed[0]
    assert changed_med.dosing_instructions == "Take 2 tablets daily_es"
    assert changed_med.reason == "dose increased_es"
    # Drug names not translated
    assert changed_med.generic_name == "Metformin"
    assert changed_med.previous_dose == "500mg"
    assert changed_med.new_dose == "1000mg"


@pytest.mark.asyncio
async def test_common_side_effects_list_items_translated_individually():
    """Each item in common_side_effects list translated separately."""
    mock_svc = AsyncMock()
    mock_svc.translate.side_effect = lambda text, lang: f"{text}_translated"

    summary = MedicationSummaryOutput(
        new=[
            MedicationEntry(
                generic_name="Lisinopril",
                dose="10mg",
                dosing_instructions="Take once daily",
                purpose="lower blood pressure",
                common_side_effects=["dry cough", "dizziness", "headache"],
            )
        ]
    )
    translator = MedicationSummaryTranslator(translation_service=mock_svc)
    result = await translator.translate(summary, target_language="es")

    # Verify each side effect translated
    assert result.new[0].common_side_effects == [
        "dry cough_translated",
        "dizziness_translated",
        "headache_translated",
    ]
    # Verify translate() called for each side effect
    assert mock_svc.translate.call_count == 5  # dosing + purpose + 3 side effects
