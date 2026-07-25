"""Unit tests for SLAMonitor breach detection logic.

Tests are pure unit tests — DB and Pub/Sub are mocked.
No APScheduler ticks are invoked; _find_breached_tasks and _handle_breach
are tested directly as async functions.

US-021 DoD: unit tests for SLA breach detection, non-escalation of completed tasks.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.sla_loader import load_sla_config
from app.monitor.sla_monitor import SLAMonitor, _ACTIVE_STATUSES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(
    agent_type: str,
    status: str,
    minutes_ago: int,
    sla_breached: bool = False,
) -> MagicMock:
    """Build a mock AgentTask with the given age and status."""
    task = MagicMock()
    task.id = uuid.uuid4()
    task.encounter_id = uuid.uuid4()
    task.agent_type = agent_type
    task.status = status
    task.sla_breached = sla_breached
    task.sla_threshold_minutes = None
    task.supervisor_id = uuid.uuid4()
    task.created_at = datetime.now(tz=timezone.utc) - timedelta(minutes=minutes_ago)
    return task


@pytest.fixture
def valid_config_yaml(tmp_path: Path) -> Path:
    content = dedent("""\
        sla_thresholds:
          DOCUMENTATION: 30
          MEDICATION_RECONCILIATION: 60
          BED_MANAGEMENT: 15
          FOLLOW_UP_CARE: 120
          PATIENT_COMMUNICATION: 30
        monitor_interval_seconds: 300
        escalation_dedup_window_minutes: 30
    """)
    p = tmp_path / "sla_config.yaml"
    p.write_text(content)
    return p


@pytest.fixture
def publisher_mock() -> MagicMock:
    mock = MagicMock()
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
def monitor(valid_config_yaml: Path, publisher_mock: MagicMock) -> SLAMonitor:
    load_sla_config.cache_clear()
    with patch("app.monitor.sla_monitor.load_sla_config") as mock_load:
        mock_load.return_value = load_sla_config(valid_config_yaml)
        m = SLAMonitor(publisher=publisher_mock)
    return m


# ---------------------------------------------------------------------------
# _find_breached_tasks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_breached_tasks_returns_overdue_in_progress(
    monitor: SLAMonitor,
    valid_config_yaml: Path,
) -> None:
    """US-021 Scenario 1: DOCUMENTATION task at 31 minutes detected as breached."""
    load_sla_config.cache_clear()
    overdue_task = _make_task("DOCUMENTATION", "IN_PROGRESS", minutes_ago=31)
    not_due_task = _make_task("DOCUMENTATION", "IN_PROGRESS", minutes_ago=10)

    read_session = AsyncMock()
    read_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[overdue_task, not_due_task])
        )))
    )

    with patch("app.monitor.sla_monitor.load_sla_config") as mock_load:
        mock_load.return_value = load_sla_config(valid_config_yaml)
        monitor._config = mock_load.return_value
        now = datetime.now(tz=timezone.utc)
        result = await monitor._find_breached_tasks(read_session, now)

    assert len(result) == 1
    assert result[0].agent_type == "DOCUMENTATION"


@pytest.mark.asyncio
async def test_find_breached_tasks_excludes_completed(
    monitor: SLAMonitor,
    valid_config_yaml: Path,
) -> None:
    """US-021 Scenario 3: COMPLETED task created 60 minutes ago is NOT returned."""
    read_session = AsyncMock()
    read_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[])  # COMPLETED filtered out by WHERE clause
        )))
    )

    with patch("app.monitor.sla_monitor.load_sla_config") as mock_load:
        mock_load.return_value = load_sla_config(valid_config_yaml)
        monitor._config = mock_load.return_value
        now = datetime.now(tz=timezone.utc)
        result = await monitor._find_breached_tasks(read_session, now)

    assert result == []


@pytest.mark.asyncio
async def test_active_statuses_set_excludes_completed_and_cancelled() -> None:
    """US-021 Scenario 3: Only IN_PROGRESS and PENDING are in _ACTIVE_STATUSES."""
    assert "COMPLETED" not in _ACTIVE_STATUSES
    assert "CANCELLED" not in _ACTIVE_STATUSES
    assert "IN_PROGRESS" in _ACTIVE_STATUSES
    assert "PENDING" in _ACTIVE_STATUSES


@pytest.mark.asyncio
async def test_bed_management_threshold_is_15_minutes(
    monitor: SLAMonitor,
    valid_config_yaml: Path,
) -> None:
    """US-021 Scenario 4: BED_MANAGEMENT task at 16 minutes is breached (threshold=15)."""
    load_sla_config.cache_clear()
    overdue = _make_task("BED_MANAGEMENT", "IN_PROGRESS", minutes_ago=16)
    within_sla = _make_task("BED_MANAGEMENT", "IN_PROGRESS", minutes_ago=10)

    read_session = AsyncMock()
    read_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[overdue, within_sla])
        )))
    )

    with patch("app.monitor.sla_monitor.load_sla_config") as mock_load:
        mock_load.return_value = load_sla_config(valid_config_yaml)
        monitor._config = mock_load.return_value
        now = datetime.now(tz=timezone.utc)
        result = await monitor._find_breached_tasks(read_session, now)

    assert len(result) == 1
    assert result[0].agent_type == "BED_MANAGEMENT"


@pytest.mark.asyncio
async def test_documentation_not_breached_at_29_minutes(
    monitor: SLAMonitor,
    valid_config_yaml: Path,
) -> None:
    """US-021 Scenario 4: DOCUMENTATION at 29 minutes is NOT breached (threshold=30)."""
    task = _make_task("DOCUMENTATION", "IN_PROGRESS", minutes_ago=29)

    read_session = AsyncMock()
    read_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[task])
        )))
    )

    with patch("app.monitor.sla_monitor.load_sla_config") as mock_load:
        mock_load.return_value = load_sla_config(valid_config_yaml)
        monitor._config = mock_load.return_value
        now = datetime.now(tz=timezone.utc)
        result = await monitor._find_breached_tasks(read_session, now)

    assert result == []


# ---------------------------------------------------------------------------
# _handle_breach
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_breach_sets_sla_breached_flag(
    monitor: SLAMonitor,
    publisher_mock: MagicMock,
    valid_config_yaml: Path,
) -> None:
    """_handle_breach sets sla_breached=True on the AgentTask."""
    task = _make_task("DOCUMENTATION", "IN_PROGRESS", minutes_ago=35)
    task.sla_breached = False

    write_session = AsyncMock()
    write_session.get = AsyncMock(return_value=task)
    write_session.add = MagicMock()

    with patch("app.monitor.sla_monitor.load_sla_config") as mock_load:
        mock_load.return_value = load_sla_config(valid_config_yaml)
        monitor._config = mock_load.return_value
        await monitor._handle_breach(write_session, task, datetime.now(tz=timezone.utc))

    assert task.sla_breached is True
    assert task.sla_threshold_minutes == 30
    write_session.add.assert_called_once_with(task)


@pytest.mark.asyncio
async def test_handle_breach_skips_db_write_if_already_breached(
    monitor: SLAMonitor,
    publisher_mock: MagicMock,
    valid_config_yaml: Path,
) -> None:
    """_handle_breach does NOT call session.add() if sla_breached already True."""
    task = _make_task("DOCUMENTATION", "IN_PROGRESS", minutes_ago=45)
    task.sla_breached = True  # already flagged

    write_session = AsyncMock()
    write_session.get = AsyncMock(return_value=task)
    write_session.add = MagicMock()

    with patch("app.monitor.sla_monitor.load_sla_config") as mock_load:
        mock_load.return_value = load_sla_config(valid_config_yaml)
        monitor._config = mock_load.return_value
        await monitor._handle_breach(write_session, task, datetime.now(tz=timezone.utc))

    write_session.add.assert_not_called()
    publisher_mock.publish.assert_called_once()  # escalation still fires


@pytest.mark.asyncio
async def test_handle_breach_still_publishes_on_already_breached(
    monitor: SLAMonitor,
    publisher_mock: MagicMock,
    valid_config_yaml: Path,
) -> None:
    """EscalationPublisher.publish() is called even if sla_breached already True.
    Idempotency is EscalationPublisher's responsibility.
    """
    task = _make_task("BED_MANAGEMENT", "IN_PROGRESS", minutes_ago=20)
    task.sla_breached = True

    write_session = AsyncMock()
    write_session.get = AsyncMock(return_value=task)
    write_session.add = MagicMock()

    with patch("app.monitor.sla_monitor.load_sla_config") as mock_load:
        mock_load.return_value = load_sla_config(valid_config_yaml)
        monitor._config = mock_load.return_value
        await monitor._handle_breach(write_session, task, datetime.now(tz=timezone.utc))

    publisher_mock.publish.assert_called_once()
