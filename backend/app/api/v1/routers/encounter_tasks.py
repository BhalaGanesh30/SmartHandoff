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
    """
    # Validate encounter exists
    await _get_encounter_or_404(encounter_id, db)

    stmt = (
        sa.select(AgentTask)
        .where(AgentTask.encounter_id == encounter_id)
        .order_by(AgentTask.created_at.asc())
    )
    result = await db.execute(stmt)
    tasks: list[AgentTask] = list(result.scalars().all())

    logger.info(
        "Tasks fetched: encounter_id=%s count=%d user=%s",
        encounter_id,
        len(tasks),
        current_user.sub,
    )

    task_responses = [AgentTaskResponse.model_validate(t) for t in tasks]

    return AgentTaskListResponse(
        encounter_id=encounter_id,
        tasks=task_responses,
        total=len(task_responses),
    )
