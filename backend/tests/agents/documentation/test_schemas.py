import pytest
from pydantic import ValidationError
from agents.documentation.schemas import DischargeSummarySchema, GenerationType


MINIMAL_VALID_PAYLOAD = {
    "encounter_id": "ENC-001",
    "diagnosis_summary": [{"icd10_code": "E11.9", "description": "Type 2 diabetes", "is_primary": True}],
    "procedures": [],
    "medications_at_discharge": [
        {"drug_name": "metformin", "dose": "500 mg", "frequency": "twice daily", "route": "oral"}
    ],
    "follow_up_instructions": [{"instruction": "Follow up with PCP within 7 days"}],
    "warning_signs": ["Shortness of breath", "Chest pain"],
    "activity_restrictions": ["No heavy lifting for 4 weeks"],
}


def test_valid_schema_parses_successfully():
    schema = DischargeSummarySchema(**MINIMAL_VALID_PAYLOAD)
    assert schema.encounter_id == "ENC-001"
    assert schema.generation_type == GenerationType.AI


def test_missing_mandatory_section_raises_validation_error():
    payload = {**MINIMAL_VALID_PAYLOAD}
    del payload["warning_signs"]
    with pytest.raises(ValidationError):
        DischargeSummarySchema(**payload)


def test_empty_mandatory_list_raises_validation_error():
    payload = {**MINIMAL_VALID_PAYLOAD, "medications_at_discharge": []}
    with pytest.raises(ValidationError):
        DischargeSummarySchema(**payload)


def test_generation_type_template_sets_correctly():
    payload = {**MINIMAL_VALID_PAYLOAD, "generation_type": "TEMPLATE"}
    schema = DischargeSummarySchema(**payload)
    assert schema.generation_type == GenerationType.TEMPLATE
