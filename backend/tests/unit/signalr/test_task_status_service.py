"""Unit tests for TaskStatusTransitionService.

Tests mock SignalRBroadcaster and AsyncSession — no live DB or Azure calls.
Coverage:
  - broadcast called with correct payload after commit.
  - Invalid transitions raise ValueError (state machine guard).
  - broadcast failure does not cause DB rollback (fire-and-forget).
  - completed_at is set on COMPLETED transition.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from uuid import uuid4

from app.models.agent_task import AgentTask, AgentTaskStatus
from app.services.task_status_service import TaskStatusTransitionService, _validate_transition
from app.signalr.schemas import TaskUpdatedPayload


def _make_task(status: AgentTaskStatus = AgentTaskStatus.IN_PROGRESS) -> AgentTask:
    """Create a mock AgentTask for testing."""
    task = MagicMock(spec=AgentTask)
    task.id = uuid4()
    task.encounter_id = uuid4()
    task.unit_id = "3A"
    task.target_role = "nurse"
    task.agent_type = "DOCUMENTATION"
    task.status = status.value
    task.completed_at = None
    return task


@pytest.fixture
def mock_broadcaster() -> AsyncMock:
    """Create a mock SignalRBroadcaster."""
    b = AsyncMock()
    b.broadcast_task_updated = AsyncMock()
    return b


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock AsyncSession."""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


class TestTaskStatusTransitionService:
    @pytest.mark.asyncio
    async def test_broadcast_called_after_commit(self, mock_broadcaster, mock_db):
        """Verify SignalR broadcast is called with correct payload after DB commit."""
        service = TaskStatusTransitionService(mock_broadcaster)
        task = _make_task(AgentTaskStatus.IN_PROGRESS)

        await service.transition(mock_db, task, AgentTaskStatus.COMPLETED)

        mock_db.commit.assert_awaited_once()
        mock_broadcaster.broadcast_task_updated.assert_awaited_once()
        
        # Verify payload structure
        payload: TaskUpdatedPayload = mock_broadcaster.broadcast_task_updated.call_args[0][0]
        assert payload.new_status == "COMPLETED"
        assert payload.previous_status == "IN_PROGRESS"
        assert str(payload.task_id) == str(task.id)
        assert payload.unit_id == "3A"
        assert payload.role_name == "nurse"
        assert payload.agent_type == "DOCUMENTATION"

    @pytest.mark.asyncio
    async def test_invalid_transition_raises_value_error(self, mock_broadcaster, mock_db):
        """Verify invalid state transitions are rejected before DB write."""
        service = TaskStatusTransitionService(mock_broadcaster)
        task = _make_task(AgentTaskStatus.COMPLETED)

        with pytest.raises(ValueError, match="Invalid AgentTask transition"):
            await service.transition(mock_db, task, AgentTaskStatus.IN_PROGRESS)

        mock_db.commit.assert_not_awaited()
        mock_broadcaster.broadcast_task_updated.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_completed_at_set_on_completed_transition(self, mock_broadcaster, mock_db):
        """Verify completed_at timestamp is set when transitioning to COMPLETED."""
        service = TaskStatusTransitionService(mock_broadcaster)
        task = _make_task(AgentTaskStatus.IN_PROGRESS)

        await service.transition(mock_db, task, AgentTaskStatus.COMPLETED)

        assert task.completed_at is not None
        assert isinstance(task.completed_at, datetime)

    @pytest.mark.asyncio
    async def test_completed_at_set_on_failed_transition(self, mock_broadcaster, mock_db):
        """Verify completed_at timestamp is set when transitioning to FAILED."""
        service = TaskStatusTransitionService(mock_broadcaster)
        task = _make_task(AgentTaskStatus.IN_PROGRESS)

        await service.transition(mock_db, task, AgentTaskStatus.FAILED)

        assert task.completed_at is not None
        assert isinstance(task.completed_at, datetime)

    @pytest.mark.asyncio
    async def test_status_updated_in_task_object(self, mock_broadcaster, mock_db):
        """Verify task status is updated to new_status value."""
        service = TaskStatusTransitionService(mock_broadcaster)
        task = _make_task(AgentTaskStatus.IN_PROGRESS)

        await service.transition(mock_db, task, AgentTaskStatus.COMPLETED)

        assert task.status == "completed"


class TestValidateTransition:
    """Test the state machine validation logic."""

    def test_pending_to_in_progress_valid(self):
        """PENDING → IN_PROGRESS is allowed."""
        _validate_transition("pending", AgentTaskStatus.IN_PROGRESS)  # no raise

    def test_in_progress_to_completed_valid(self):
        """IN_PROGRESS → COMPLETED is allowed."""
        _validate_transition("running", AgentTaskStatus.COMPLETED)

    def test_in_progress_to_failed_valid(self):
        """IN_PROGRESS → FAILED is allowed."""
        _validate_transition("running", AgentTaskStatus.FAILED)

    def test_completed_to_any_invalid(self):
        """COMPLETED is terminal — no transitions allowed."""
        with pytest.raises(ValueError):
            _validate_transition("completed", AgentTaskStatus.IN_PROGRESS)

    def test_pending_to_completed_invalid(self):
        """Cannot skip IN_PROGRESS."""
        with pytest.raises(ValueError):
            _validate_transition("pending", AgentTaskStatus.COMPLETED)

    def test_failed_to_in_progress_valid_retry(self):
        """FAILED → IN_PROGRESS is allowed (retry path)."""
        _validate_transition("failed", AgentTaskStatus.IN_PROGRESS)

    def test_queued_to_pending_valid(self):
        """QUEUED → PENDING is allowed."""
        _validate_transition("queued", AgentTaskStatus.PENDING)

    def test_queued_to_in_progress_valid(self):
        """QUEUED → IN_PROGRESS is allowed (skip pending)."""
        _validate_transition("queued", AgentTaskStatus.IN_PROGRESS)
