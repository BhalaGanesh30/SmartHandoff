import pytest
from agents.documentation.fhir_fetcher import (
    EncounterContext, DiagnosisContext, MedicationContext,
)
from agents.documentation.prompt_renderer import PromptRenderer

PHI_STRINGS = ["John", "Doe", "123 Main St", "555-1234", "123-45-6789", "01/01/1960"]


@pytest.fixture
def sample_context():
    return EncounterContext(
        encounter_id="ENC-001",
        admission_reason="Acute heart failure exacerbation",
        encounter_type="inpatient",
        discharge_disposition="Home",
        length_of_stay_days=4,
        diagnoses=[DiagnosisContext(icd10_code="I50.9", description="Heart failure, unspecified", is_primary=True)],
        medications=[MedicationContext(drug_name="lisinopril", dose="10 mg", frequency="once daily", route="oral", rxnorm_code="29046")],
    )


def test_rendered_prompt_contains_encounter_id(sample_context):
    renderer = PromptRenderer()
    prompt = renderer.render_discharge_summary(sample_context)
    assert "ENC-001" in prompt


def test_rendered_prompt_contains_icd10_code(sample_context):
    renderer = PromptRenderer()
    prompt = renderer.render_discharge_summary(sample_context)
    assert "I50.9" in prompt


def test_rendered_prompt_contains_no_phi(sample_context):
    renderer = PromptRenderer()
    prompt = renderer.render_discharge_summary(sample_context)
    for phi_value in PHI_STRINGS:
        assert phi_value not in prompt, f"PHI string '{phi_value}' found in rendered prompt"


def test_rendered_prompt_contains_all_required_sections_instructions(sample_context):
    renderer = PromptRenderer()
    prompt = renderer.render_discharge_summary(sample_context)
    required_section_mentions = [
        "diagnosis_summary", "medications_at_discharge",
        "follow_up_instructions", "warning_signs", "activity_restrictions",
    ]
    for section in required_section_mentions:
        assert section in prompt, f"Section '{section}' not referenced in prompt template"
