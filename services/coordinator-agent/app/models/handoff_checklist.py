"""Pydantic models for the AI-generated handoff checklist.

Defines the structured-output contract consumed by:
  - Vertex AI Gemini ``response_schema`` parameter (TASK-003)
  - ``AgentTask.metadata`` JSONB storage (TASK-004)
  - ``GET /api/v1/encounters/{id}/tasks`` response schema (TASK-004)

PHI policy (AIR-021):
  This module intentionally contains NO patient-identifying fields.
  The checklist is keyed by encounter context (diagnosis codes, unit, transition
  type) — never by patient name, MRN, DOB, or phone number.

Design refs:
    ADR-004  — LangChain + Vertex AI structured output
    AIR-020  — coordinator agent orchestration
    AIR-021  — minimum-necessary PHI in LLM prompts
    US-023   — Generate Context-Aware Handoff Checklist via LLM
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ACTIONABLE_VERBS: frozenset[str] = frozenset(
    {"verify", "confirm", "schedule", "review", "assess", "ensure", "notify"}
)

# ---------------------------------------------------------------------------
# ChecklistItem
# ---------------------------------------------------------------------------


class ChecklistItem(BaseModel):
    """A single actionable item within a handoff checklist.

    Attributes:
        item: Human-readable instruction beginning with an actionable verb.
        category: Clinical grouping (e.g. ``"medications"``, ``"follow_up"``,
            ``"patient_education"``, ``"equipment"``, ``"documentation"``).
        priority: Urgency level — ``HIGH`` must be addressed before handoff
            completes; ``MEDIUM`` within 4 hours; ``LOW`` within 24 hours.

    Example::

        ChecklistItem(
            item="Verify blood glucose monitoring plan for discharge",
            category="medications",
            priority="HIGH",
        )
    """

    item: Annotated[
        str,
        Field(
            min_length=10,
            max_length=300,
            description=(
                "Actionable instruction beginning with Verify, Confirm, Schedule, "
                "Review, Assess, Ensure, or Notify."
            ),
        ),
    ]
    category: Annotated[
        str,
        Field(
            min_length=2,
            max_length=50,
            description="Clinical category grouping this checklist item.",
        ),
    ]
    priority: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        description="Urgency classification for this checklist item."
    )

    @model_validator(mode="after")
    def _item_starts_with_actionable_verb(self) -> "ChecklistItem":
        """Ensure ``item`` text opens with a recognised clinical action verb."""
        first_word = self.item.split()[0].lower().rstrip(".,:")
        if first_word not in _ACTIONABLE_VERBS:
            raise ValueError(
                f"ChecklistItem.item must begin with one of "
                f"{sorted(_ACTIONABLE_VERBS)!r}. Got first word: {first_word!r}"
            )
        return self


# ---------------------------------------------------------------------------
# HandoffChecklist
# ---------------------------------------------------------------------------


class HandoffChecklist(BaseModel):
    """Structured handoff checklist returned by the coordinator checklist service.

    This is the top-level container used as:
      - The ``response_schema`` passed to Vertex AI Gemini (TASK-003)
      - The value stored in ``AgentTask.metadata["checklist"]`` (TASK-004)

    Attributes:
        checklist: Ordered list of actionable checklist items. Must contain
            at least 1 item; LLM-generated checklists are expected to return ≥3
            patient-specific items (US-023 AC Scenario 1).
        generated_type: Source of the checklist. ``"LLM"`` when produced by
            Vertex AI Gemini; ``"TEMPLATE"`` when the 15-second timeout fired
            and the pre-defined fallback was used (AC Scenario 4).
        transition_type: ADT transition code (e.g. ``"A03"`` discharge,
            ``"A02"`` transfer). Stored for audit traceability.

    Example::

        checklist = HandoffChecklist(
            checklist=[
                ChecklistItem(item="Verify blood glucose monitoring plan", category="medications", priority="HIGH"),
                ChecklistItem(item="Confirm diuretic dose adjustment per discharge orders", category="medications", priority="HIGH"),
                ChecklistItem(item="Schedule follow-up with cardiologist within 7 days", category="follow_up", priority="MEDIUM"),
            ],
            generated_type="LLM",
            transition_type="A03",
        )
    """

    checklist: Annotated[
        list[ChecklistItem],
        Field(min_length=1, description="Ordered list of actionable handoff items."),
    ]
    generated_type: Literal["LLM", "TEMPLATE"] = Field(
        description="Source of checklist generation — LLM or template fallback."
    )
    transition_type: Annotated[
        str,
        Field(
            min_length=3,
            max_length=10,
            description="ADT transition code (e.g. A03, A02, A01).",
        ),
    ]

    @classmethod
    def llm_response_schema(cls) -> dict:
        """Return the JSON schema dict to pass as ``response_schema`` to Gemini.

        Usage in TASK-003::

            from app.models.handoff_checklist import HandoffChecklist

            response = await gemini_client.generate(
                prompt=rendered_prompt,
                response_schema=HandoffChecklist.llm_response_schema(),
            )

        Returns:
            JSON Schema dict representing the ``HandoffChecklist`` structure,
            scoped to the ``checklist`` array (Gemini structured-output contract).
        """
        schema = cls.model_json_schema()
        # Gemini response_schema expects the checklist array definition directly
        return schema
