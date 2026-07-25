"""Unit tests for HandoffChecklist and ChecklistItem Pydantic models.

Coverage:
  - Valid model instantiation
  - Actionable-verb enforcement (model_validator)
  - Priority constraint (Literal type)
  - generated_type discriminator (LLM / TEMPLATE)
  - llm_response_schema() returns checklist definition
  - No PHI fields in model schema

Design refs: AIR-021, US-023 AC Scenarios 1, 2, 4
"""
import pytest
from pydantic import ValidationError

from app.models.handoff_checklist import ChecklistItem, HandoffChecklist


# ---------------------------------------------------------------------------
# ChecklistItem — valid construction
# ---------------------------------------------------------------------------


class TestChecklistItemValidConstruction:
    def test_valid_item_verify(self) -> None:
        item = ChecklistItem(
            item="Verify blood glucose monitoring plan",
            category="medications",
            priority="HIGH",
        )
        assert item.item.startswith("Verify")
        assert item.priority == "HIGH"

    def test_valid_item_confirm(self) -> None:
        item = ChecklistItem(
            item="Confirm diuretic dose adjustment per discharge orders",
            category="medications",
            priority="MEDIUM",
        )
        assert item.priority == "MEDIUM"

    @pytest.mark.parametrize(
        "verb",
        ["Verify", "Confirm", "Schedule", "Review", "Assess", "Ensure", "Notify"],
    )
    def test_all_actionable_verbs_accepted(self, verb: str) -> None:
        item = ChecklistItem(
            item=f"{verb} care plan updated before discharge",
            category="documentation",
            priority="LOW",
        )
        assert item.item.startswith(verb)


# ---------------------------------------------------------------------------
# ChecklistItem — invalid construction
# ---------------------------------------------------------------------------


class TestChecklistItemInvalidConstruction:
    def test_non_actionable_verb_raises(self) -> None:
        with pytest.raises(ValidationError, match="must begin with one of"):
            ChecklistItem(
                item="Patient should monitor blood glucose daily",
                category="medications",
                priority="HIGH",
            )

    def test_invalid_priority_raises(self) -> None:
        with pytest.raises(ValidationError):
            ChecklistItem(
                item="Verify labs reviewed",
                category="documentation",
                priority="CRITICAL",  # Not in Literal
            )

    def test_item_too_short_raises(self) -> None:
        with pytest.raises(ValidationError):
            ChecklistItem(item="Check", category="safety", priority="HIGH")


# ---------------------------------------------------------------------------
# HandoffChecklist — valid construction
# ---------------------------------------------------------------------------


class TestHandoffChecklistValid:
    def _make_checklist(
        self,
        count: int = 3,
        generated_type: str = "LLM",
        transition_type: str = "A03",
    ) -> HandoffChecklist:
        items = [
            ChecklistItem(
                item=f"Verify care item number {i} for patient",
                category="documentation",
                priority="MEDIUM",
            )
            for i in range(count)
        ]
        return HandoffChecklist(
            checklist=items,
            generated_type=generated_type,
            transition_type=transition_type,
        )

    def test_three_items_discharge_scenario(self) -> None:
        """US-023 AC Scenario 1 — discharge checklist contains ≥3 items."""
        checklist = self._make_checklist(count=3, transition_type="A03")
        assert len(checklist.checklist) >= 3

    def test_generated_type_llm(self) -> None:
        checklist = self._make_checklist(generated_type="LLM")
        assert checklist.generated_type == "LLM"

    def test_generated_type_template(self) -> None:
        """US-023 AC Scenario 4 — TEMPLATE discriminator accepted."""
        checklist = self._make_checklist(generated_type="TEMPLATE")
        assert checklist.generated_type == "TEMPLATE"

    def test_serialises_to_dict_with_required_keys(self) -> None:
        """US-023 AC Scenario 3 — checklist items serialise to dict with item/category/priority."""
        checklist = self._make_checklist()
        for item_dict in [i.model_dump() for i in checklist.checklist]:
            assert "item" in item_dict
            assert "category" in item_dict
            assert "priority" in item_dict


# ---------------------------------------------------------------------------
# HandoffChecklist — PHI schema audit (US-023 AC Scenario 2)
# ---------------------------------------------------------------------------


class TestHandoffChecklistPHIAudit:
    PHI_FIELDS = {"first_name", "last_name", "mrn", "dob", "phone", "email", "patient_name"}

    def test_handoff_checklist_schema_contains_no_phi_fields(self) -> None:
        """Ensure HandoffChecklist model schema exposes zero PHI field names."""
        schema_str = str(HandoffChecklist.model_json_schema())
        violations = [f for f in self.PHI_FIELDS if f in schema_str]
        assert not violations, f"PHI fields found in HandoffChecklist schema: {violations}"

    def test_checklist_item_schema_contains_no_phi_fields(self) -> None:
        schema_str = str(ChecklistItem.model_json_schema())
        violations = [f for f in self.PHI_FIELDS if f in schema_str]
        assert not violations, f"PHI fields found in ChecklistItem schema: {violations}"


# ---------------------------------------------------------------------------
# llm_response_schema()
# ---------------------------------------------------------------------------


class TestLlmResponseSchema:
    def test_returns_dict(self) -> None:
        schema = HandoffChecklist.llm_response_schema()
        assert isinstance(schema, dict)

    def test_schema_contains_checklist_definition(self) -> None:
        schema_str = str(HandoffChecklist.llm_response_schema())
        assert "checklist" in schema_str
