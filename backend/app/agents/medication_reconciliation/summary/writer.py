"""Persists the generated MedicationSummaryOutput to the Document record.

Writes the summary into ``document.medications_section`` (JSONB) so that
the Documentation Agent can embed it in the patient discharge instructions.

Design refs:
    US-033 AC Scenario 3  — summary stored in Document.medications_section
    design.md §6          — Document table; JSONB content fields
    design.md §4.1        — SQLAlchemy 2.x async ORM; no N+1 writes
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.agents.medication_reconciliation.summary.schema import MedicationSummaryOutput

logger = logging.getLogger(__name__)


class MedicationSummaryWriter:
    """Writes a MedicationSummaryOutput to the Document record.

    Args:
        db: Async SQLAlchemy session (write session — primary DB).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def write(
        self,
        document_id: UUID,
        summary: MedicationSummaryOutput,
    ) -> None:
        """Persist the medication summary to the document record.

        Args:
            document_id: Primary key (UUID) of the ``Document`` record to update.
            summary: Validated ``MedicationSummaryOutput`` to store.

        Raises:
            ValueError: If no Document with ``document_id`` is found.
        """
        result = await self._db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise ValueError(
                f"Document id={document_id} not found — cannot write medications_section"
            )

        document.medications_section = summary.model_dump()
        await self._db.flush()
        logger.info(
            "medications_section written: document_id=%s categories=%s",
            document_id,
            list(summary.model_dump().keys()),
        )
