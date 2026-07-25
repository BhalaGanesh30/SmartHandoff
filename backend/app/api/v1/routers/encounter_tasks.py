"""Router: GET /api/v1/encounters/{encounter_id}/tasks

Returns all AgentTask records for a given encounter with SLA fields.

Security: requires valid JWT via get_current_user dependency (EP-011).
DB: reads from replica session (TR-010) — no write operations.

US-021 Scenario 2: Returns tasks with id, agent_type, status, start_time,
completed_time, sla_threshold_minutes, sla_breached.
"""
from __future__ import annotations

import logging
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.jwt import TokenClaims, get_current_user
from app.db.deps import get_read_db
from app.models.agent_task import AgentTask
from app.models.document import Document
from app.models.encounter import Encounter
from app.schemas.agent_task import AgentTaskListResponse, AgentTaskResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/encounters", tags=["encounters", "tasks"])


async def _get_encounter_or_404(
    encounter_id: UUID,
    db: AsyncSession,
) -> Encounter:
    """Verify the encounter exists; raise 404 if not found."""
    encounter = await db.get(Encounter, encounter_id)
    if encounter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encounter {encounter_id} not found.",
        )
    return encounter


@router.get(
    "/{encounter_id}/tasks",
    response_model=AgentTaskListResponse,
    summary="List all agent tasks for an encounter with SLA status",
    responses={
        200: {"description": "Task list returned successfully"},
        401: {"description": "Missing or invalid JWT"},
        403: {"description": "Insufficient role"},
        404: {"description": "Encounter not found"},
    },
)
async def list_encounter_tasks(
    encounter_id: UUID,
    db: AsyncSession = Depends(get_read_db),
    current_user: TokenClaims = Depends(get_current_user),
) -> AgentTaskListResponse:
    """Return all AgentTask records for the specified encounter.

    Requires a valid staff JWT. Uses the read replica for query performance (TR-010).
    Includes sla_threshold_minutes (backfilled from config if NULL) and sla_breached flag.
    
    US-026: For DOCUMENTATION tasks, includes completeness_status and missing_fields from
    the most recent Document record.
    """
    # Validate encounter exists
    await _get_encounter_or_404(encounter_id, db)

    # Fetch all tasks for the encounter
    stmt = (
        sa.select(AgentTask)
        .where(AgentTask.encounter_id == encounter_id)
        .order_by(AgentTask.created_at.asc())
    )
    result = await db.execute(stmt)
    tasks: list[AgentTask] = list(result.scalars().all())

    # Fetch all documents for the encounter (US-026)
    doc_stmt = (
        sa.select(Document)
        .where(Document.encounter_id == encounter_id)
        .order_by(Document.created_at.desc())
    )
    doc_result = await db.execute(doc_stmt)
    documents: list[Document] = list(doc_result.scalars().all())
    
    # Find the latest document (most recent by created_at)
    latest_doc = documents[0] if documents else None

    logger.info(
        "Tasks fetched: encounter_id=%s count=%d user=%s",
        encounter_id,
        len(tasks),
        current_user.sub,
    )

    # Build response with document completeness info for DOCUMENTATION tasks
    task_responses: list[AgentTaskResponse] = []
    for task in tasks:
        task_resp = AgentTaskResponse.model_validate(task)
        
        # US-026: Populate document completeness fields for DOCUMENTATION tasks
        if task.agent_type.lower() == "documentation" and latest_doc:
            task_resp.document_id = latest_doc.id
            task_resp.generation_type = latest_doc.generation_type
            task_resp.completeness_status = latest_doc.completeness_status
            task_resp.missing_fields = latest_doc.missing_fields or []
        
        task_responses.append(task_resp)

    return AgentTaskListResponse(
        encounter_id=encounter_id,
        tasks=task_responses,
        total=len(task_responses),
    )
