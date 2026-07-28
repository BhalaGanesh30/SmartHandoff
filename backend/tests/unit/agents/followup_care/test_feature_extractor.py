"""Unit tests for FollowUpCareAgent feature extraction (feature_extractor.py)."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.followup_care.feature_extractor import extract_features, ICD10_GROUP_DEFAULT


def make_encounter(
    admit_date=None,
    discharge_date=None,
    discharge_disposition="home",
    admitting_diagnosis="I25.10",
):
    enc = MagicMock()
    enc.id = "enc-uuid-001"
    enc.patient_id = "pat-uuid-001"
    enc.admit_date = admit_date or datetime.datetime(2026, 3, 1, 9, 0)
    enc.discharge_date = discharge_date or datetime.datetime(2026, 3, 6, 14, 0)
    enc.discharge_disposition = discharge_disposition
    enc.admitting_diagnosis = admitting_diagnosis
    return enc


def make_patient(dob=datetime.date(1954, 1, 15)):
    pat = MagicMock()
    pat.id = "pat-uuid-001"
    pat.dob = dob
    return pat


@pytest.fixture
def mock_session(make_enc=None, make_pat=None):
    session = AsyncMock()
    enc = make_encounter()
    pat = make_patient()

    def side_effect(stmt):
        result = AsyncMock()
        # Determine which model is being queried by inspecting the statement class name
        class_name = stmt.column_descriptions[0]["entity"].__name__ if hasattr(stmt, "column_descriptions") else ""
        if "Encounter" in str(stmt):
            result.scalar_one_or_none.return_value = enc
            result.scalar_one.return_value = 1  # prior admissions count
        elif "Patient" in str(stmt):
            result.scalar_one_or_none.return_value = pat
        elif "Medication" in str(stmt):
            result.scalar_one.return_value = 5  # medication count
        return result

    session.execute = AsyncMock(side_effect=side_effect)
    return session


@pytest.mark.asyncio
async def test_age_calculated_correctly():
    session = AsyncMock()
    enc = make_encounter(admit_date=datetime.datetime(2026, 3, 1))
    pat = make_patient(dob=datetime.date(1954, 1, 15))

    def execute_side_effect(stmt):
        result = MagicMock()
        if "Patient" in str(stmt):
            result.scalar_one_or_none.return_value = pat
        elif "Encounter" in str(stmt) and "count" not in str(stmt).lower():
            result.scalar_one_or_none.return_value = enc
        else:
            result.scalar_one.return_value = 0
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    fhir_client = AsyncMock()
    fhir_client.get_conditions.return_value = []

    features = await extract_features(session, fhir_client, "enc-uuid-001")
    # age ≈ 72.1 (born 1954-01-15, admit 2026-03-01)
    assert 71.0 < features["age"] < 73.0


@pytest.mark.asyncio
async def test_los_days_calculated_from_admit_and_discharge():
    session = AsyncMock()
    admit = datetime.datetime(2026, 3, 1, 9, 0)
    discharge = datetime.datetime(2026, 3, 6, 14, 0)  # 5.208 days
    enc = make_encounter(admit_date=admit, discharge_date=discharge)
    pat = make_patient()

    def execute_side_effect(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = pat if "Patient" in str(stmt) else enc
        result.scalar_one.return_value = 0
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    fhir_client = AsyncMock()
    fhir_client.get_conditions.return_value = []

    features = await extract_features(session, fhir_client, "enc-uuid-001")
    assert 5.0 < features["los_days"] < 6.0


@pytest.mark.asyncio
async def test_fhir_failure_defaults_num_comorbidities_to_zero():
    """FHIR unavailability must not crash the agent — degrade gracefully."""
    session = AsyncMock()
    enc = make_encounter()
    pat = make_patient()

    def execute_side_effect(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = pat if "Patient" in str(stmt) else enc
        result.scalar_one.return_value = 0
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    fhir_client = AsyncMock()
    fhir_client.get_conditions.side_effect = ConnectionError("FHIR unreachable")

    features = await extract_features(session, fhir_client, "enc-uuid-001")
    assert features["num_comorbidities"] == 0.0


@pytest.mark.asyncio
async def test_unknown_icd10_prefix_maps_to_default_group():
    session = AsyncMock()
    enc = make_encounter(admitting_diagnosis="X99.0")  # "X" not in ICD10_GROUP_MAP
    pat = make_patient()

    def execute_side_effect(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = pat if "Patient" in str(stmt) else enc
        result.scalar_one.return_value = 0
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    fhir_client = AsyncMock()
    fhir_client.get_conditions.return_value = []

    features = await extract_features(session, fhir_client, "enc-uuid-001")
    assert features["primary_diagnosis_group"] == float(ICD10_GROUP_DEFAULT)
