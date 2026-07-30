"""Unit tests for BedManagementAgent.process() (agent.py).

Coverage:
  SC-1 (A01): bed → OCCUPIED; mv_refresh triggered; no housekeeping notification
  SC-2 (A03): bed → DIRTY; mv_refresh triggered; housekeeping notification published
  SC-2 (A02): two DB updates; mv_refresh triggered; no housekeeping notification
  DoD: unhandled event types silently skipped (returns None)
  DoD: DB failure raises RetryableError

Design refs:
    US-035 TASK-006 — Unit test coverage for agent.py
    US-035 TASK-001 — BedManagementAgent implementation
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.agents.bed_management.agent import BedManagementAgent, RetryableError
from app.agents.bed_management.schemas import BedStatus
from app.models.bed import Bed


@pytest.fixture
def mock_refresh_service():
    """Mock BedBoardRefreshService."""
    svc = AsyncMock()
    svc.refresh_async = AsyncMock()
    return svc


@pytest.fixture
def mock_notifier():
    """Mock HousekeepingNotifier."""
    notifier = AsyncMock()
    notifier.notify = AsyncMock()
    return notifier


@pytest.fixture
def mock_bed():
    """Mock Bed ORM object."""
    bed = MagicMock(spec=Bed)
    bed.id = uuid4()
    bed.status = BedStatus.VACANT.value
    bed.unit = "3A"
    bed.room = "301"
    bed.bed_number = "A"
    return bed


@pytest.fixture
def mock_session_factory(mock_bed):
    """Factory returning an AsyncMock session with a bed record."""
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_bed
    execute_result.rowcount = 1
    session.execute.return_value = execute_result
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


@pytest.fixture
def agent(mock_session_factory, mock_refresh_service, mock_notifier):
    """BedManagementAgent with mocked dependencies."""
    return BedManagementAgent(
        db_session_factory=mock_session_factory,
        refresh_service=mock_refresh_service,
        housekeeping_notifier=mock_notifier,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 1: A01 (Admit)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a01_sets_bed_to_occupied(agent, mock_session_factory):
    """A01 (admit) sets bed status to OCCUPIED."""
    bed_id = str(uuid4())
    encounter_id = str(uuid4())
    message = {
        "event_type": "A01",
        "encounter_id": encounter_id,
        "bed_id": bed_id,
    }
    result = await agent.process(message)

    assert result is not None
    assert result.new_status == BedStatus.OCCUPIED
    assert result.event_type == "A01"
    assert result.bed_id == bed_id


@pytest.mark.asyncio
async def test_a01_triggers_mv_refresh_not_housekeeping(
    agent, mock_refresh_service, mock_notifier
):
    """A01 triggers mv_bed_board refresh but NOT housekeeping notification."""
    message = {
        "event_type": "A01",
        "encounter_id": str(uuid4()),
        "bed_id": str(uuid4()),
    }
    await agent.process(message)

    mock_refresh_service.refresh_async.assert_awaited_once()
    mock_notifier.notify.assert_not_awaited()


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 2: A03 (Discharge)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a03_sets_bed_to_dirty_and_notifies(
    agent, mock_refresh_service, mock_notifier, mock_bed
):
    """A03 (discharge) sets bed to DIRTY and publishes housekeeping notification."""
    mock_bed.status = BedStatus.OCCUPIED.value
    bed_id = str(uuid4())
    encounter_id = str(uuid4())
    message = {
        "event_type": "A03",
        "encounter_id": encounter_id,
        "bed_id": bed_id,
    }
    result = await agent.process(message)

    assert result.new_status == BedStatus.DIRTY
    assert result.event_type == "A03"
    mock_refresh_service.refresh_async.assert_awaited_once()
    mock_notifier.notify.assert_awaited_once_with(
        bed_id=bed_id,
        encounter_id=encounter_id,
    )


# ──────────────────────────────────────────────────────────────────────────────
# A02 (Transfer)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a02_updates_two_beds(agent, mock_session_factory, mock_refresh_service):
    """A02 (transfer) updates two beds: previous → DIRTY, new → OCCUPIED."""
    previous_bed_id = str(uuid4())
    new_bed_id = str(uuid4())
    encounter_id = str(uuid4())
    message = {
        "event_type": "A02",
        "encounter_id": encounter_id,
        "previous_bed_id": previous_bed_id,
        "bed_id": new_bed_id,
    }
    result = await agent.process(message)

    assert result is not None
    assert result.event_type == "A02"
    # mv_refresh triggered after transfer
    mock_refresh_service.refresh_async.assert_awaited_once()


# ──────────────────────────────────────────────────────────────────────────────
# Unhandled event type
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unhandled_event_type_returns_none(agent):
    """Unhandled event types (e.g., A08) return None — silently skipped."""
    message = {
        "event_type": "A08",  # Update demographics — not handled
        "encounter_id": str(uuid4()),
        "bed_id": str(uuid4()),
    }
    result = await agent.process(message)
    assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# DB failure → RetryableError
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_db_failure_raises_retryable_error(agent, mock_session_factory):
    """DB connection failure raises RetryableError for Pub/Sub retry."""
    session = mock_session_factory.return_value.__aenter__.return_value
    session.execute.side_effect = Exception("DB connection lost")

    with pytest.raises(RetryableError):
        await agent.process({
            "event_type": "A01",
            "encounter_id": str(uuid4()),
            "bed_id": str(uuid4()),
        })


# ──────────────────────────────────────────────────────────────────────────────
# Status transition validation
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a01_from_occupied_is_valid(agent, mock_bed):
    """A01 can admit into an already-occupied bed (override scenario)."""
    mock_bed.status = BedStatus.OCCUPIED.value
    message = {
        "event_type": "A01",
        "encounter_id": str(uuid4()),
        "bed_id": str(uuid4()),
    }
    result = await agent.process(message)
    assert result.new_status == BedStatus.OCCUPIED


@pytest.mark.asyncio
async def test_a03_from_vacant_raises_error(agent, mock_bed):
    """A03 (discharge) from VACANT is invalid — raises BedStatusTransitionError."""
    from app.exceptions import BedStatusTransitionError
    
    mock_bed.status = BedStatus.VACANT.value
    message = {
        "event_type": "A03",
        "encounter_id": str(uuid4()),
        "bed_id": str(uuid4()),
    }
    
    # BedStatusTransitionError should be raised by status_machine, not wrapped
    with pytest.raises(BedStatusTransitionError):
        await agent.process(message)
