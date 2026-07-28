"""CareEscalationMonitor — processes URGENCY_FLAG_SET events from the patient-events topic.

Responsibility:
    1. Receive URGENCY_FLAG_SET message from Pub/Sub subscription urgency-escalation-sub
    2. Look up encounter + on-call nurse from SmartHandoff DB
    3. Create care_escalation record (idempotency-guarded INSERT ... ON CONFLICT DO NOTHING)
    4. Publish CARE_TEAM_ESCALATION to notification-requests topic
    5. ACK the Pub/Sub message

SLA:
    The 60-second window (US-042 AC Scenario 1) starts from the Pub/Sub message publish_time.
    This handler MUST NOT make synchronous FHIR API calls. All data is read from the local DB.

PHI handling:
    Logs contain only encounter_id (UUID), escalation_id (UUID), and nurse_user_id (UUID).
    No patient name, MRN, DOB, phone, or email in any log line.

Design refs:
    design.md §3.2 — agent container pattern
    US-042 AC Scenario 1
    ADR-001 (idempotency), ADR-007 (PHI logs)
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from google.cloud import pubsub_v1
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.followup_care.escalation.schemas import (
    CareTeamEscalationMessage,
    UrgencyFlagSetEvent,
)
from app.models.app_user import AppUser
from app.models.care_escalation import CareEscalation, CareEscalationStatus
from app.models.encounter import Encounter

if TYPE_CHECKING:
    from google.cloud.pubsub_v1.subscriber.message import Message

logger = logging.getLogger(__name__)

ON_CALL_NURSE_ROLE = "ON_CALL_NURSE"


class CareEscalationMonitor:
    """Processes URGENCY_FLAG_SET events and creates initial care team escalations.

    Args:
        session_factory: Async SQLAlchemy session factory for DB operations.
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

    async def handle_urgency_flag_set(
        self,
        message: Message,
    ) -> None:
        """Main entry point called by the Pub/Sub pull subscriber.

        Validates the event, creates the escalation record, and publishes the
        CARE_TEAM_ESCALATION notification — all within the 60-second SLA window.

        Args:
            message: Raw Pub/Sub message from urgency-escalation-sub.
        """
        try:
            event = self._parse_event(message)
        except Exception as exc:
            logger.error(
                "care_escalation_monitor.parse_failure",
                extra={"error": str(exc), "message_id": message.message_id},
            )
            # NACK — let DLQ handle after max_delivery_attempts=5
            message.nack()
            return

        idempotency_key = f"ESC-{event.encounter_id}"
        logger.info(
            "care_escalation_monitor.urgency_flag_received",
            extra={
                "encounter_id": str(event.encounter_id),
                "idempotency_key": idempotency_key,
            },
        )

        async with self._session_factory() as session:
            try:
                escalation = await self._get_or_create_escalation(
                    session=session,
                    event=event,
                    idempotency_key=idempotency_key,
                )
                if escalation is None:
                    # Duplicate event — already processed (idempotency hit)
                    logger.info(
                        "care_escalation_monitor.duplicate_event_skipped",
                        extra={"idempotency_key": idempotency_key},
                    )
                    message.ack()
                    return

                await self._publish_care_team_escalation(escalation)
                await session.commit()

                logger.info(
                    "care_escalation_monitor.escalation_created",
                    extra={
                        "escalation_id": str(escalation.id),
                        "encounter_id": str(escalation.encounter_id),
                        "nurse_user_id": str(escalation.notified_nurse_user_id)
                        if escalation.notified_nurse_user_id
                        else None,
                    },
                )
                message.ack()

            except Exception as exc:
                await session.rollback()
                logger.error(
                    "care_escalation_monitor.processing_error",
                    extra={
                        "encounter_id": str(event.encounter_id),
                        "error": str(exc),
                    },
                    exc_info=True,
                )
                message.nack()

    def _parse_event(self, message: Message) -> UrgencyFlagSetEvent:
        """Deserialise and validate the Pub/Sub message payload."""
        payload = json.loads(message.data.decode("utf-8"))
        return UrgencyFlagSetEvent(**payload)

    async def _get_or_create_escalation(
        self,
        session: AsyncSession,
        event: UrgencyFlagSetEvent,
        idempotency_key: str,
    ) -> CareEscalation | None:
        """Create a CareEscalation record using INSERT ... ON CONFLICT DO NOTHING.

        Returns the new CareEscalation record, or None if the idempotency key
        already exists (duplicate Pub/Sub delivery).
        
        Args:
            session: Active async database session
            event: Parsed URGENCY_FLAG_SET event
            idempotency_key: Idempotency key format: ESC-{encounter_id}
        
        Returns:
            CareEscalation instance if created, None if duplicate
        
        Raises:
            ValueError: If encounter not found in database
        """
        # Fetch encounter to determine current unit for on-call nurse lookup
        encounter: Encounter | None = await session.get(Encounter, event.encounter_id)
        if encounter is None:
            raise ValueError(f"Encounter {event.encounter_id} not found in DB")

        # Resolve on-call nurse for the encounter's current unit
        nurse = await self._resolve_on_call_nurse(session, encounter.current_unit)
        if nurse is None:
            # No on-call nurse configured — log warning and proceed without nurse FK
            logger.warning(
                "care_escalation_monitor.no_on_call_nurse",
                extra={
                    "encounter_id": str(event.encounter_id),
                    "unit": encounter.current_unit,
                },
            )

        escalation = CareEscalation(
            id=uuid.uuid4(),
            encounter_id=event.encounter_id,
            patient_id=event.patient_id,
            notified_nurse_user_id=nurse.id if nurse else None,
            status=CareEscalationStatus.PENDING,
            sent_at=datetime.now(tz=timezone.utc),
            escalated_to_supervisor=False,
            idempotency_key=idempotency_key,
        )

        # INSERT ... ON CONFLICT (idempotency_key) DO NOTHING
        session.add(escalation)
        try:
            await session.flush()  # Flushes to detect conflict before commit
        except IntegrityError:
            # Unique constraint violation → duplicate delivery
            await session.rollback()
            return None

        return escalation

    async def _resolve_on_call_nurse(
        self,
        session: AsyncSession,
        unit: str | None,
    ) -> AppUser | None:
        """Look up the on-call nurse assigned to the given unit.

        Query: app_user WHERE role=ON_CALL_NURSE AND unit=encounter.current_unit
        Returns the first matching AppUser, or None if no on-call nurse configured.
        
        Args:
            session: Active async database session
            unit: Hospital unit identifier (e.g., "ICU", "Emergency")
        
        Returns:
            AppUser instance of on-call nurse, or None if not found
        """
        if unit is None:
            return None

        result = await session.execute(
            select(AppUser).where(
                AppUser.role == ON_CALL_NURSE_ROLE,
                AppUser.unit == unit,
                AppUser.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def _publish_care_team_escalation(self, escalation: CareEscalation) -> None:
        """Publish CARE_TEAM_ESCALATION to the notification-requests Pub/Sub topic.

        PHI policy:
            Only UUIDs are included. The Notification Service resolves nurse phone
            from app_user at dispatch time (ADR-007).
        
        Args:
            escalation: The CareEscalation record created in the database
        """
        if escalation.notified_nurse_user_id is None:
            logger.warning(
                "care_escalation_monitor.escalation_no_nurse_notified",
                extra={"escalation_id": str(escalation.id)},
            )
            return

        message = CareTeamEscalationMessage(
            escalation_id=escalation.id,
            encounter_id=escalation.encounter_id,
            patient_id=escalation.patient_id,
            nurse_user_id=escalation.notified_nurse_user_id,
            idempotency_key=f"NOTIF-ESC-{escalation.id}",
        )
        payload = message.model_dump_json().encode("utf-8")
        future = self._publisher.publish(self._notification_topic, payload)
        future.result(timeout=10)  # Block until confirmed — within 60-second SLA budget
        
        logger.info(
            "care_escalation_monitor.notification_published",
            extra={
                "escalation_id": str(escalation.id),
                "notification_topic": self._notification_topic,
            },
        )
