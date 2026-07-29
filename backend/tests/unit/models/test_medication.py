"""Unit tests for medication models and schemas.

US-030 TASK-006: Validates enum values and Pydantic schema serialization.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.models.medication import (
    Medication,
    MedicationListSource,
    ReconciliationCategory,
    ReconciliationFlag,
)
from app.schemas.medication import (
    MedicationReconciliationResponse,
    MedicationReconciliationResult,
)


# ── Enum Value Tests ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_reconciliation_category_enum_values():
    """Test that ReconciliationCategory enum has all expected values."""
    assert ReconciliationCategory.CONTINUED.value == "CONTINUED"
    assert ReconciliationCategory.NEW.value == "NEW"
    assert ReconciliationCategory.STOPPED.value == "STOPPED"
    assert ReconciliationCategory.DOSE_CHANGED.value == "DOSE_CHANGED"


@pytest.mark.unit
def test_reconciliation_flag_enum_values():
    """Test that ReconciliationFlag enum has all expected values."""
    assert ReconciliationFlag.DUPLICATE.value == "DUPLICATE"
    assert ReconciliationFlag.STOPPED_WITHOUT_ORDER.value == "STOPPED_WITHOUT_ORDER"


@pytest.mark.unit
def test_medication_list_source_enum_values():
    """Test that MedicationListSource enum has all expected values."""
    assert MedicationListSource.PRE_ADMIT.value == "PRE_ADMIT"
    assert MedicationListSource.INPATIENT.value == "INPATIENT"
    assert MedicationListSource.DISCHARGE.value == "DISCHARGE"


# ── ORM Model Tests ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_medication_orm_creation():
    """Test that Medication ORM model can be instantiated."""
    med = Medication(
        id=uuid4(),
        encounter_id=uuid4(),
        name="Metformin 500mg",
        rxnorm_cui="860975",
        reconciliation_category=ReconciliationCategory.CONTINUED,
        flags=[ReconciliationFlag.DUPLICATE],
        dose_value=500.0,
        dose_unit="mg",
        route="oral",
        frequency="twice daily",
        sources=[MedicationListSource.PRE_ADMIT, MedicationListSource.DISCHARGE],
        reconciliation_completed_at=datetime.now(timezone.utc),
    )
    
    assert med.name == "Metformin 500mg"
    assert med.rxnorm_cui == "860975"
    assert med.reconciliation_category == ReconciliationCategory.CONTINUED
    assert ReconciliationFlag.DUPLICATE in med.flags
    assert med.dose_value == 500.0
    assert med.dose_unit == "mg"


@pytest.mark.unit
def test_medication_orm_nullable_fields():
    """Test that nullable fields can be None."""
    med = Medication(
        id=uuid4(),
        encounter_id=uuid4(),
        name="As directed medication",
        rxnorm_cui=None,  # Can be None
        reconciliation_category=None,  # Can be None before reconciliation
        flags=[],
        dose_value=None,  # Can be None
        dose_unit=None,  # Can be None
        route=None,  # Can be None
        frequency=None,  # Can be None
        sources=[],
        reconciliation_completed_at=None,  # Can be None before completion
    )
    
    assert med.rxnorm_cui is None
    assert med.dose_value is None
    assert med.reconciliation_completed_at is None


# ── Pydantic Schema Tests ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_medication_reconciliation_result_schema():
    """Test MedicationReconciliationResult Pydantic schema serialization."""
    result = MedicationReconciliationResult(
        id=uuid4(),
        name="Metformin 500mg",
        rxnorm_cui="860975",
        reconciliation_category=ReconciliationCategory.CONTINUED,
        pre_admit=True,
        inpatient=False,
        discharge=True,
        flags=[ReconciliationFlag.DUPLICATE],
        dose="500 mg",
        route="oral",
        frequency="twice daily",
    )
    
    # Test serialization to dict
    data = result.model_dump()
    assert data["name"] == "Metformin 500mg"
    assert data["rxnorm_cui"] == "860975"
    assert data["reconciliation_category"] == "CONTINUED"
    assert data["pre_admit"] is True
    assert data["discharge"] is True
    assert data["flags"] == ["DUPLICATE"]


@pytest.mark.unit
def test_medication_reconciliation_response_schema():
    """Test MedicationReconciliationResponse Pydantic schema serialization."""
    encounter_id = uuid4()
    med_id = uuid4()
    now = datetime.now(timezone.utc)
    
    response = MedicationReconciliationResponse(
        encounter_id=encounter_id,
        total_medications=2,
        reconciliation_completed_at=now.isoformat(),
        medications=[
            MedicationReconciliationResult(
                id=med_id,
                name="Metformin 500mg",
                rxnorm_cui="860975",
                reconciliation_category=ReconciliationCategory.CONTINUED,
                pre_admit=True,
                inpatient=False,
                discharge=True,
                flags=[],
                dose="500 mg",
                route="oral",
                frequency="twice daily",
            ),
            MedicationReconciliationResult(
                id=uuid4(),
                name="Apixaban 5mg",
                rxnorm_cui="1364430",
                reconciliation_category=ReconciliationCategory.NEW,
                pre_admit=False,
                inpatient=False,
                discharge=True,
                flags=[],
                dose="5 mg",
                route="oral",
                frequency="twice daily",
            ),
        ],
    )
    
    # Test serialization
    data = response.model_dump()
    assert str(data["encounter_id"]) == str(encounter_id)
    assert data["total_medications"] == 2
    assert len(data["medications"]) == 2
    assert data["medications"][0]["name"] == "Metformin 500mg"


@pytest.mark.unit
def test_medication_reconciliation_result_optional_fields():
    """Test that optional fields can be None in schema."""
    result = MedicationReconciliationResult(
        id=uuid4(),
        name="As directed medication",
        rxnorm_cui=None,
        reconciliation_category=None,
        pre_admit=True,
        inpatient=False,
        discharge=False,
        flags=[],
        dose=None,
        route=None,
        frequency=None,
    )
    
    data = result.model_dump()
    assert data["rxnorm_cui"] is None
    assert data["dose"] is None
    assert data["route"] is None


@pytest.mark.unit
def test_medication_reconciliation_response_empty_medications():
    """Test response with no medications (pending reconciliation case)."""
    response = MedicationReconciliationResponse(
        encounter_id=uuid4(),
        total_medications=0,
        reconciliation_completed_at=None,
        medications=[],
    )
    
    data = response.model_dump()
    assert data["total_medications"] == 0
    assert data["reconciliation_completed_at"] is None
    assert data["medications"] == []


@pytest.mark.unit
def test_medication_reconciliation_result_json_serialization():
    """Test that schema can be serialized to JSON."""
    result = MedicationReconciliationResult(
        id=uuid4(),
        name="Warfarin 5mg",
        rxnorm_cui="855332",
        reconciliation_category=ReconciliationCategory.STOPPED,
        pre_admit=True,
        inpatient=True,
        discharge=False,
        flags=[ReconciliationFlag.STOPPED_WITHOUT_ORDER],
        dose="5 mg",
        route="oral",
        frequency="once daily",
    )
    
    # Test JSON serialization
    json_str = result.model_dump_json()
    assert "Warfarin 5mg" in json_str
    assert "855332" in json_str
    assert "STOPPED" in json_str
    assert "STOPPED_WITHOUT_ORDER" in json_str
