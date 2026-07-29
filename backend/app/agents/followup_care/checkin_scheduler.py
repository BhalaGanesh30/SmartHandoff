"""Check-in notification scheduler for the FollowUpCareAgent.

Implements US-041: creates a ScheduledNotification record (type=CHECK_IN_48H)
for patients with readmission risk_score >= CHECKIN_RISK_THRESHOLD (0.5)
after A03 discharge event processing.

PHI handling:
    Patient phone/email is NOT stored in scheduled_notification. It is resolved
    at dispatch time by the NotificationService from the encrypted patient record
    (ADR-007 minimum-necessary principle). Only patient_id (UUID) is stored here.

Idempotency:
    idempotency_key = f"CHK48-{encounter_id}" — prevents duplicate records on
    Pub/Sub at-least-once redelivery (ADR-001).

Design refs:
    US-041 AC Scenarios 1, 2, 3
    design.md §3.1 — Follow-up Care Agent: check-in scheduling
    ADR-001 — Pub/Sub at-least-once delivery; idempotency required
    ADR-007 — PHI minimization; phone/email not duplicated
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.scheduled_notification import (
    DeliveryStatus,
    NotificationChannel,
    NotificationType,
    ScheduledNotification,
)

logger = logging.getLogger(__name__)

# US-041 AC Scenario 1 / Scenario 2 — threshold for scheduling a check-in
# risk_score >= 0.5 → schedule check-in (MEDIUM/HIGH risk patients)
# risk_score < 0.5 → skip (LOW risk patients)
CHECKIN_RISK_THRESHOLD: float = 0.5

# US-041 Technical Notes — 48 hours post-discharge
CHECKIN_DELAY_HOURS: int = 48


async def maybe_schedule_48h_checkin(
    *,
    session: AsyncSession,
    encounter: Encounter,
    patient: Patient,
    risk_score: float,
) -> ScheduledNotification | None:
    """Create a CHECK_IN_48H ScheduledNotification if risk_score >= 0.5.

    This function is called AFTER the encounter risk score has been committed
    to the database. It creates a separate ScheduledNotification record that
    the NotificationService will poll for future dispatch.

    Args:
        session: Writable AsyncSession (Cloud SQL Primary). Should be a NEW
            session or transaction after the risk score commit.
        encounter: The discharged encounter with discharge_time populated.
        patient: The patient associated with the encounter.
        risk_score: The 30-day readmission probability from the ML Inference Service.

    Returns:
        The created ScheduledNotification, or None if:
            - risk_score < CHECKIN_RISK_THRESHOLD (0.5)
            - encounter.discharge_time is None
            - Duplicate already exists (idempotency)

    Raises:
        Exception: On database errors other than unique constraint violations.
    """
    # AC Scenario 2: Skip check-in for LOW risk patients (risk_score < 0.5)
    if risk_score < CHECKIN_RISK_THRESHOLD:
        logger.info(
            "check_in_skipped",
            extra={
                "encounter_id": str(encounter.id),
                "risk_score": risk_score,
                "reason": f"risk_score < {CHECKIN_RISK_THRESHOLD}",
            },
        )
        return None

    # Validate discharge_time is populated (set by coordinator agent on A03)
    if encounter.discharge_time is None:
        logger.error(
            "check_in_skipped_no_discharge_time",
            extra={"encounter_id": str(encounter.id)},
        )
        return None

    # Idempotency key format: CHK48-{encounter_id}
    # Prevents duplicate notifications on Pub/Sub redelivery (ADR-001)
    idempotency_key = f"CHK48-{encounter.id}"

    # AC Scenario 3: Resolve channel from patient preference (default: SMS)
    # patient.preferred_contact is a string field: "email", "sms", or None
    channel = (
        NotificationChannel.EMAIL
        if getattr(patient, "preferred_contact", None) == "email"
        else NotificationChannel.SMS
    )

    # AC Scenario 1: send_at computed from discharge_time, NOT current time
    # This ensures the check-in is scheduled relative to actual discharge,
    # not when the agent processes the message (which may be delayed)
    send_at: datetime = encounter.discharge_time + timedelta(hours=CHECKIN_DELAY_HOURS)

    # Create the notification record
    notification = ScheduledNotification(
        idempotency_key=idempotency_key,
        type=NotificationType.CHECK_IN_48H,
        send_at=send_at,
        channel=channel,
        delivery_status=DeliveryStatus.PENDING,
        patient_id=patient.id,
        encounter_id=encounter.id,
    )

    # Insert with idempotency handling
    session.add(notification)
    try:
        await session.flush()  # Flush to catch constraint violations before commit
    except IntegrityError:
        # Unique constraint violation on idempotency_key: already scheduled
        # This is expected on Pub/Sub redelivery — safe to ignore
        await session.rollback()
        logger.info(
            "check_in_already_scheduled",
            extra={
                "encounter_id": str(encounter.id),
                "idempotency_key": idempotency_key,
            },
        )
        return None
    except Exception:
        # Unexpected error — rollback and re-raise
        await session.rollback()
        raise

    logger.info(
        "check_in_scheduled",
        extra={
            "encounter_id": str(encounter.id),
            "risk_score": risk_score,
            "send_at": send_at.isoformat(),
            "channel": channel.value,
            "idempotency_key": idempotency_key,
        },
    )
    return notification
