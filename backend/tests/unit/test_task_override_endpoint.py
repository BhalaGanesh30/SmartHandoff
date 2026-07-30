"""Unit tests for PATCH /api/v1/encounters/{id}/tasks/{task_id}/override.

US-034 Scenario 4: override sets status=COMPLETED, clears sla_escalation_sent_at.
RBAC: only charge_pharmacist and pharmacy_supervisor may call the endpoint.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.repositories.agent_task_repository import (
    TaskAlreadyCompletedError,
    TaskNotFoundError,
    InvalidTaskTypeError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed_task(task_id: uuid.UUID, encounter_id: uuid.UUID) -> MagicMock:
    task = MagicMock()
    task.id = task_id
    task.encounter_id = encounter_id
    task.agent_type = "MEDICATION_RECONCILIATION"
    task.status = MagicMock()
    task.status.value = "completed"
    task.completed_at = datetime.now(tz=timezone.utc)
    task.sla_escalation_sent_at = None  # cleared by override
    return task


# ---------------------------------------------------------------------------
# Scenario 4: Override succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_override_succeeds_for_charge_pharmacist() -> None:
    """US-034 Scenario 4: charge pharmacist can override; response has status=COMPLETED and sla_escalation_sent_at=None."""
    from app.api.v1.routers.tasks import override_task
    from app.core.auth.jwt import TokenClaims
    
    enc_id = uuid.uuid4()
    task_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    completed_task = _make_completed_task(task_id, enc_id)

    # Mock repository
    mock_repo = AsyncMock()
    mock_repo.override_task = AsyncMock(return_value=completed_task)
    
    # Mock current_user (charge pharmacist)
    mock_user = TokenClaims(sub=str(actor_id), role="CHARGE_PHARMACIST", exp=9999999999)
    
    # Mock request body
    from app.schemas.task_override import TaskOverrideRequest
    body = TaskOverrideRequest(note="Reconciliation completed offline with attending.")
    
    # Mock database session
    mock_db = AsyncMock()
    
    with patch("app.api.v1.routers.tasks.AgentTaskRepository", return_value=mock_repo):
        response = await override_task(
            encounter_id=enc_id,
            task_id=task_id,
            body=body,
            current_user=mock_user,
            db=mock_db,
        )
    
    assert response.status == "completed"
    assert response.sla_escalation_sent_at is None
    assert response.task_id == task_id
    assert response.encounter_id == enc_id


@pytest.mark.asyncio
async def test_override_returns_404_when_task_not_found() -> None:
    """HTTP 404 if task does not exist for this encounter."""
    from app.api.v1.routers.tasks import override_task
    from app.core.auth.jwt import TokenClaims
    
    enc_id = uuid.uuid4()
    task_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    # Mock repository that raises TaskNotFoundError
    mock_repo = AsyncMock()
    mock_repo.override_task = AsyncMock(
        side_effect=TaskNotFoundError(task_id=task_id, encounter_id=enc_id)
    )
    
    mock_user = TokenClaims(sub=str(actor_id), role="CHARGE_PHARMACIST", exp=9999999999)
    from app.schemas.task_override import TaskOverrideRequest
    body = TaskOverrideRequest(note="Task gone.")
    mock_db = AsyncMock()
    
    with patch("app.api.v1.routers.tasks.AgentTaskRepository", return_value=mock_repo):
        with pytest.raises(HTTPException) as exc_info:
            await override_task(
                encounter_id=enc_id,
                task_id=task_id,
                body=body,
                current_user=mock_user,
                db=mock_db,
            )
    
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_override_returns_409_when_already_completed() -> None:
    """HTTP 409 if task is already COMPLETED."""
    from app.api.v1.routers.tasks import override_task
    from app.core.auth.jwt import TokenClaims
    
    enc_id = uuid.uuid4()
    task_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    # Mock repository that raises TaskAlreadyCompletedError
    mock_repo = AsyncMock()
    mock_repo.override_task = AsyncMock(
        side_effect=TaskAlreadyCompletedError(task_id=task_id)
    )
    
    mock_user = TokenClaims(sub=str(actor_id), role="PHARMACY_SUPERVISOR", exp=9999999999)
    from app.schemas.task_override import TaskOverrideRequest
    body = TaskOverrideRequest(note="Already done.")
    mock_db = AsyncMock()
    
    with patch("app.api.v1.routers.tasks.AgentTaskRepository", return_value=mock_repo):
        with pytest.raises(HTTPException) as exc_info:
            await override_task(
                encounter_id=enc_id,
                task_id=task_id,
                body=body,
                current_user=mock_user,
                db=mock_db,
            )
    
    assert exc_info.value.status_code == 409
    assert "already completed" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_override_returns_422_when_invalid_task_type() -> None:
    """HTTP 422 if task is not MEDICATION_RECONCILIATION."""
    from app.api.v1.routers.tasks import override_task
    from app.core.auth.jwt import TokenClaims
    
    enc_id = uuid.uuid4()
    task_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    # Mock repository that raises InvalidTaskTypeError
    mock_repo = AsyncMock()
    mock_repo.override_task = AsyncMock(
        side_effect=InvalidTaskTypeError(task_id=task_id, agent_type="DOCUMENTATION")
    )
    
    mock_user = TokenClaims(sub=str(actor_id), role="CHARGE_PHARMACIST", exp=9999999999)
    from app.schemas.task_override import TaskOverrideRequest
    body = TaskOverrideRequest(note="Wrong type.")
    mock_db = AsyncMock()
    
    with patch("app.api.v1.routers.tasks.AgentTaskRepository", return_value=mock_repo):
        with pytest.raises(HTTPException) as exc_info:
            await override_task(
                encounter_id=enc_id,
                task_id=task_id,
                body=body,
                current_user=mock_user,
                db=mock_db,
            )
    
    assert exc_info.value.status_code == 422
    assert "DOCUMENTATION" in exc_info.value.detail


@pytest.mark.asyncio
async def test_override_clears_sla_escalation_sent_at() -> None:
    """US-034 Scenario 4: Override operation clears sla_escalation_sent_at field."""
    from app.repositories.agent_task_repository import AgentTaskRepository
    from app.models.agent_task import AgentTask, AgentTaskStatus
    
    enc_id = uuid.uuid4()
    task_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    
    # Create a mock task with sla_escalation_sent_at set
    mock_task = MagicMock(spec=AgentTask)
    mock_task.id = task_id
    mock_task.encounter_id = enc_id
    mock_task.agent_type = "MEDICATION_RECONCILIATION"
    mock_task.status = AgentTaskStatus.IN_PROGRESS
    mock_task.sla_escalation_sent_at = datetime.now(tz=timezone.utc)  # Initially set
    
    # Mock session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()
    
    repo = AgentTaskRepository()
    
    with patch("app.repositories.agent_task_repository.sa") as mock_sa:
        # Allow the query to be constructed
        mock_sa.select.return_value.where.return_value = MagicMock()
        mock_sa.update.return_value.where.return_value.values.return_value = MagicMock()
        
        result = await repo.override_task(
            task_id=task_id,
            encounter_id=enc_id,
            actor_id=actor_id,
            note="Test override",
            session=mock_session,
        )
    
    # Verify sla_escalation_sent_at was cleared (set to None)
    assert mock_task.sla_escalation_sent_at is None
    assert mock_task.status == AgentTaskStatus.COMPLETED
    assert mock_task.completed_at is not None
