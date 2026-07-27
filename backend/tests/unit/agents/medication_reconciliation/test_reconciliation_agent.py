"""Unit tests for MedicationReconciliationAgent comparison logic.

US-030 TASK-006: 15+ parameterised medication fixtures covering all
reconciliation categories (CONTINUED, NEW, STOPPED, DOSE_CHANGED) and
both flag types (DUPLICATE, STOPPED_WITHOUT_ORDER).
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.agents.medication_reconciliation.agent import MedicationReconciliationAgent
from app.agents.medication_reconciliation.dose_parser import parse_dose
from app.agents.medication_reconciliation.models import RawMedicationEntry
from app.models.medication import (
    Medication,
    MedicationListSource,
    ReconciliationCategory,
    ReconciliationFlag,
)

# Shorthand aliases for readability
PRE_ADMIT = MedicationListSource.PRE_ADMIT
INPATIENT = MedicationListSource.INPATIENT
DISCHARGE = MedicationListSource.DISCHARGE


# ── Test Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_agent() -> MedicationReconciliationAgent:
    """Create agent with mocked dependencies."""
    return MedicationReconciliationAgent(
        fhir_fetcher=AsyncMock(),
        normaliser=AsyncMock(),
        session=AsyncMock(),
    )


def make_entry(
    source: MedicationListSource,
    name: str,
    dose_string: str | None = None,
    route: str | None = "oral",
    cui: str | None = None,
) -> RawMedicationEntry:
    """Helper to create a RawMedicationEntry with parsed dose.
    
    Args:
        source: Which FHIR list this medication came from
        name: Drug name
        dose_string: Raw dose string (e.g. "500 mg")
        route: Administration route (default: "oral")
        cui: RxNorm CUI (optional)
    
    Returns:
        RawMedicationEntry with dose_value and dose_unit pre-parsed
    """
    entry = RawMedicationEntry(
        source=source,
        fhir_id=f"{source.value}-{name[:4]}",
        name=name,
        dose_string=dose_string,
        route=route,
    )
    entry.rxnorm_cui = cui
    entry.dose_value, entry.dose_unit = parse_dose(dose_string)
    return entry


# ── 15+ Parameterized Category Test Fixtures ───────────────────────────────────


RECONCILIATION_FIXTURES = [
    # id, description, pre_admit_list, discharge_list, expected_category
    pytest.param(
        [make_entry(PRE_ADMIT, "Metformin 500mg", "500 mg", "oral", "860975")],
        [make_entry(DISCHARGE, "Metformin 500mg", "500 mg", "oral", "860975")],
        ReconciliationCategory.CONTINUED,
        id="fixture-01-continued-metformin-same-dose",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Lisinopril 5mg", "5 mg", "oral", "203644")],
        [make_entry(DISCHARGE, "Lisinopril 5mg", "5 mg", "oral", "203644")],
        ReconciliationCategory.CONTINUED,
        id="fixture-02-continued-lisinopril",
    ),
    pytest.param(
        [],
        [make_entry(DISCHARGE, "Apixaban 5mg", "5 mg", "oral", "1364430")],
        ReconciliationCategory.NEW,
        id="fixture-03-new-apixaban",
    ),
    pytest.param(
        [],
        [make_entry(DISCHARGE, "Pantoprazole 40mg", "40 mg", "oral", "40790")],
        ReconciliationCategory.NEW,
        id="fixture-04-new-pantoprazole",
    ),
    pytest.param(
        [],
        [make_entry(DISCHARGE, "Enoxaparin 40mg", "40 mg", "subcutaneous", "67108")],
        ReconciliationCategory.NEW,
        id="fixture-05-new-enoxaparin-subcutaneous",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Atorvastatin 40mg", "40 mg", "oral", "617310")],
        [],
        ReconciliationCategory.STOPPED,
        id="fixture-06-stopped-atorvastatin",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Warfarin 5mg", "5 mg", "oral", "855332")],
        [],
        ReconciliationCategory.STOPPED,
        id="fixture-07-stopped-warfarin",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Metoprolol 25mg", "25 mg", "oral", "866514")],
        [make_entry(DISCHARGE, "Metoprolol 50mg", "50 mg", "oral", "866514")],
        ReconciliationCategory.DOSE_CHANGED,
        id="fixture-08-dose-changed-metoprolol-25-to-50",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Amlodipine 5mg", "5 mg", "oral", "329526")],
        [make_entry(DISCHARGE, "Amlodipine 10mg", "10 mg", "oral", "329526")],
        ReconciliationCategory.DOSE_CHANGED,
        id="fixture-09-dose-changed-amlodipine-5-to-10",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Furosemide 20mg", "20 mg", "oral", "310429")],
        [make_entry(DISCHARGE, "Furosemide 40mg", "40 mg", "oral", "310429")],
        ReconciliationCategory.DOSE_CHANGED,
        id="fixture-10-dose-changed-furosemide-20-to-40",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Omeprazole 20mg", "20 mg", "oral", "40790")],
        [make_entry(DISCHARGE, "Omeprazole 20mg", "20 mg", "oral", "40790")],
        ReconciliationCategory.CONTINUED,
        id="fixture-11-continued-omeprazole",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Aspirin 81mg", "81 mg", "oral", "243670")],
        [make_entry(DISCHARGE, "Aspirin 81mg", "81 mg", "oral", "243670")],
        ReconciliationCategory.CONTINUED,
        id="fixture-12-continued-aspirin-81mg",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Sertraline 50mg", "50 mg", "oral", "36437")],
        [],
        ReconciliationCategory.STOPPED,
        id="fixture-13-stopped-sertraline",
    ),
    pytest.param(
        [],
        [make_entry(DISCHARGE, "Dalteparin 5000 units", "5000 units", "subcutaneous", "67108")],
        ReconciliationCategory.NEW,
        id="fixture-14-new-dalteparin-units",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Levothyroxine 50mcg", "50 mcg", "oral", "10582")],
        [make_entry(DISCHARGE, "Levothyroxine 100mcg", "100 mcg", "oral", "10582")],
        ReconciliationCategory.DOSE_CHANGED,
        id="fixture-15-dose-changed-levothyroxine-mcg",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Insulin glargine 20 units", "20 units", "subcutaneous", "261551")],
        [make_entry(DISCHARGE, "Insulin glargine 20 units", "20 units", "subcutaneous", "261551")],
        ReconciliationCategory.CONTINUED,
        id="fixture-16-continued-insulin-glargine",
    ),
    pytest.param(
        [make_entry(PRE_ADMIT, "Gabapentin 300mg", "300 mg", "oral", "25480")],
        [make_entry(DISCHARGE, "Gabapentin 600mg", "600 mg", "oral", "25480")],
        ReconciliationCategory.DOSE_CHANGED,
        id="fixture-17-dose-changed-gabapentin-300-to-600",
    ),
    pytest.param(
        [],
        [make_entry(DISCHARGE, "Clopidogrel 75mg", "75 mg", "oral", "32968")],
        ReconciliationCategory.NEW,
        id="fixture-18-new-clopidogrel",
    ),
]


# ── Comparison Logic Tests ─────────────────────────────────────────────────────


@pytest.mark.parametrize("pre,dis,expected_category", RECONCILIATION_FIXTURES)
@pytest.mark.unit
def test_compare_categories(
    mock_agent: MedicationReconciliationAgent,
    pre: list[RawMedicationEntry],
    dis: list[RawMedicationEntry],
    expected_category: ReconciliationCategory,
):
    """Test that three-way comparison assigns correct reconciliation categories.
    
    Validates all reconciliation categories:
    - CONTINUED: Same drug and dose in pre-admit and discharge
    - DOSE_CHANGED: Same drug, different dose values
    - NEW: Present in discharge only
    - STOPPED: Present in pre-admit but not discharge
    """
    raw_lists = {
        PRE_ADMIT: pre,
        INPATIENT: [],
        DISCHARGE: dis,
    }
    
    medications = mock_agent._compare(raw_lists)
    
    assert len(medications) > 0, "Expected at least one medication result"
    
    # Find medication with expected category
    matching = [m for m in medications if m.reconciliation_category == expected_category]
    
    assert len(matching) > 0, (
        f"Expected category {expected_category.value} not found. "
        f"Got categories: {[m.reconciliation_category.value for m in medications]}"
    )


@pytest.mark.unit
def test_compare_multiple_medications(mock_agent: MedicationReconciliationAgent):
    """Test that multiple medications are all processed correctly."""
    pre_list = [
        make_entry(PRE_ADMIT, "Metformin 500mg", "500 mg", "oral", "860975"),
        make_entry(PRE_ADMIT, "Warfarin 5mg", "5 mg", "oral", "855332"),
    ]
    dis_list = [
        make_entry(DISCHARGE, "Metformin 500mg", "500 mg", "oral", "860975"),
        make_entry(DISCHARGE, "Apixaban 5mg", "5 mg", "oral", "1364430"),
    ]
    
    raw_lists = {PRE_ADMIT: pre_list, INPATIENT: [], DISCHARGE: dis_list}
    medications = mock_agent._compare(raw_lists)
    
    # Should have: 1 CONTINUED (Metformin), 1 NEW (Apixaban), 1 STOPPED (Warfarin)
    assert len(medications) == 3, f"Expected 3 medications, got {len(medications)}"
    
    categories = [m.reconciliation_category for m in medications]
    assert ReconciliationCategory.CONTINUED in categories
    assert ReconciliationCategory.NEW in categories
    assert ReconciliationCategory.STOPPED in categories


@pytest.mark.unit
def test_compare_sources_list_populated(mock_agent: MedicationReconciliationAgent):
    """Test that sources list correctly reflects which FHIR lists contain each drug."""
    pre_list = [make_entry(PRE_ADMIT, "Metformin 500mg", "500 mg", "oral", "860975")]
    inp_list = [make_entry(INPATIENT, "Metformin 500mg", "500 mg", "oral", "860975")]
    dis_list = [make_entry(DISCHARGE, "Metformin 500mg", "500 mg", "oral", "860975")]
    
    raw_lists = {PRE_ADMIT: pre_list, INPATIENT: inp_list, DISCHARGE: dis_list}
    medications = mock_agent._compare(raw_lists)
    
    assert len(medications) == 1
    med = medications[0]
    
    assert PRE_ADMIT in med.sources, "PRE_ADMIT missing from sources"
    assert INPATIENT in med.sources, "INPATIENT missing from sources"
    assert DISCHARGE in med.sources, "DISCHARGE missing from sources"


# ── Duplicate Detection Tests ──────────────────────────────────────────────────


@pytest.mark.unit
def test_duplicate_detection_same_cui_same_route(mock_agent: MedicationReconciliationAgent):
    """Test that two discharge meds with same CUI and route are flagged DUPLICATE."""
    med1 = Medication(
        name="Metformin 500mg oral",
        rxnorm_cui="860975",
        route="oral",
        sources=[DISCHARGE],
        flags=[],
    )
    med2 = Medication(
        name="Metformin XR 500mg oral",
        rxnorm_cui="860975",
        route="oral",
        sources=[DISCHARGE],
        flags=[],
    )
    
    mock_agent._detect_duplicates([med1, med2])
    
    assert ReconciliationFlag.DUPLICATE in med1.flags, "med1 should be flagged DUPLICATE"
    assert ReconciliationFlag.DUPLICATE in med2.flags, "med2 should be flagged DUPLICATE"


@pytest.mark.unit
def test_duplicate_detection_different_route_not_flagged(mock_agent: MedicationReconciliationAgent):
    """Test that same CUI with different routes is NOT flagged as duplicate."""
    med1 = Medication(
        name="Metformin 500mg oral",
        rxnorm_cui="860975",
        route="oral",
        sources=[DISCHARGE],
        flags=[],
    )
    med2 = Medication(
        name="Metformin 500mg IV",
        rxnorm_cui="860975",
        route="intravenous",
        sources=[DISCHARGE],
        flags=[],
    )
    
    mock_agent._detect_duplicates([med1, med2])
    
    assert ReconciliationFlag.DUPLICATE not in med1.flags, "Different routes should not be flagged"
    assert ReconciliationFlag.DUPLICATE not in med2.flags, "Different routes should not be flagged"


@pytest.mark.unit
def test_single_discharge_med_not_flagged_as_duplicate(mock_agent: MedicationReconciliationAgent):
    """Test that a single medication is not flagged as duplicate."""
    med = Medication(
        name="Lisinopril 10mg",
        rxnorm_cui="203644",
        route="oral",
        sources=[DISCHARGE],
        flags=[],
    )
    
    mock_agent._detect_duplicates([med])
    
    assert ReconciliationFlag.DUPLICATE not in med.flags, "Single medication should not be flagged"


@pytest.mark.unit
def test_duplicate_detection_pre_admit_not_flagged(mock_agent: MedicationReconciliationAgent):
    """Test that duplicates are only detected in discharge list."""
    med1 = Medication(
        name="Warfarin 5mg",
        rxnorm_cui="855332",
        route="oral",
        sources=[PRE_ADMIT],  # Not in discharge
        flags=[],
    )
    med2 = Medication(
        name="Warfarin 5mg tablet",
        rxnorm_cui="855332",
        route="oral",
        sources=[PRE_ADMIT],  # Not in discharge
        flags=[],
    )
    
    mock_agent._detect_duplicates([med1, med2])
    
    assert ReconciliationFlag.DUPLICATE not in med1.flags, "Pre-admit meds should not be flagged"
    assert ReconciliationFlag.DUPLICATE not in med2.flags, "Pre-admit meds should not be flagged"


@pytest.mark.unit
def test_duplicate_detection_no_cui_uses_name(mock_agent: MedicationReconciliationAgent):
    """Test that duplicate detection falls back to name when CUI is None."""
    med1 = Medication(
        name="Generic Med X",
        rxnorm_cui=None,
        route="oral",
        sources=[DISCHARGE],
        flags=[],
    )
    med2 = Medication(
        name="generic med x",  # Same name, different case
        rxnorm_cui=None,
        route="oral",
        sources=[DISCHARGE],
        flags=[],
    )
    
    mock_agent._detect_duplicates([med1, med2])
    
    assert ReconciliationFlag.DUPLICATE in med1.flags, "Should detect duplicate by name"
    assert ReconciliationFlag.DUPLICATE in med2.flags, "Should detect duplicate by name"


# ── Missing Chronic Detection Tests ────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.unit
async def test_detect_missing_chronic_no_stop_order(mock_agent: MedicationReconciliationAgent):
    """Test that STOPPED medication without stop order is flagged STOPPED_WITHOUT_ORDER."""
    mock_agent._check_stop_order = AsyncMock(return_value=False)
    
    stopped_med = Medication(
        name="Atorvastatin 40mg",
        reconciliation_category=ReconciliationCategory.STOPPED,
        flags=[],
        sources=[PRE_ADMIT],
    )
    
    await mock_agent._detect_missing_chronic([stopped_med], "enc-123")
    
    assert ReconciliationFlag.STOPPED_WITHOUT_ORDER in stopped_med.flags, (
        "Stopped med without stop order should be flagged STOPPED_WITHOUT_ORDER"
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_detect_missing_chronic_with_stop_order(mock_agent: MedicationReconciliationAgent):
    """Test that STOPPED medication WITH stop order is NOT flagged."""
    mock_agent._check_stop_order = AsyncMock(return_value=True)
    
    stopped_med = Medication(
        name="Warfarin 5mg",
        reconciliation_category=ReconciliationCategory.STOPPED,
        flags=[],
        sources=[PRE_ADMIT],
    )
    
    await mock_agent._detect_missing_chronic([stopped_med], "enc-456")
    
    assert ReconciliationFlag.STOPPED_WITHOUT_ORDER not in stopped_med.flags, (
        "Stopped med WITH stop order should NOT be flagged"
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_detect_missing_chronic_only_checks_stopped(mock_agent: MedicationReconciliationAgent):
    """Test that only STOPPED medications are checked for missing stop orders."""
    mock_agent._check_stop_order = AsyncMock(return_value=False)
    
    continued_med = Medication(
        name="Metformin 500mg",
        reconciliation_category=ReconciliationCategory.CONTINUED,
        flags=[],
        sources=[PRE_ADMIT, DISCHARGE],
    )
    new_med = Medication(
        name="Apixaban 5mg",
        reconciliation_category=ReconciliationCategory.NEW,
        flags=[],
        sources=[DISCHARGE],
    )
    
    await mock_agent._detect_missing_chronic([continued_med, new_med], "enc-789")
    
    # _check_stop_order should never be called for non-STOPPED meds
    mock_agent._check_stop_order.assert_not_called()
    assert ReconciliationFlag.STOPPED_WITHOUT_ORDER not in continued_med.flags
    assert ReconciliationFlag.STOPPED_WITHOUT_ORDER not in new_med.flags


# ── Edge Cases and Integration ─────────────────────────────────────────────────


@pytest.mark.unit
def test_compare_handles_empty_lists(mock_agent: MedicationReconciliationAgent):
    """Test that comparison handles all-empty lists gracefully."""
    raw_lists = {PRE_ADMIT: [], INPATIENT: [], DISCHARGE: []}
    medications = mock_agent._compare(raw_lists)
    
    assert medications == [], "Empty input should produce empty output"


@pytest.mark.unit
def test_compare_handles_none_dose(mock_agent: MedicationReconciliationAgent):
    """Test that medications with None dose_value are handled correctly."""
    pre_list = [make_entry(PRE_ADMIT, "As directed med", None, "oral", None)]
    dis_list = [make_entry(DISCHARGE, "As directed med", None, "oral", None)]
    
    raw_lists = {PRE_ADMIT: pre_list, INPATIENT: [], DISCHARGE: dis_list}
    medications = mock_agent._compare(raw_lists)
    
    assert len(medications) == 1
    assert medications[0].reconciliation_category == ReconciliationCategory.CONTINUED


@pytest.mark.unit
def test_dose_change_detection_requires_both_values(mock_agent: MedicationReconciliationAgent):
    """Test that dose change requires both pre and discharge to have parsed values."""
    # Pre has dose, discharge has None → should be CONTINUED, not DOSE_CHANGED
    pre_list = [make_entry(PRE_ADMIT, "Med X", "500 mg", "oral", "12345")]
    dis_list = [make_entry(DISCHARGE, "Med X", None, "oral", "12345")]
    
    raw_lists = {PRE_ADMIT: pre_list, INPATIENT: [], DISCHARGE: dis_list}
    medications = mock_agent._compare(raw_lists)
    
    assert len(medications) == 1
    # Should be CONTINUED because we can't compare None dose
    assert medications[0].reconciliation_category == ReconciliationCategory.CONTINUED
