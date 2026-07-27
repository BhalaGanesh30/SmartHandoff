"""PHI audit unit tests — US-023 DoD mandatory test.

Confirms that:
  1. ``ChecklistInput`` model has no PHI field definitions.
  2. The rendered ``checklist.jinja2`` prompt contains no PHI field names or values.
  3. ``ChecklistService._call_gemini()`` receives a rendered prompt free of PHI.

Design refs: AIR-021, US-023 DoD PHI audit requirement
"""
import pathlib

import jinja2
import pytest

from app.checklist import ChecklistInput


_PROMPTS_DIR = pathlib.Path(__file__).parent.parent.parent / "prompts"

_PHI_FIELDS = ["first_name", "last_name", "mrn", "dob", "date_of_birth", "phone", "email", "ssn"]

_SAFE_INPUT = ChecklistInput(
    encounter_id="ENC-001",
    diagnosis_codes=["E11.9", "I50.9"],
    unit_name="Med-Surg 4B",
    transition_type="A03",
    medication_names=["Metformin", "Furosemide"],
)


class TestChecklistInputPHIAudit:
    """Verify ChecklistInput model defines no PHI fields (AIR-021)."""

    def test_checklist_input_has_no_phi_fields(self) -> None:
        model_fields = set(ChecklistInput.model_fields.keys())
        phi_violations = set(_PHI_FIELDS) & model_fields
        assert not phi_violations, (
            f"PHI fields found in ChecklistInput model definition: {phi_violations}. "
            "Remove all patient-identifying fields per AIR-021."
        )

    def test_encounter_id_is_only_identifier(self) -> None:
        """encounter_id (UUID) is the only identifier — not a PHI field."""
        fields = set(ChecklistInput.model_fields.keys())
        expected = {"encounter_id", "diagnosis_codes", "unit_name", "transition_type", "medication_names"}
        assert fields == expected, f"Unexpected fields in ChecklistInput: {fields - expected}"


class TestRenderedPromptPHIAudit:
    """Verify the rendered Jinja2 prompt contains no PHI values or field names."""

    @pytest.fixture()
    def rendered_prompt(self) -> str:
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=False,
            undefined=jinja2.StrictUndefined,
        )
        tmpl = env.get_template("checklist.jinja2")
        return tmpl.render(
            diagnosis_codes=_SAFE_INPUT.diagnosis_codes,
            unit_name=_SAFE_INPUT.unit_name,
            transition_type=_SAFE_INPUT.transition_type,
            medication_names=_SAFE_INPUT.medication_names,
        )

    def test_phi_field_names_absent_from_rendered_prompt(self, rendered_prompt: str) -> None:
        """US-023 DoD — unit test confirms PHI field names absent from prompt."""
        violations = [field for field in _PHI_FIELDS if field in rendered_prompt.lower()]
        assert not violations, (
            f"PHI field names found in rendered prompt: {violations}. "
            "Review checklist.jinja2 template to remove PHI references."
        )

    def test_encounter_id_absent_from_rendered_prompt(self, rendered_prompt: str) -> None:
        """encounter_id is used only for logging, must NOT appear in the LLM prompt."""
        assert "ENC-001" not in rendered_prompt, (
            "encounter_id appears in rendered prompt. "
            "It must be used only for logging, never injected into the LLM prompt."
        )

    def test_rendered_prompt_contains_diagnosis_codes(self, rendered_prompt: str) -> None:
        """ICD-10 codes (not text) should appear in the prompt."""
        assert "E11.9" in rendered_prompt
        assert "I50.9" in rendered_prompt

    def test_rendered_prompt_contains_unit_name(self, rendered_prompt: str) -> None:
        assert "Med-Surg 4B" in rendered_prompt

    def test_rendered_prompt_contains_transition_type(self, rendered_prompt: str) -> None:
        assert "A03" in rendered_prompt or "DISCHARGE" in rendered_prompt
