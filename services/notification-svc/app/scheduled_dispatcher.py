"""Scheduled notification polling dispatcher — US-041.

Runs every 5 minutes (APScheduler AsyncIOScheduler) to query
`scheduled_notification` for rows where:
    send_at <= NOW()  AND  delivery_status = PENDING

For each due notification:
    1. Check patient opt-out flag  → mark OPTED_OUT and continue
    2. Decrypt patient contact details (phone / email) from ORM EncryptedString
    3. Dispatch via Twilio (SMS) or SendGrid (email)
    4. Update delivery_status to SENT on success, FAILED on error

PHI handling:
    Only patient.first_name appears in the message body.
    Logs contain only scheduled_notification.id and encounter_id (no PHI).
    Patient phone / email are never written to structured logs (ADR-007, AIR-021).

Design refs:
    US-041 AC Scenarios 3, 4
    US-041 Technical Notes — poll every 5 min; PHI minimisation (first_name only)
    design.md §3.1 — Notification Service
    AIR-040 — dispatch via Twilio (SMS) or SendGrid (email)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# US-041 Technical Notes: poll every 5 minutes
POLL_INTERVAL_SECONDS: int = 300
POLL_BATCH_LIMIT: int = 100


async def dispatch_due_notifications(session_factory: async_sessionmaker) -> None:
    """Query and dispatch all scheduled notifications with send_at <= now().

    Called by APScheduler every POLL_INTERVAL_SECONDS seconds.
    
    Args:
        session_factory: Async SQLAlchemy session factory for database access.
    """
    # Import models here to avoid circular import issues
    # These models are in the backend app, shared via database
    from app.models.scheduled_notification import (
        DeliveryStatus,
        NotificationChannel,
        ScheduledNotification,
    )
    from app.models.patient import Patient
    from app.services.sms_service import send_checkin_sms
    from app.services.email_service import send_checkin_email
    
    now = datetime.now(tz=timezone.utc)

    async with session_factory() as session:
        result = await session.execute(
            select(ScheduledNotification)
            .options(joinedload(ScheduledNotification.patient))
            .where(
                ScheduledNotification.send_at <= now,
                ScheduledNotification.delivery_status == DeliveryStatus.PENDING,
                ScheduledNotification.deleted_at.is_(None),
            )
            .order_by(ScheduledNotification.send_at.asc())
            .limit(POLL_BATCH_LIMIT)
        )
        due: list[ScheduledNotification] = list(result.scalars().all())

    logger.info(
        "scheduled_dispatch_poll",
        extra={"due_count": len(due), "poll_time": now.isoformat()}
    )

    for notification in due:
        await _process_notification(
            session_factory=session_factory,
            notification=notification,
        )


async def _process_notification(
    *,
    session_factory: async_sessionmaker,
    notification,  # ScheduledNotification type
) -> None:
    """Dispatch a single ScheduledNotification and update its delivery_status.
    
    Args:
        session_factory: Async SQLAlchemy session factory for database access.
        notification: ScheduledNotification instance with patient relationship loaded.
    """
    # Import models here to avoid circular imports
    from app.models.scheduled_notification import DeliveryStatus, NotificationChannel
    from app.services.sms_service import send_checkin_sms
    from app.services.email_service import send_checkin_email
    
    patient = notification.patient

    # US-041 AC Scenario 4 — opt-out check before any dispatch
    if patient.notification_opt_out:
        await _update_status(
            session_factory=session_factory,
            notification_id=notification.id,
            new_status=DeliveryStatus.OPTED_OUT,
        )
        logger.info(
            "notification_opted_out",
            extra={
                "scheduled_notification_id": str(notification.id),
                "encounter_id": str(notification.encounter_id),
            },
        )
        return

    # Decrypt contact details via ORM EncryptedString (transparent to caller)
    first_name: str = patient.first_name  # decrypted by SQLAlchemy TypeDecorator
    care_team_number: str = os.environ.get("CARE_TEAM_CONTACT_NUMBER", "1-800-CARE-TEAM")

    try:
        if notification.channel == NotificationChannel.SMS:
            phone: str = patient.phone  # decrypted
            await send_checkin_sms(
                to_phone=phone,
                first_name=first_name,
                care_team_number=care_team_number,
            )
        else:
            email: str = patient.email  # decrypted
            await send_checkin_email(
                to_email=email,
                first_name=first_name,
                care_team_number=care_team_number,
            )

        await _update_status(
            session_factory=session_factory,
            notification_id=notification.id,
            new_status=DeliveryStatus.SENT,
        )
        logger.info(
            "notification_sent",
            extra={
                "scheduled_notification_id": str(notification.id),
                "encounter_id": str(notification.encounter_id),
                "channel": notification.channel.value,
            },
        )

    except Exception as exc:
        await _update_status(
            session_factory=session_factory,
            notification_id=notification.id,
            new_status=DeliveryStatus.FAILED,
        )
        logger.error(
            "notification_dispatch_failed",
            extra={
                "scheduled_notification_id": str(notification.id),
                "encounter_id": str(notification.encounter_id),
                "error": str(exc),
            },
        )


async def _update_status(
    *,
    session_factory: async_sessionmaker,
    notification_id,
    new_status,  # DeliveryStatus type
) -> None:
    """Update delivery_status in a separate DB session to avoid long-lived transactions.
    
    Args:
        session_factory: Async SQLAlchemy session factory for database access.
        notification_id: UUID of the ScheduledNotification to update.
        new_status: New DeliveryStatus enum value.
    """
    from app.models.scheduled_notification import ScheduledNotification
    
    async with session_factory() as session:
        async with session.begin():
            result = await session.get(ScheduledNotification, notification_id)
            if result:
                result.delivery_status = new_status


def register_scheduled_dispatcher(
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker
) -> None:
    """Register the polling job with an existing APScheduler instance.

    Call this from notification-svc/app/main.py during startup.
    
    Args:
        scheduler: APScheduler AsyncIOScheduler instance.
        session_factory: Async SQLAlchemy session factory for database access.
    """
    scheduler.add_job(
        dispatch_due_notifications,
        trigger="interval",
        seconds=POLL_INTERVAL_SECONDS,
        kwargs={"session_factory": session_factory},
        id="scheduled_notification_dispatcher",
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info(
        "scheduled_dispatcher_registered",
        extra={"poll_interval_seconds": POLL_INTERVAL_SECONDS},
    )
