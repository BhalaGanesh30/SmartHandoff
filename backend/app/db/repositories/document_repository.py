"""
DocumentRepository — async ORM repository for Document records.

Implements create, read, and status-transition operations for the Document
entity. All PHI content is encrypted at the ORM layer via EncryptedText
before database write (DR-013, US-007).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from agents.documentation.completeness_validator import CompletenessResult, CompletenessStatus
from agents.documentation.schemas import DischargeSummarySchema
from app.signalr import SignalRHub

if TYPE_CHECKING:
    from agents.documentation.patient_instructions_schemas import PatientInstructionsDocument

logger = logging.getLogger(__name__)


class DocumentRepository:
    """
    Async repository for Document ORM operations.

    Args:
        session: SQLAlchemy AsyncSession (injected per-request/per-event).
        signalr_hub: SignalR hub client for real-time UI push notifications.
    """

    def __init__(self, session: AsyncSession, signalr_hub: SignalRHub) -> None:
        self._session = session
        self._signalr = signalr_hub

    async def create_discharge_document(
        self,
        encounter_id: str,
        summary: DischargeSummarySchema,
    ) -> Document:
        """
        Persist an AI-generated or template-generated discharge summary as a
        Document ORM record with status=PENDING_APPROVAL.

        The summary JSON is stored encrypted via EncryptedText (AES-256-GCM).
        After a successful commit, a SignalR push is sent to the encounter group.

        Args:
            encounter_id: The FHIR/internal encounter identifier.
            summary: Validated DischargeSummarySchema (AI or template-generated).

        Returns:
            The persisted Document ORM instance.

        Raises:
            SQLAlchemyError: Propagated on DB write failure (caller handles retry via BaseAgent).
        """
        # Serialize summary to JSON; EncryptedText handles AES-256-GCM encryption at ORM layer
        summary_json = summary.model_dump_json()

        document = Document(
            encounter_id=encounter_id,
            document_type="discharge_summary",
            status=DocumentStatus.PENDING_APPROVAL.value,          # US-025 AC Scenario 1 & 2
            generation_type=summary.generation_type.value,          # "AI" or "TEMPLATE"
            content=summary_json,                                   # Encrypted by EncryptedText column
            ai_assisted_label=True,                                 # US-029 — permanent provenance flag
            approved_at=None,
            reviewed_by_user_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self._session.add(document)
        await self._session.commit()
        await self._session.refresh(document)

        logger.info(
            "Document record created",
            extra={
                "document_id": str(document.id),
                "encounter_id": encounter_id,
                "status": document.status,
                "generation_type": document.generation_type,
            },
        )

        # Real-time push: notify physician dashboard that summary is ready for review
        await self._signalr.send_to_group(
            group=f"encounter-{encounter_id}",
            event="DocumentReady",
            payload={
                "document_id": str(document.id),
                "document_type": "discharge_summary",
                "status": DocumentStatus.PENDING_APPROVAL.value,
                "generation_type": document.generation_type,
            },
        )

        return document

    async def update_completeness(
        self,
        document: Document,
        result: CompletenessResult,
    ) -> Document:
        """
        Persist the CompletenessValidator result onto an existing Document row.

        Sets:
          - document.completeness_status to result.status.value ("COMPLETE" or "INCOMPLETE")
          - document.missing_fields to result.missing_fields
          - document.status remains PENDING_APPROVAL if COMPLETE;
            reverted to DRAFT if INCOMPLETE (US-026 Scenario 2)

        Args:
            document: The Document ORM instance returned by create_discharge_document().
            result:   CompletenessResult from CompletenessValidator.validate().

        Returns:
            Updated Document instance after commit.
        """
        document.completeness_status = result.status.value
        document.missing_fields = result.missing_fields

        if result.status == CompletenessStatus.INCOMPLETE:
            # Hold the document in DRAFT — not visible in the physician review queue
            document.status = DocumentStatus.DRAFT.value

        self._session.add(document)
        await self._session.commit()
        await self._session.refresh(document)

        logger.info(
            "DocumentRepository.update_completeness: document_id=%s completeness_status=%s missing_fields=%s",
            document.id,
            document.completeness_status,
            document.missing_fields,
        )
        return document

    async def get_review_queue(self, limit: int = 50, offset: int = 0) -> list[Document]:
        """
        Return documents ready for physician review.

        Filters:
          - status = PENDING_APPROVAL
          - completeness_status = COMPLETE   ← US-026: exclude INCOMPLETE documents

        Args:
            limit: Maximum number of records to return (pagination).
            offset: Number of records to skip (pagination).

        Returns:
            List of Document ORM instances ready for physician review.
        """
        result = await self._session.execute(
            select(Document)
            .where(
                Document.status == DocumentStatus.PENDING_APPROVAL.value,
                Document.completeness_status == "COMPLETE",  # US-026
            )
            .order_by(Document.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_encounter(self, encounter_id: str) -> list[Document]:
        """
        Get all documents for a specific encounter.

        Args:
            encounter_id: The encounter identifier.

        Returns:
            List of Document ORM instances for the encounter.
        """
        result = await self._session.execute(
            select(Document)
            .where(Document.encounter_id == encounter_id)
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def save_patient_instructions(
        self,
        document_id: int,
        instructions_doc: PatientInstructionsDocument,
    ) -> None:
        """
        Persist patient instructions translations and language metadata to the Document record.

        Updates `translations` JSONB and `metadata` JSONB fields on the existing Document.
        The Document record must already exist (created by DocumentationAgent, US-025).

        Args:
            document_id: Primary key of the existing Document record.
            instructions_doc: Fully-populated PatientInstructionsDocument from TASK-003/TASK-004.

        Raises:
            ValueError: If the Document record does not exist.
        """
        document = await self._session.get(Document, document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found.")

        document.translations = instructions_doc.translations_as_dict()
        document.document_metadata = {
            "language_fallback": instructions_doc.language_fallback,
            "requested_language": instructions_doc.requested_language,
            "primary_language": instructions_doc.primary_language,
            "primary_fk_grade": instructions_doc.primary_flesch_kincaid_grade,
        }

        self._session.add(document)
        await self._session.commit()
        await self._session.refresh(document)

        logger.info(
            "Patient instructions saved for document %s (primary_lang=%s, fallback=%s).",
            document_id,
            instructions_doc.primary_language,
            instructions_doc.language_fallback,
        )
