"""
DocumentationAgent — AI discharge summary generation.

Subscribes to GCP Pub/Sub `docs-agent-sub` subscription.
Processes A03 (discharge) and A02 (transfer) ADT events.
Generates structured discharge summaries via Vertex AI Gemini 1.5 Pro.
Timeout and template fallback logic is applied by the calling layer (TASK-005).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from langchain_google_vertexai import ChatVertexAI

from agents.base_agent import BaseAgent
from agents.documentation.completeness_validator import CompletenessValidator
from agents.documentation.fallback_renderer import TemplateFallbackRenderer
from agents.documentation.fhir_fetcher import FHIREncounterFetcher
from agents.documentation.patient_instructions_generator import PatientInstructionsGenerator
from agents.documentation.patient_instructions_translator import PatientInstructionsTranslator
from agents.documentation.prompt_renderer import PromptRenderer
from agents.documentation.schemas import DischargeSummarySchema, GenerationType

if TYPE_CHECKING:
    from db.repositories.document_repository import DocumentRepository
    from integrations.fhir_client import FHIRClient

logger = logging.getLogger(__name__)

# ADT event types this agent handles
_SUPPORTED_EVENT_TYPES: frozenset[str] = frozenset({"A03", "A02"})


class DocumentationAgent(BaseAgent):
    """
    AI Documentation Agent.

    Orchestrates: FHIR fetch → prompt render → Gemini structured output → Document DB write.

    Inherits:
        BaseAgent: Pub/Sub consumer, retry logic, DLQ forwarding, health endpoint (US-024).

    Args:
        fhir_client: Async FHIR R4 HTTP client (US-017).
        document_repository: Document ORM repository (US-006).
        project_id: GCP project ID for Vertex AI.
        location: GCP region for Vertex AI endpoint (e.g. 'us-central1').
    """

    SUBSCRIPTION_ID = "docs-agent-sub"

    def __init__(
        self,
        fhir_client: "FHIRClient",
        document_repository: "DocumentRepository",
        project_id: str,
        location: str = "us-central1",
    ) -> None:
        super().__init__(subscription_id=self.SUBSCRIPTION_ID)

        self._fetcher = FHIREncounterFetcher(fhir_client)
        self._renderer = PromptRenderer()
        self._fallback_renderer = TemplateFallbackRenderer()
        self._doc_repo = document_repository

        # Completeness validator — instantiated once at agent startup
        # Reads YAML config and caches required fields list for agent lifetime (US-026)
        self._completeness_validator = CompletenessValidator()

        # Patient instructions generator and translator (US-027)
        self._instructions_generator = PatientInstructionsGenerator(
            project_id=project_id, location=location
        )
        self._instructions_translator = PatientInstructionsTranslator(
            project_id=project_id, location=location
        )

        # LangChain Vertex AI Gemini 1.5 Pro
        # response_mime_type="application/json" enables structured JSON output mode
        self._llm = ChatVertexAI(
            model_name="gemini-1.5-pro",
            project=project_id,
            location=location,
            temperature=0.1,        # Low temperature for deterministic clinical content
            max_output_tokens=4096,
            streaming=True,         # Incremental token delivery reduces perceived latency (TR-004)
            model_kwargs={
                "generation_config": {
                    "response_mime_type": "application/json",
                }
            },
        )

        # LangChain chain: structured output enforces DischargeSummarySchema
        self._chain = self._llm.with_structured_output(DischargeSummarySchema)

    # -------------------------------------------------------------------------
    # BaseAgent interface
    # -------------------------------------------------------------------------

    def can_handle(self, event_type: str) -> bool:
        """Returns True for A03 (discharge) and A02 (transfer) ADT events."""
        return event_type in _SUPPORTED_EVENT_TYPES

    async def process(self, event: dict) -> None:
        """
        Main processing entry point called by BaseAgent on each Pub/Sub message.

        Args:
            event: Deserialised ADT event dict with keys:
                   `event_type` (str), `encounter_id` (str), `occurred_at` (str).

        Raises:
            Does NOT raise — all errors are caught, logged, and the message is
            nacked to trigger Pub/Sub retry / DLQ forwarding via BaseAgent.
        """
        encounter_id: str = event["encounter_id"]
        event_type: str = event["event_type"]

        logger.info(
            "DocumentationAgent processing event",
            extra={"encounter_id": encounter_id, "event_type": event_type},
        )

        # Step 1: Fetch PHI-minimised FHIR encounter context
        encounter_context = await self._fetcher.fetch(encounter_id)

        # Step 2: Render Jinja2 prompt
        prompt_text = self._renderer.render_discharge_summary(encounter_context)

        # Step 3: Invoke Gemini 1.5 Pro with 25-second timeout
        start_ms = time.monotonic_ns() // 1_000_000
        try:
            summary: DischargeSummarySchema = await asyncio.wait_for(
                self._chain.ainvoke(prompt_text),
                timeout=25.0,  # TR-004: 25s API timeout, 2s buffer before 28s fallback trigger
            )
            summary.generation_type = GenerationType.AI

        except asyncio.TimeoutError:
            # 28-second boundary: AI timed out — fall back to deterministic template rendering
            logger.warning(
                "Gemini API timeout — activating template fallback",
                extra={"encounter_id": encounter_id, "timeout_seconds": 25},
            )
            summary = self._fallback_renderer.render(encounter_context)

        except Exception as exc:
            # Unexpected LLM error — fall back rather than losing the document
            logger.error(
                "Gemini API error — activating template fallback",
                extra={"encounter_id": encounter_id, "error": str(exc)},
                exc_info=True,
            )
            summary = self._fallback_renderer.render(encounter_context)

        summary.generation_duration_ms = (time.monotonic_ns() // 1_000_000) - start_ms

        # Step 4: Persist Document record with status=PENDING_REVIEW (TASK-006)
        document = await self._doc_repo.create_discharge_document(
            encounter_id=encounter_id,
            summary=summary,
        )

        # Step 5: Run completeness validation (US-026 TASK-004)
        result = self._completeness_validator.validate(summary.model_dump())

        # Step 6: Persist validation result; status reverted to DRAFT if INCOMPLETE (US-026 TASK-004)
        document = await self._doc_repo.update_completeness(document=document, result=result)

        logger.info(
            "Discharge summary generated, persisted, and validated",
            extra={
                "encounter_id": encounter_id,
                "generation_type": summary.generation_type.value,
                "duration_ms": summary.generation_duration_ms,
                "completeness_status": document.completeness_status,
                "missing_fields": document.missing_fields,
                "document_status": document.status,
            },
        )

        # Step 7: Generate and persist patient instructions (US-027)
        # Runs after discharge summary is committed; failures are isolated
        await self._generate_patient_instructions(
            document_id=document.id,
            discharge_summary=summary,
            encounter_context=encounter_context,
        )

    async def _generate_patient_instructions(
        self,
        document_id: int,
        discharge_summary: DischargeSummarySchema,
        encounter_context: dict,
    ) -> None:
        """
        Generate and persist patient instructions (US-027).

        Designed to be called after the discharge summary Document record is committed.
        Failures are caught and logged — they do not propagate to the Pub/Sub consumer
        to avoid nacking the event and causing retry storms.

        Args:
            document_id: PK of the newly-created Document record.
            discharge_summary: Structured discharge summary from US-025 pipeline.
            encounter_context: FHIR encounter context dict from FHIREncounterFetcher.
        """
        try:
            # Step 1: Generate English instructions with FK enforcement
            instructions_doc = await self._instructions_generator.generate(
                discharge_summary=discharge_summary,
                fhir_patient=encounter_context.get("patient", {}),
            )

            # Step 2: Translate into 4 non-English languages with quality check
            instructions_doc = await self._instructions_translator.translate_all(
                instructions_doc
            )

            # Step 3: Persist to Document.translations and Document.metadata
            await self._doc_repo.save_patient_instructions(
                document_id=document_id,
                instructions_doc=instructions_doc,
            )

            logger.info(
                "Patient instructions generated and saved for document %d "
                "(primary_lang=%s, fallback=%s, fk_grade=%.2f).",
                document_id,
                instructions_doc.primary_language,
                instructions_doc.language_fallback,
                instructions_doc.primary_flesch_kincaid_grade,
            )

        except Exception:
            logger.exception(
                "Patient instructions generation failed for document %d — "
                "discharge summary record is unaffected.",
                document_id,
            )
