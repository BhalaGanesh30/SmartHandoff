"""ChecklistService — orchestrates AI-generated handoff checklist via Vertex AI Gemini.

Responsibilities:
  1. Render ``prompts/checklist.jinja2`` with minimum-necessary clinical context.
  2. Call Vertex AI Gemini with ``response_schema`` for structured JSON output.
  3. Enforce 15-second timeout; fall back to ``config/checklist_templates.yaml`` on expiry.
  4. Return a validated ``HandoffChecklist`` with ``generated_type`` set appropriately.

PHI policy (AIR-021):
  ``ChecklistInput`` accepts only ICD-10 diagnosis codes, generic medication names,
  unit name, and transition type. Patient-identifying fields (name, MRN, DOB, phone)
  are explicitly excluded from both the input model and the rendered prompt.

Environment variables:
  GOOGLE_CLOUD_PROJECT      — GCP project ID for Vertex AI
  VERTEX_AI_LOCATION        — Vertex AI region (default: us-central1)
  GEMINI_MODEL_ID           — Gemini model identifier (default: gemini-1.5-pro)
  CHECKLIST_LLM_TIMEOUT_SEC — LLM call timeout in seconds (default: 15)

Design refs:
    ADR-004, TR-004, AIR-020, AIR-021, US-023 DoD, AC Scenarios 1–4
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
from typing import Annotated

import jinja2
import yaml
from pydantic import BaseModel, Field

from app.models.handoff_checklist import ChecklistItem, HandoffChecklist

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_SEC: int = 15
_DEFAULT_GEMINI_MODEL: str = "gemini-1.5-pro"
_DEFAULT_VERTEX_LOCATION: str = "us-central1"

_SERVICE_ROOT = pathlib.Path(__file__).parent.parent.parent  # coordinator-agent/
_PROMPTS_DIR = _SERVICE_ROOT / "prompts"
_TEMPLATES_PATH = _SERVICE_ROOT / "config" / "checklist_templates.yaml"

# ADT event_type → YAML key mapping
_TRANSITION_KEY_MAP: dict[str, str] = {
    "A01": "A01",
    "A02": "A02",
    "A03": "A03",
}

# ---------------------------------------------------------------------------
# ChecklistInput — PHI-safe input model
# ---------------------------------------------------------------------------


class ChecklistInput(BaseModel):
    """Minimum-necessary clinical context for checklist generation.

    PHI policy (AIR-021):
        This model intentionally omits patient-identifying fields.
        DO NOT add: patient_name, first_name, last_name, mrn, dob, phone, email.

    Attributes:
        encounter_id:      Encounter UUID — used only for logging/tracing, not injected into LLM prompt.
        diagnosis_codes:   ICD-10 codes (e.g. ``["E11.9", "I50.9"]``).
        unit_name:         Care unit name (e.g. ``"ICU"``).
        transition_type:   ADT code (e.g. ``"A03"``).
        medication_names:  Generic drug names only (e.g. ``["Metformin", "Furosemide"]``).
    """

    encounter_id: Annotated[
        str,
        Field(description="Encounter UUID for audit logging (not injected into LLM prompt)."),
    ]
    diagnosis_codes: Annotated[
        list[str],
        Field(min_length=1, description="ICD-10 diagnosis codes."),
    ]
    unit_name: Annotated[
        str,
        Field(min_length=2, max_length=100, description="Care unit name."),
    ]
    transition_type: Annotated[
        str,
        Field(min_length=3, max_length=10, description="ADT event code (A01/A02/A03)."),
    ]
    medication_names: list[str] = Field(
        default_factory=list,
        description="Generic medication names — no PHI.",
    )


# ---------------------------------------------------------------------------
# ChecklistService
# ---------------------------------------------------------------------------


class ChecklistService:
    """Generates a ``HandoffChecklist`` via Vertex AI Gemini or template fallback.

    Args:
        project_id:   GCP project ID. Defaults to ``GOOGLE_CLOUD_PROJECT`` env var.
        location:     Vertex AI region. Defaults to ``VERTEX_AI_LOCATION`` env var or ``us-central1``.
        model_id:     Gemini model ID. Defaults to ``GEMINI_MODEL_ID`` env var or ``gemini-1.5-pro``.
        timeout_sec:  LLM call timeout in seconds. Defaults to ``CHECKLIST_LLM_TIMEOUT_SEC`` env var or 15.

    Example::

        service = ChecklistService()
        checklist = await service.generate(
            ChecklistInput(
                encounter_id="ENC-001",
                diagnosis_codes=["E11.9", "I50.9"],
                unit_name="Med-Surg 4B",
                transition_type="A03",
                medication_names=["Metformin", "Furosemide"],
            )
        )
        assert checklist.generated_type in ("LLM", "TEMPLATE")
    """

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        model_id: str | None = None,
        timeout_sec: int | None = None,
    ) -> None:
        self._project_id = project_id or os.environ["GOOGLE_CLOUD_PROJECT"]
        self._location = location or os.environ.get("VERTEX_AI_LOCATION", _DEFAULT_VERTEX_LOCATION)
        self._model_id = model_id or os.environ.get("GEMINI_MODEL_ID", _DEFAULT_GEMINI_MODEL)
        self._timeout_sec = int(
            timeout_sec or os.environ.get("CHECKLIST_LLM_TIMEOUT_SEC", _DEFAULT_TIMEOUT_SEC)
        )

        # Load Jinja2 template once at init — not on every call
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=False,  # Clinical text — no HTML escaping needed
            undefined=jinja2.StrictUndefined,  # Fail fast on missing variables
        )
        self._prompt_template = self._jinja_env.get_template("checklist.jinja2")

        # Load YAML fallback templates once at init
        self._fallback_templates: dict[str, list[dict]] = yaml.safe_load(
            _TEMPLATES_PATH.read_text()
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(self, context: ChecklistInput) -> HandoffChecklist:
        """Generate a handoff checklist for the given clinical context.

        Attempts a Vertex AI Gemini structured-output call. If the call does
        not complete within ``timeout_sec`` seconds, falls back to the
        pre-defined YAML template for the given ``transition_type``.

        Args:
            context: ``ChecklistInput`` with ICD-10 codes, unit, transition type.
                     Must NOT contain PHI fields (enforced by model definition).

        Returns:
            ``HandoffChecklist`` with ``generated_type="LLM"`` on success, or
            ``generated_type="TEMPLATE"`` on timeout/fallback.
        """
        try:
            checklist = await asyncio.wait_for(
                self._call_gemini(context),
                timeout=self._timeout_sec,
            )
            logger.info(
                "checklist_generated_llm",
                extra={
                    "encounter_id": context.encounter_id,
                    "transition_type": context.transition_type,
                    "item_count": len(checklist.checklist),
                },
            )
            return checklist

        except asyncio.TimeoutError:
            logger.warning(
                "checklist_llm_timeout_fallback",
                extra={
                    "encounter_id": context.encounter_id,
                    "transition_type": context.transition_type,
                    "timeout_sec": self._timeout_sec,
                },
            )
            return self._load_template_fallback(context)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "checklist_llm_error_fallback",
                extra={
                    "encounter_id": context.encounter_id,
                    "transition_type": context.transition_type,
                    "error": str(exc),
                },
            )
            return self._load_template_fallback(context)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _call_gemini(self, context: ChecklistInput) -> HandoffChecklist:
        """Render prompt and call Vertex AI Gemini with structured output schema.

        Args:
            context: Validated ``ChecklistInput`` — no PHI fields.

        Returns:
            ``HandoffChecklist`` parsed from Gemini structured JSON response.

        Raises:
            Exception: Any Vertex AI / network exception propagates to caller
                       for fallback handling in ``generate()``.
        """
        # Lazy import — avoids load penalty when service is not used
        import vertexai  # type: ignore[import]
        from vertexai.generative_models import GenerativeModel, GenerationConfig  # type: ignore[import]

        prompt_text = self._prompt_template.render(
            diagnosis_codes=context.diagnosis_codes,
            unit_name=context.unit_name,
            transition_type=context.transition_type,
            medication_names=context.medication_names,
        )

        # Initialise Vertex AI (idempotent — safe to call multiple times)
        vertexai.init(project=self._project_id, location=self._location)

        model = GenerativeModel(self._model_id)
        response_schema = HandoffChecklist.llm_response_schema()

        # Run synchronous Vertex AI call in thread pool to avoid blocking event loop
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                prompt_text,
                generation_config=GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.3,  # Low temperature for clinical reliability
                    max_output_tokens=2048,
                ),
            ),
        )

        raw_json: dict = json.loads(response.text)
        checklist_items = [ChecklistItem(**item) for item in raw_json.get("checklist", [])]

        return HandoffChecklist(
            checklist=checklist_items,
            generated_type="LLM",
            transition_type=context.transition_type,
        )

    def _load_template_fallback(self, context: ChecklistInput) -> HandoffChecklist:
        """Load pre-defined checklist items from YAML for the given transition type.

        Args:
            context: ``ChecklistInput`` — only ``transition_type`` is used for lookup.

        Returns:
            ``HandoffChecklist`` with ``generated_type="TEMPLATE"``.
        """
        yaml_key = _TRANSITION_KEY_MAP.get(context.transition_type, "DEFAULT")
        raw_items: list[dict] = self._fallback_templates.get(
            yaml_key, self._fallback_templates["DEFAULT"]
        )
        checklist_items = [ChecklistItem(**item) for item in raw_items]

        return HandoffChecklist(
            checklist=checklist_items,
            generated_type="TEMPLATE",
            transition_type=context.transition_type,
        )
