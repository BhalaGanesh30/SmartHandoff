"""Patient portal API router.

Provides read-only endpoints scoped to the authenticated patient's own data.
All routes enforce:
  1. `patient` role JWT claim (403 for any other role)
  2. Encounter ownership check (patient may only access their own encounters)
  3. Document APPROVED-only filter (PENDING_REVIEW / DRAFT / REJECTED silently excluded)

US-029 Scenario 3: GET /api/v1/portal/documents?encounter_id={id}
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import get_current_patient_user
from app.db.deps import get_read_db
from app.models.document import Document
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.schemas.document_schemas import DocumentResponse, DocumentStatus

router = APIRouter(prefix="/portal", tags=["Patient Portal"])


@router.get(
    "/documents",
    summary="Return APPROVED documents for an encounter — patient portal (US-029 Scenario 3)",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_200_OK,
)
async def get_portal_documents(
    encounter_id: UUID = Query(..., description="Encounter UUID to retrieve documents for."),
    db: Annotated[AsyncSession, Depends(get_read_db)] = None,
    current_patient: Annotated[Patient, Depends(get_current_patient_user)] = None,
) -> list[DocumentResponse]:
    """
    Return only APPROVED documents for the given encounter.

    US-029 Scenario 3: documents with status PENDING_REVIEW, DRAFT, or REJECTED
    are silently excluded. Returns an empty list (not 404) when no approved
    documents exist yet.

    Ownership check: the authenticated patient must be the subject of the encounter.
    Returns 403 if the encounter belongs to a different patient.

    Args:
        encounter_id: UUID of the encounter to retrieve documents for.
        db: Read-replica database session (injected via dependency).
        current_patient: Patient entity from JWT validation.

    Returns:
        List of DocumentResponse objects for APPROVED documents only.

    Raises:
        HTTPException 404: If the encounter does not exist.
        HTTPException 403: If the encounter does not belong to the authenticated patient.
    """
    # ── Ownership check: patient may only read their own encounter ─────────────
    encounter: Encounter | None = await db.get(Encounter, encounter_id)
    if encounter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encounter {encounter_id} not found.",
        )
    if encounter.patient_id != current_patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: encounter does not belong to the authenticated patient.",
        )

    # ── APPROVED-only document query (US-029 Scenario 3) ─────────────────────
    stmt = (
        select(Document)
        .where(Document.encounter_id == encounter_id)
        .where(Document.status == DocumentStatus.APPROVED.value)  # hard filter — no override
        .order_by(Document.updated_at.desc())
    )
    result = await db.execute(stmt)
    documents: list[Document] = list(result.scalars().all())

    return [DocumentResponse.model_validate(doc) for doc in documents]
