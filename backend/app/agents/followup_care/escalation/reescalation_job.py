"""APScheduler job for re-escalating unacknowledged care team escalations.

Runs every 60 seconds to detect escalations that have not been acknowledged
within 15 minutes and escalates them to the supervisor.

Responsibility:
    1. Query care_escalation WHERE status=PENDING AND escalated_to_supervisor=FALSE
       AND sent_at < NOW() - INTERVAL '15 minutes'
    2. For each result:
        a. Update status=ESCALATED_TO_SUPERVISOR, escalated_to_supervisor=True, escalated_at=NOW()
        b. Publish SUPERVISOR_ESCALATION to notification-requests

Idempotency:
    The DB UPDATE is performed before the Pub/Sub publish. The escalated_to_supervisor
    flag prevents duplicate supervisor escalations on subsequent scheduler ticks.
    If the job crashes between UPDATE and publish, Cloud Monitoring alerts detect
    the missing notification via DLQ depth.

PHI handling:
    Logs contain only escalation_id (UUID), encounter_id (UUID). No patient name,
    MRN, DOB, phone, or email in any log line (ADR-007).

Design refs:
    US-042 AC Scenario 3 — supervisor escalation for unacknowledged alerts
    design.md §5.1 TR-015 — DLQ and zero message loss
    ADR-001 — idempotency via escalated_to_supervisor flag
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from google.cloud import pubsub_v1
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.care_escalation import CareEscalation, CareEscalationStatus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

ESCALATION_SLA_MINUTES = 15
JOB_INTERVAL_SECONDS = 60


class ReEscalationJob:
    """Detects unacknowledged escalations past the 15-minute SLA and re-escalates to supervisor.

    Args:
        session_factory: Async SQLAlchemy session factory.
        publisher: GCP Pub/Sub PublisherClient.
        notification_topic: Full Pub/Sub topic path for notification-requests.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        publisher: pubsub_v1.PublisherClient,
        notification_topic: str,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._notification_topic = notification_topic

    async def run(self) -> None:
        """APScheduler callback — runs every 60 seconds.

        Queries for PENDING escalations past the 15-minute SLA and re-escalates each.
        Errors in individual records are caught and logged; they do not abort the batch.
        """
        sla_cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=ESCALATION_SLA_MINUTES)

        async with self._session_factory() as session:
            result = await session.execute(
                select(CareEscalation).where(
                    CareEscalation.status == CareEscalationStatus.PENDING,
                    CareEscalation.escalated_to_supervisor.is_(False),
                    CareEscalation.sent_at < sla_cutoff,
                    CareEscalation.deleted_at.is_(None),
                )
            )
            overdue_escalations = result.scalars().all()

        if not overdue_escalations:
            logger.debug(
                "reescalation_job.no_overdue_escalations",
                extra={"sla_cutoff": sla_cutoff.isoformat()},
            )
            return

        logger.info(
            "reescalation_job.overdue_escalations_found",
            extra={"count": len(overdue_escalations)},
        )

        for escalation in overdue_escalations:
            try:
                await self._reescalate(escalation)
            except Exception as exc:
                logger.error(
                    "reescalation_job.reescalation_failed",
                    extra={
                        "escalation_id": str(escalation.id),
                        "encounter_id": str(escalation.encounter_id),
                        "error": str(exc),
                    },
                    exc_info=True,
                )

    async def _reescalate(self, escalation: CareEscalation) -> None:
        """Update the escalation record to ESCALATED_TO_SUPERVISOR and publish notification.

        The DB update is committed before the Pub/Sub publish so that a crash
        after the UPDATE but before publish is recoverable via Cloud Monitoring
        alert (DLQ count > 0), not via duplicate re-escalation.
        
        Args:
            escalation: The CareEscalation record to re-escalate
        """
        now = datetime.now(tz=timezone.utc)

        async with self._session_factory() as session:
            # Atomic update — only updates PENDING records that are not yet escalated
            result = await session.execute(
                update(CareEscalation)
                .where(
                    CareEscalation.id == escalation.id,
                    CareEscalation.status == CareEscalationStatus.PENDING,
                    CareEscalation.escalated_to_supervisor.is_(False),
                )
                .values(
                    status=CareEscalationStatus.ESCALATED_TO_SUPERVISOR,
                    escalated_to_supervisor=True,
                    escalated_at=now,
                )
                .returning(CareEscalation.id)
            )
            updated_id = result.scalar_one_or_none()

            if updated_id is None:
                # Concurrent tick already updated this record — skip
                logger.info(
                    "reescalation_job.concurrent_update_skipped",
                    extra={"escalation_id": str(escalation.id)},
                )
                return

            await session.commit()

        # Publish SUPERVISOR_ESCALATION after DB commit
        self._publish_supervisor_escalation(escalation, sent_at=now)

        logger.info(
            "reescalation_job.supervisor_escalation_published",
            extra={
                "escalation_id": str(escalation.id),
                "encounter_id": str(escalation.encounter_id),
            },
        )

    def _publish_supervisor_escalation(
        self,
        escalation: CareEscalation,
        sent_at: datetime,
    ) -> None:
        """Publish SUPERVISOR_ESCALATION to the notification-requests topic.

        PHI policy: Only UUIDs are published. The Notification Service resolves
        the supervisor's contact from app_user at dispatch time (ADR-007).
        
        Args:
            escalation: The CareEscalation record being escalated
            sent_at: UTC timestamp of the escalation
        """
        payload = json.dumps(
            {
                "event_type": "SUPERVISOR_ESCALATION",
                "escalation_id": str(escalation.id),
                "encounter_id": str(escalation.encounter_id),
                "patient_id": str(escalation.patient_id),
                "original_sent_at": escalation.sent_at.isoformat(),
                "channel": "SMS",
                "idempotency_key": f"NOTIF-SUP-ESC-{escalation.id}",
            }
        ).encode("utf-8")

        future = self._publisher.publish(self._notification_topic, payload)
        future.result(timeout=10)  # Block until confirmed
        
        logger.debug(
            "reescalation_job.notification_published",
            extra={
                "escalation_id": str(escalation.id),
                "notification_topic": self._notification_topic,
            },
        )
