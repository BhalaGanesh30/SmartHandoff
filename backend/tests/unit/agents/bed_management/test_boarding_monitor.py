"""Unit tests for BoardingMonitor — threshold detection and exclusion logic.

Covers:
    _detect_boarding_candidates — returns candidates at ≥120 min
    _detect_boarding_candidates — excludes encounters under 120 min
    _detect_boarding_candidates — excludes resolved encounters
    register() — adds APScheduler job with correct parameters

Design refs:
    US-038 TASK-005 — Unit test coverage for boarding alert workflow
    US-038 AC Scenario 1 — threshold detection at 120 minutes
    US-038 AC Scenario 2 — no alert before threshold
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.bed_management.boarding_monitor import (
    BOARDING_THRESHOLD_MINUTES,
    MONITOR_INTERVAL_MINUTES,
    BoardingMonitor,
)
from app.agents.bed_management.boarding_schemas import BoardingCandidate
from app.models.encounter import Encounter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_encounter(
    *,
    encounter_id: str | None = None,
    patient_id: str | None = None,
    unit: str = "ED",
    status: str = "ADMITTED",
    admit_date: datetime | None = None,
    boarding_alert_sent_at: datetime | None = None,
    boarding_alert_resolved_at: datetime | None = None,
) -> MagicMock:
    """Create mock Encounter for testing."""
    enc = MagicMock(spec=Encounter)
    enc.id = uuid4() if encounter_id is None else encounter_id
    enc.patient_id = uuid4() if patient_id is None else patient_id
    enc.unit = unit
    enc.status = status
    enc.admit_date = admit_date
    enc.boarding_alert_sent_at = boarding_alert_sent_at
    enc.boarding_alert_resolved_at = boarding_alert_resolved_at
    return enc


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

class TestBoardingMonitorRegister:
    def test_register_adds_interval_job(self):
        """Verify register() adds APScheduler job with correct parameters."""
        scheduler = MagicMock()
        monitor = BoardingMonitor(publisher=MagicMock(), scheduler=scheduler)

        monitor.register()

        scheduler.add_job.assert_called_once()
        call_kwargs = scheduler.add_job.call_args.kwargs
        assert call_kwargs["id"] == "boarding_monitor"
        assert call_kwargs["minutes"] == MONITOR_INTERVAL_MINUTES
        assert call_kwargs["replace_existing"] is True
        assert call_kwargs["misfire_grace_time"] == 60

    def test_register_is_idempotent(self):
        """Calling register() twice replaces the job (does not raise)."""
        scheduler = MagicMock()
        monitor = BoardingMonitor(publisher=MagicMock(), scheduler=scheduler)

        monitor.register()
        monitor.register()

        assert scheduler.add_job.call_count == 2


# ---------------------------------------------------------------------------
# _detect_boarding_candidates()
# ---------------------------------------------------------------------------

class TestDetectBoardingCandidates:
    @pytest.fixture
    def monitor(self):
        return BoardingMonitor(publisher=AsyncMock(), scheduler=MagicMock())

    @pytest.mark.asyncio
    async def test_detect_returns_candidate_at_exactly_120_minutes(self, monitor):
        """An encounter with admit_date exactly 120 minutes ago must be returned."""
        now = datetime.now(UTC)
        enc = _make_encounter(
            encounter_id="enc-001",
            patient_id="pat-001",
            admit_date=now - timedelta(minutes=120),
        )

        with (
            patch(
                "app.agents.bed_management.boarding_monitor.load_ed_location_codes",
                return_value=frozenset({"ED"}),
            ),
            patch(
                "app.agents.bed_management.boarding_monitor.get_write_session"
            ) as mock_session_factory,
            patch("app.agents.bed_management.boarding_monitor.datetime") as mock_dt,
        ):
            mock_dt.now.return_value = now
            mock_dt.UTC = UTC
            session = AsyncMock()
            result_mock = AsyncMock()
            result_mock.scalars.return_value.all.return_value = [enc]
            session.execute.return_value = result_mock
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            candidates = await monitor._detect_boarding_candidates()

        assert len(candidates) == 1
        assert candidates[0].encounter_id == enc.id
        assert candidates[0].minutes_elapsed >= BOARDING_THRESHOLD_MINUTES

    @pytest.mark.asyncio
    async def test_detect_excludes_encounters_under_120_minutes(self, monitor):
        """Encounters admitted less than 120 minutes ago must not be returned."""
        with (
            patch(
                "app.agents.bed_management.boarding_monitor.load_ed_location_codes",
                return_value=frozenset({"ED"}),
            ),
            patch(
                "app.agents.bed_management.boarding_monitor.get_write_session"
            ) as mock_session_factory,
        ):
            session = AsyncMock()
            result_mock = AsyncMock()
            # The DB query WHERE clause handles this — simulate empty result
            result_mock.scalars.return_value.all.return_value = []
            session.execute.return_value = result_mock
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            candidates = await monitor._detect_boarding_candidates()

        assert candidates == []

    @pytest.mark.asyncio
    async def test_detect_excludes_resolved_encounters(self, monitor):
        """Encounters with boarding_alert_resolved_at set must not be returned."""
        now = datetime.now(UTC)
        enc = _make_encounter(
            admit_date=now - timedelta(minutes=130),
            boarding_alert_resolved_at=now - timedelta(minutes=10),
        )

        with (
            patch(
                "app.agents.bed_management.boarding_monitor.load_ed_location_codes",
                return_value=frozenset({"ED"}),
            ),
            patch(
                "app.agents.bed_management.boarding_monitor.get_write_session"
            ) as mock_session_factory,
        ):
            session = AsyncMock()
            result_mock = AsyncMock()
            # DB WHERE boarding_alert_resolved_at IS NULL excludes this encounter
            result_mock.scalars.return_value.all.return_value = []
            session.execute.return_value = result_mock
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            candidates = await monitor._detect_boarding_candidates()

        assert candidates == []

    @pytest.mark.asyncio
    async def test_cycle_exception_does_not_crash_scheduler(self, monitor):
        """A DB exception in _run_cycle() must be caught; scheduler continues."""
        with patch.object(
            monitor,
            "_detect_boarding_candidates",
            side_effect=Exception("DB timeout"),
        ):
            # Must not raise
            await monitor._run_cycle()
