"""
Unit tests for FHIR Encounter Fetcher (TASK-002).

Tests cover:
- US-025 AC Scenario 3: Fetcher returns conditions (ICD-10), medications (RxNorm)
- US-025 AC Scenario 4: PHI stripping at fetcher level
- DoD: Length-of-stay calculation
- DoD: Parallel async fetch

Design refs:
    TASK-002 — FHIREncounterFetcher unit tests
    US-025   — Documentation Agent FHIR integration
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from agents.documentation.fhir_fetcher import (
    FHIREncounterFetcher,
    EncounterContext,
    DiagnosisContext,
    MedicationContext,
)
from app.core.fhir.models import (
    EncounterModel,
    ConditionModel,
    MedicationStatementModel,
)


# ─────────────────────────────────────────────────────────────────────────────
# Mock Data Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_encounter_model():
    """Mock EncounterModel with typical inpatient data."""
    return EncounterModel(
        id="ENC-001",
        patient_id="PAT-001",
        status="finished",
        class_code="inpatient",
        period_start=datetime(2026, 7, 10, 8, 0, 0),
        period_end=datetime(2026, 7, 14, 10, 0, 0),
    )


@pytest.fixture
def mock_conditions():
    """Mock ConditionModel list with ICD-10 codes."""
    return [
        ConditionModel(
            id="COND-001",
            patient_id="PAT-001",
            clinical_status="active",
            verification_status="confirmed",
            category=["encounter-diagnosis"],
            severity="severe",
            code_display="Heart failure",
            code_system="http://hl7.org/fhir/sid/icd-10-cm",
            code_value="I50.9",
            onset_datetime=datetime(2026, 7, 10, 8, 0, 0),
        ),
        ConditionModel(
            id="COND-002",
            patient_id="PAT-001",
            clinical_status="active",
            verification_status="confirmed",
            category=["problem-list-item"],
            severity="moderate",
            code_display="Type 2 diabetes mellitus",
            code_system="http://hl7.org/fhir/sid/icd-10-cm",
            code_value="E11.9",
            onset_datetime=datetime(2025, 1, 1, 0, 0, 0),
        ),
    ]


@pytest.fixture
def mock_medications():
    """Mock MedicationStatementModel list with RxNorm codes."""
    return [
        MedicationStatementModel(
            id="MED-001",
            patient_id="PAT-001",
            medication_display="lisinopril 10 mg oral tablet",
            medication_code="197884",  # RxNorm code
            status="active",
            dosage_text="10 mg once daily",
            effective_start=datetime(2026, 7, 10, 8, 0, 0),
        ),
        MedicationStatementModel(
            id="MED-002",
            patient_id="PAT-001",
            medication_display="metformin 500 mg oral tablet",
            medication_code="860975",  # RxNorm code
            status="active",
            dosage_text="500 mg twice daily with meals",
            effective_start=datetime(2025, 1, 1, 0, 0, 0),
        ),
    ]


@pytest.fixture
def mock_fhir_client(mock_encounter_model, mock_conditions, mock_medications):
    """Mock FHIRClient with async methods."""
    client = MagicMock()
    client.get_encounter_by_id = AsyncMock(return_value=mock_encounter_model)
    client.get_conditions = AsyncMock(return_value=mock_conditions)
    client.get_medication_statements = AsyncMock(return_value=mock_medications)
    return client


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_encounter_context(mock_fhir_client):
    """
    Test: Fetcher returns EncounterContext with all expected fields.
    
    AC Coverage: US-025 AC Scenario 3 (partial)
    """
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    context = await fetcher.fetch("ENC-001")

    assert isinstance(context, EncounterContext)
    assert context.encounter_id == "ENC-001"
    assert context.encounter_type == "inpatient"
    assert context.admission_reason == "Heart failure"


@pytest.mark.asyncio
async def test_diagnoses_include_icd10_codes(mock_fhir_client):
    """
    Test: Fetcher extracts ICD-10 codes from Condition resources.
    
    AC Coverage: US-025 AC Scenario 3
    DoD: ICD-10 codes extracted from Condition.code.coding
    """
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    context = await fetcher.fetch("ENC-001")

    assert len(context.diagnoses) == 2
    assert context.diagnoses[0].icd10_code == "I50.9"
    assert context.diagnoses[0].description == "Heart failure"
    assert context.diagnoses[0].is_primary is True  # encounter-diagnosis category

    assert context.diagnoses[1].icd10_code == "E11.9"
    assert context.diagnoses[1].description == "Type 2 diabetes mellitus"
    assert context.diagnoses[1].is_primary is False  # problem-list-item category


@pytest.mark.asyncio
async def test_medications_include_rxnorm_codes(mock_fhir_client):
    """
    Test: Fetcher extracts RxNorm codes from MedicationStatement resources.
    
    AC Coverage: US-025 AC Scenario 3
    DoD: RxNorm codes extracted from MedicationStatement.medicationCodeableConcept.coding
    """
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    context = await fetcher.fetch("ENC-001")

    assert len(context.medications) == 2
    assert context.medications[0].drug_name == "lisinopril 10 mg oral tablet"
    assert context.medications[0].rxnorm_code == "197884"
    assert context.medications[0].dose == "10 mg once daily"

    assert context.medications[1].drug_name == "metformin 500 mg oral tablet"
    assert context.medications[1].rxnorm_code == "860975"


@pytest.mark.asyncio
async def test_context_contains_no_phi_fields(mock_fhir_client):
    """
    Test: EncounterContext dataclass has no direct PII fields.
    
    AC Coverage: US-025 AC Scenario 4
    DoD: PHI field names (patient_name, dob, ssn, address, phone) never appear
    """
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    context = await fetcher.fetch("ENC-001")

    phi_attrs = {"patient_name", "date_of_birth", "address", "phone", "ssn", "mrn"}
    context_fields = set(context.__dataclass_fields__.keys())
    
    overlap = phi_attrs & context_fields
    assert not overlap, f"PHI fields found in EncounterContext: {overlap}"


@pytest.mark.asyncio
async def test_calculate_los_returns_correct_days(mock_fhir_client):
    """
    Test: Length-of-stay calculation from Encounter.period.start/end.
    
    DoD: Length-of-stay calculated from Encounter.period.start/end
    """
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    context = await fetcher.fetch("ENC-001")

    # period_start: 2026-07-10 08:00
    # period_end:   2026-07-14 10:00
    # Expected LOS: 4 days
    assert context.length_of_stay_days == 4


@pytest.mark.asyncio
async def test_parallel_async_fetch(mock_fhir_client):
    """
    Test: Fetcher performs parallel async fetch of Conditions and MedicationStatements.
    
    DoD: Parallel async fetch of Encounter, Conditions, and MedicationStatements
    """
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    await fetcher.fetch("ENC-001")

    # Verify that get_conditions and get_medication_statements were called
    mock_fhir_client.get_conditions.assert_called_once_with("PAT-001")
    mock_fhir_client.get_medication_statements.assert_called_once_with("PAT-001")


@pytest.mark.asyncio
async def test_empty_conditions_list(mock_fhir_client):
    """
    Test: Fetcher handles empty conditions list gracefully.
    """
    mock_fhir_client.get_conditions = AsyncMock(return_value=[])
    
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    context = await fetcher.fetch("ENC-001")

    assert len(context.diagnoses) == 0
    assert context.admission_reason == "Not specified"


@pytest.mark.asyncio
async def test_empty_medications_list(mock_fhir_client):
    """
    Test: Fetcher handles empty medications list gracefully.
    """
    mock_fhir_client.get_medication_statements = AsyncMock(return_value=[])
    
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    context = await fetcher.fetch("ENC-001")

    assert len(context.medications) == 0


@pytest.mark.asyncio
async def test_missing_period_returns_none_los(mock_fhir_client, mock_encounter_model):
    """
    Test: Missing encounter period returns None for length_of_stay_days.
    """
    # Create encounter with no period
    mock_encounter_model.period_start = None
    mock_encounter_model.period_end = None
    
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    context = await fetcher.fetch("ENC-001")

    assert context.length_of_stay_days is None


@pytest.mark.asyncio
async def test_admission_reason_uses_encounter_diagnosis(mock_fhir_client, mock_conditions):
    """
    Test: Admission reason extracted from first encounter-diagnosis category condition.
    """
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    context = await fetcher.fetch("ENC-001")

    # First condition has category=["encounter-diagnosis"] 
    assert context.admission_reason == "Heart failure"


@pytest.mark.asyncio
async def test_medication_without_rxnorm_code(mock_fhir_client, mock_medications):
    """
    Test: Medication without RxNorm code has rxnorm_code=None.
    """
    # Remove RxNorm code from first medication
    mock_medications[0].medication_code = None
    
    fetcher = FHIREncounterFetcher(mock_fhir_client)
    context = await fetcher.fetch("ENC-001")

    assert context.medications[0].rxnorm_code is None
    assert context.medications[0].drug_name == "lisinopril 10 mg oral tablet"
