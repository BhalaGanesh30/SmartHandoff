"""Unit tests for FHIR Pydantic wrapper models.

Tests:
- Valid FHIR resources convert to Pydantic models
- Invalid FHIR resources raise FHIRValidationError
- PatientModel resolution_method and partial_match fields
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fhir.resources.encounter import Encounter
from fhir.resources.medicationstatement import MedicationStatement
from fhir.resources.patient import Patient

from app.core.fhir.models import (
    EncounterModel,
    FHIRValidationError,
    MedicationStatementModel,
    PatientModel,
    PatientResolutionMethod,
)

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "fhir_r4"


def load_fixture(filename: str) -> dict:
    """Load FHIR R4 JSON fixture."""
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)


def test_patient_model_from_valid_fhir():
    """Test PatientModel with valid FHIR Patient (AC Scenario 1)."""
    fhir_json = load_fixture("patient_valid.json")
    fhir_patient = Patient(**fhir_json)
    patient_model = PatientModel.from_fhir(fhir_patient)

    assert patient_model.id == "patient-001"
    assert patient_model.mrn == "MRN-001"
    assert patient_model.family_name == "Smith"
    assert patient_model.given_name == "John"
    assert patient_model.gender == "male"
    assert str(patient_model.birth_date) == "1980-01-01"
    assert patient_model.phone == "555-1234"
    assert patient_model.email == "john.smith@example.com"
    assert patient_model.partial_match is False
    assert patient_model.resolution_method == PatientResolutionMethod.MRN


def test_patient_model_from_invalid_fhir():
    """Test PatientModel raises FHIRValidationError on invalid resource (AC Scenario 4)."""
    fhir_json = load_fixture("patient_invalid.json")
    fhir_patient = Patient(**fhir_json)

    with pytest.raises(FHIRValidationError) as exc_info:
        PatientModel.from_fhir(fhir_patient)

    assert "name" in str(exc_info.value)
    assert exc_info.value.resource_type == "Patient"


def test_patient_model_partial_match_flag():
    """Test PatientModel partial_match field can be set."""
    fhir_json = load_fixture("patient_valid.json")
    fhir_patient = Patient(**fhir_json)
    patient_model = PatientModel.from_fhir(fhir_patient)

    # Simulate name+DOB resolution
    patient_model.resolution_method = PatientResolutionMethod.NAME_DOB
    patient_model.partial_match = True

    assert patient_model.partial_match is True
    assert patient_model.resolution_method == PatientResolutionMethod.NAME_DOB


def test_encounter_model_from_valid_fhir():
    """Test EncounterModel with valid FHIR Encounter."""
    fhir_json = load_fixture("encounter_valid.json")
    fhir_encounter = Encounter(**fhir_json)
    encounter_model = EncounterModel.from_fhir(fhir_encounter)

    assert encounter_model.id == "encounter-001"
    assert encounter_model.patient_id == "patient-001"
    assert encounter_model.status == "in-progress"
    assert encounter_model.class_code == "IMP"


def test_medication_statement_model_from_valid_fhir():
    """Test MedicationStatementModel with valid FHIR MedicationStatement."""
    fhir_json = load_fixture("medication_statement_valid.json")
    fhir_med_statement = MedicationStatement(**fhir_json)
    med_model = MedicationStatementModel.from_fhir(fhir_med_statement)

    assert med_model.id == "med-statement-001"
    assert med_model.patient_id == "patient-001"
    assert med_model.medication_display == "Metformin 500mg"
    assert med_model.medication_code == "197361"
    assert med_model.status == "active"
    assert med_model.dosage_text == "Take one tablet twice daily"


def test_fhir_validation_error_attributes():
    """Test FHIRValidationError includes resource_type, field_path, received_value."""
    exc = FHIRValidationError(
        "Missing required field",
        resource_type="Patient",
        field_path="name",
        received_value=None,
    )

    assert exc.resource_type == "Patient"
    assert exc.field_path == "name"
    assert exc.received_value is None
    assert "Patient.name" in str(exc)
