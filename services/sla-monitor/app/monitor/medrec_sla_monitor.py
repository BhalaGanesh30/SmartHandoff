"""MedRecSLAMonitor — Medication reconciliation 24-hour admission SLA check.

Added as a second job to the same APScheduler AsyncIOScheduler instance
started by SLAMonitor (app/monitor/sla_monitor.py, US-021).

SLA window: 24 hours from encounter.admit_date (BR-002, CMS CoP).
Idempotency: sla_escalation_sent_at field on AgentTask (US-034 Scenario 3).

Design refs:
    US-034 AC Scenario 1  — escalate at 24 h after admit_date
    US-034 AC Scenario 2  — COMPLETED tasks must never be escalated
    US-034 AC Scenario 3  — sla_escalation_sent_at prevents duplicate escalation
    US-034 Technical Notes — same APScheduler instance as US-021; admit_date from encounter
    TR-010                 — use read replica for poll queries
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.sla_loader import SLAConfig
from app.db.session import get_read_session, get_write_session
from app.models.agent_task import AgentTask
from app.models.encounter import Encounter
from app.publisher.charge_pharmacist_escalation_publisher import (
    ChargePharmacistEscalationPublisher,
)

logger = logging.getLogger(__name__)

_MEDREC_AGENT_TYPE = "MEDICATION_RECONCILIATION"
_ACTIVE_STATUSES: frozenset[str] = frozenset({"IN_PROGRESS", "PENDING"})


class MedRecSLAMonitor:
    """Medication reconciliation 24-hour admission SLA checker.

    Intended to be registered as a second job on the APScheduler instance
    owned by ``SLAMonitor`` — not as a standalone scheduler.

    Usage (in ``SLAMonitor.start()``)::

        medrec_monitor = MedRecSLAMonitor(
            publisher=ChargePharmacistEscalationPublisher(...),
            config=self._config,
        )
        self._scheduler.add_job(
            medrec_monitor.run_check,
            trigger="interval",
            seconds=self._config.monitor_interval_seconds,
            id="medrec_sla_check",
            max_instances=1,
            coalesce=True,
        )
    """

    def __init__(
        self,
        publisher: ChargePharmacistEscalationPublisher,
        config: SLAConfig,
    ) -> None:
        self._publisher = publisher
        self._sla_entry = config.med_reconciliation_admission_entry()
        self._threshold = timedelta(minutes=self._sla_entry.threshold_minutes)

    async def run_check(self) -> None:
        """Entry point called by APScheduler every ``monitor_interval_seconds``."""
        logger.info("MedRecSLAMonitor: starting 24-hour admission SLA check")
        try:
            breached = await self._find_breached_tasks()
            for task, encounter in breached:
                await self._handle_breach(task, encounter)
        except Exception:
            logger.exception("MedRecSLAMonitor: unhandled error during SLA check")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _find_breached_tasks(
        self,
    ) -> list[tuple[AgentTask, Encounter]]:
        """Query the read replica for MEDICATION_RECONCILIATION tasks past 24h.

        Returns:
            List of (AgentTask, Encounter) pairs where the admission SLA is breached
            and no escalation has been sent yet.
        """
        cutoff: datetime = datetime.now(tz=timezone.utc) - self._threshold

        stmt = (
            sa.select(AgentTask, Encounter)
            .join(Encounter, AgentTask.encounter_id == Encounter.id)
            .where(
                AgentTask.agent_type == _MEDREC_AGENT_TYPE,
                AgentTask.status.in_(_ACTIVE_STATUSES),
                AgentTask.sla_escalation_sent_at.is_(None),
                Encounter.admit_date.isnot(None),
                Encounter.admit_date <= cutoff,
            )
        )

        async with get_read_session() as session:  # TR-010: read replica
            result = await session.execute(stmt)
            return list(result.all())

    async def _handle_breach(
        self,
        task: AgentTask,
        encounter: Encounter,
    ) -> None:
        """Publish escalation and stamp ``sla_escalation_sent_at`` atomically.

        Sets ``AgentTask.sla_escalation_sent_at = NOW()`` before publishing so that
        a publisher failure leaves the stamp set — a deliberate choice to avoid
        duplicate escalation storms if the publisher is intermittently unavailable.
        The publisher has its own retry (TASK-004).
        """
        now = datetime.now(tz=timezone.utc)
        
        # Ensure admit_date has timezone info for calculation
        admit_date_aware = encounter.admit_date
        if admit_date_aware.tzinfo is None:
            admit_date_aware = admit_date_aware.replace(tzinfo=timezone.utc)
        
        hours_elapsed = int(
            (now - admit_date_aware).total_seconds() / 3600
        )

        async with get_write_session() as session:
            # Stamp first — prevents race if scheduler fires two concurrent ticks
            await session.execute(
                sa.update(AgentTask)
                .where(
                    AgentTask.id == task.id,
                    AgentTask.sla_escalation_sent_at.is_(None),  # guard
                )
                .values(sla_escalation_sent_at=now)
            )
            await session.commit()

        await self._publisher.publish(
            encounter_id=encounter.id,
            task_id=task.id,
            patient_unit=encounter.unit or "UNKNOWN",
            hours_elapsed=hours_elapsed,
        )

        logger.warning(
            "MedRecSLAMonitor: escalation sent",
            extra={
                "encounter_id": str(encounter.id),
                "task_id": str(task.id),
                "hours_elapsed": hours_elapsed,
                "patient_unit": encounter.unit or "UNKNOWN",
            },
        )
