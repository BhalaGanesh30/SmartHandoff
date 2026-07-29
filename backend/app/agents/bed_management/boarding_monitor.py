"""BoardingMonitor — detects ED encounters that have breached the 2-hour boarding threshold.

Runs as an APScheduler interval job every 5 minutes on the shared scheduler
provided by US-021. Delegates alert publishing to BoardingAlertPublisher (TASK-003).

Detection query returns encounters where ALL of the following hold:
    1. unit IN <ed_location_codes> (patient is in the ED)
    2. status = 'ADMITTED'
    3. admit_date + 120 minutes <= now (threshold breached)
    4. boarding_alert_resolved_at IS NULL (alert not already resolved)

NOTE: The Encounter model uses `admit_date` (not `admit_time`) and `unit` (not
`current_location`). This implementation adapts to the actual schema.

Design refs:
    US-038 AC Scenario 1  — 120-minute threshold; every-5-min APScheduler job
    US-038 AC Scenario 2  — no bed_assigned_at filter (not in current schema)
    US-038 AC Scenario 4  — idempotency enforced in publisher; monitor passes all candidates
    US-038 TASK-002      — BoardingMonitor class, detection query, APScheduler registration
    design.md §3.1        — BedManagementAgent responsibility
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.bed_management.boarding_schemas import BoardingCandidate
from app.agents.bed_management.ed_location_loader import load_ed_location_codes
from app.db.session import get_write_session
from app.models.encounter import Encounter

if TYPE_CHECKING:
    from app.agents.bed_management.boarding_publisher import BoardingAlertPublisher

logger = logging.getLogger(__name__)

# US-038 AC Scenario 1: threshold = 120 minutes
BOARDING_THRESHOLD_MINUTES: int = 120
# US-038 DoD: monitor runs every 5 minutes
MONITOR_INTERVAL_MINUTES: int = 5


class BoardingMonitor:
    """Identifies ED encounters that have exceeded the boarding threshold.

    Instantiated once per `bed-mgmt-agent` Cloud Run container and registered
    on the shared APScheduler instance (US-021).

    Args:
        publisher: Callable that receives a list of ``BoardingCandidate`` instances
                   and dispatches alerts. Injected to keep monitor/publisher decoupled.
        scheduler: The shared AsyncIOScheduler from US-021.

    Design refs:
        US-038 TASK-002 — BoardingMonitor class definition
        US-038 AC Scenario 1 — 5-minute interval, 120-minute threshold
    """

    def __init__(
        self,
        publisher: "BoardingAlertPublisher",
        scheduler: AsyncIOScheduler,
    ) -> None:
        self._publisher = publisher
        self._scheduler = scheduler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self) -> None:
        """Register the boarding monitor as an APScheduler interval job.

        Idempotent — safe to call multiple times (APScheduler deduplicates by job_id).

        Design ref:
            US-038 TASK-002 — APScheduler registration with 5-minute interval
        """
        self._scheduler.add_job(
            self._run_cycle,
            trigger="interval",
            minutes=MONITOR_INTERVAL_MINUTES,
            id="boarding_monitor",
            replace_existing=True,
            misfire_grace_time=60,  # tolerate 60-second scheduler lag
        )
        logger.info(
            "BoardingMonitor registered: interval=%d minutes, threshold=%d minutes",
            MONITOR_INTERVAL_MINUTES,
            BOARDING_THRESHOLD_MINUTES,
        )

    # ------------------------------------------------------------------
    # Internal cycle
    # ------------------------------------------------------------------

    async def _run_cycle(self) -> None:
        """Execute a single monitoring cycle.

        Queries the DB for boarding candidates and delegates each to the publisher.
        Exceptions are caught and logged — a failed cycle must not crash the scheduler.

        Design refs:
            US-038 TASK-002 — cycle execution with exception handling
            US-038 AC Scenario 1 — detect candidates, delegate to publisher
        """
        try:
            candidates = await self._detect_boarding_candidates()
            if not candidates:
                logger.debug("BoardingMonitor: no boarding candidates found this cycle.")
                return

            logger.info(
                "BoardingMonitor: %d boarding candidate(s) detected.", len(candidates)
            )
            await self._publisher.dispatch_alerts(candidates)
        except Exception:
            logger.exception("BoardingMonitor cycle failed — will retry next interval.")

    async def _detect_boarding_candidates(self) -> list[BoardingCandidate]:
        """Query for encounters that qualify for a boarding alert.

        Returns a list of ``BoardingCandidate`` instances (may include already-alerted
        encounters — idempotency is enforced in the publisher).

        Query criteria (US-038 AC Scenario 1, TASK-002):
            1. unit IN <ed_location_codes> — patient is in the ED
            2. status = 'ADMITTED' — active admission
            3. admit_date + 120 minutes <= now — threshold breached
            4. boarding_alert_resolved_at IS NULL — alert not resolved

        NOTE: Current Encounter model does not have `transfer_time`, `bed_assigned_at`,
        or `current_location` fields. This implementation uses:
            - `admit_date` (instead of admit_time or transfer_time)
            - `unit` (instead of current_location)
            - `boarding_alert_resolved_at IS NULL` (instead of bed_assigned_at IS NULL)

        Returns:
            List of BoardingCandidate instances.

        Design refs:
            US-038 TASK-002 — detection query logic
            US-038 AC Scenario 2 — exclude resolved alerts
        """
        ed_codes = load_ed_location_codes()
        threshold_time = datetime.now(UTC) - timedelta(minutes=BOARDING_THRESHOLD_MINUTES)

        stmt = (
            select(Encounter)
            .where(
                Encounter.unit.in_(ed_codes),
                Encounter.status == "ADMITTED",
                Encounter.admit_date.isnot(None),
                Encounter.admit_date <= threshold_time,
                Encounter.boarding_alert_resolved_at.is_(None),
            )
        )

        candidates: list[BoardingCandidate] = []
        async with get_write_session() as session:  # type: AsyncSession
            result = await session.execute(stmt)
            encounters = result.scalars().all()

        now = datetime.now(UTC)
        for enc in encounters:
            if enc.admit_date is None:
                logger.warning(
                    "Encounter %s has no admit_date — skipping.", enc.id
                )
                continue

            minutes_elapsed = int((now - enc.admit_date).total_seconds() / 60)
            candidates.append(
                BoardingCandidate(
                    encounter_id=str(enc.id),
                    patient_id=str(enc.patient_id),
                    ed_arrival_time=enc.admit_date,
                    minutes_elapsed=minutes_elapsed,
                    target_unit=enc.unit,  # NOTE: using unit as target_unit (might need adjustment)
                    boarding_alert_sent_at=enc.boarding_alert_sent_at,
                    current_location=enc.unit,  # NOTE: using unit as current_location
                )
            )

        return candidates
