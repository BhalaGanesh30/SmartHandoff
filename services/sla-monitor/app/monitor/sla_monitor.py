"""SLAMonitor — APScheduler background job for AgentTask SLA breach detection.

Runs every 5 minutes (configurable via sla_config.yaml: monitor_interval_seconds).
Evaluates only ACTIVE tasks (IN_PROGRESS, PENDING); skips COMPLETED / CANCELLED.

On breach:
  1. Sets AgentTask.sla_breached = True (write session).
  2. Populates AgentTask.sla_threshold_minutes if not already set.
  3. Delegates escalation to EscalationPublisher (app/publisher/escalation_publisher.py).

US-021: SLA Monitor must use READ DB session for poll query (replica routing, TR-010).
US-021 Technical Notes: avoid time.sleep(); use APScheduler AsyncIOScheduler.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.sla_loader import SLAConfig, load_sla_config
from app.db.session import get_read_session, get_write_session
from app.models.agent_task import AgentTask
from app.monitor.medrec_sla_monitor import MedRecSLAMonitor
from app.publisher.charge_pharmacist_escalation_publisher import (
    ChargePharmacistEscalationPublisher,
)
from app.publisher.escalation_publisher import EscalationPublisher

logger = logging.getLogger(__name__)

# Statuses eligible for SLA evaluation (US-021 Scenario 3).
_ACTIVE_STATUSES: frozenset[str] = frozenset({"IN_PROGRESS", "PENDING"})


class SLAMonitor:
    """Scheduled SLA breach detector for AgentTask records.

    Usage (startup lifespan):
        monitor = SLAMonitor(
            publisher=EscalationPublisher(...),
            medrec_publisher=ChargePharmacistEscalationPublisher(...),
        )
        monitor.start()
        # on shutdown:
        monitor.shutdown()
    """

    def __init__(
        self,
        publisher: EscalationPublisher,
        medrec_publisher: ChargePharmacistEscalationPublisher | None = None,
    ) -> None:
        self._publisher = publisher
        self._medrec_publisher = medrec_publisher
        self._config: SLAConfig = load_sla_config()
        self._scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        """Register the monitor job(s) and start the scheduler."""
        # US-021: Coordinator SLA job
        self._scheduler.add_job(
            self._run_check,
            trigger="interval",
            seconds=self._config.monitor_interval_seconds,
            id="sla_monitor",
            replace_existing=True,
            max_instances=1,  # prevent overlapping runs
        )
        
        # US-034: Medication reconciliation admission SLA job (second job, same scheduler)
        if self._medrec_publisher is not None:
            medrec_monitor = MedRecSLAMonitor(
                publisher=self._medrec_publisher,
                config=self._config,
            )
            self._scheduler.add_job(
                medrec_monitor.run_check,
                trigger="interval",
                seconds=self._config.monitor_interval_seconds,
                id="medrec_sla_check",
                replace_existing=True,
                max_instances=1,  # prevent overlapping runs
                coalesce=True,
            )
            logger.info("SLAMonitor: registered medication reconciliation SLA job")
        
        self._scheduler.start()
        job_count = 2 if self._medrec_publisher is not None else 1
        logger.info(
            "SLAMonitor started — %d job(s) registered, polling every %d seconds",
            job_count,
            self._config.monitor_interval_seconds,
        )

    def shutdown(self) -> None:
        """Stop the scheduler gracefully."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("SLAMonitor stopped")

    async def _run_check(self) -> None:
        """Single monitor tick: detect and escalate SLA breaches.

        Uses READ session for poll query (TR-010 replica routing).
        Uses WRITE session for breach flag updates.
        """
        logger.debug("SLAMonitor tick — scanning for SLA breaches")
        now = datetime.now(tz=timezone.utc)

        async with get_read_session() as read_session:
            breached_tasks = await self._find_breached_tasks(read_session, now)

        if not breached_tasks:
            logger.debug("SLAMonitor tick — no breaches found")
            return

        logger.info("SLAMonitor tick — %d breach(es) detected", len(breached_tasks))

        async with get_write_session() as write_session:
            for task in breached_tasks:
                await self._handle_breach(write_session, task, now)
            await write_session.commit()

    async def _find_breached_tasks(
        self,
        session: AsyncSession,
        now: datetime,
    ) -> list[AgentTask]:
        """Query active tasks and return those that have exceeded their SLA.

        Applies the partial index ix_agent_task_active_status_created (TASK-002)
        by filtering on status IN ('IN_PROGRESS', 'PENDING').
        """
        stmt = (
            sa.select(AgentTask)
            .where(AgentTask.status.in_(_ACTIVE_STATUSES))
            .execution_options(populate_existing=True)
        )
        result = await session.execute(stmt)
        active_tasks: list[AgentTask] = list(result.scalars().all())

        breached: list[AgentTask] = []
        for task in active_tasks:
            threshold_minutes = self._config.threshold_for(task.agent_type)
            elapsed_minutes = (now - task.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
            if elapsed_minutes >= threshold_minutes:
                breached.append(task)

        return breached

    async def _handle_breach(
        self,
        session: AsyncSession,
        task: AgentTask,
        now: datetime,
    ) -> None:
        """Update breach flag and fire escalation for a single breached task.

        Idempotent: if `sla_breached` is already True, skips the DB write.
        Escalation idempotency is enforced inside EscalationPublisher (TASK-004).
        """
        threshold_minutes = self._config.threshold_for(task.agent_type)
        elapsed_minutes = int(
            (now - task.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
        )

        # Re-fetch the task in the WRITE session to avoid stale state.
        db_task: AgentTask | None = await session.get(AgentTask, task.id)
        if db_task is None:
            logger.warning("AgentTask %s not found in write session — skipping", task.id)
            return

        if not db_task.sla_breached:
            db_task.sla_breached = True
            db_task.sla_threshold_minutes = threshold_minutes
            session.add(db_task)
            logger.info(
                "SLA breach flagged: task_id=%s agent_type=%s elapsed=%d min threshold=%d min",
                db_task.id,
                db_task.agent_type,
                elapsed_minutes,
                threshold_minutes,
            )

        # Always attempt to publish escalation — EscalationPublisher deduplicates.
        await self._publisher.publish(
            encounter_id=db_task.encounter_id,
            agent_type=db_task.agent_type,
            minutes_elapsed=elapsed_minutes,
            supervisor_id=db_task.supervisor_id,  # resolved from encounter (TASK-004)
        )
