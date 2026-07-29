"""SQLAlchemy ORM model for the `scheduled_notification` table.

Tracks every notification that the FollowUpCareAgent schedules for
future dispatch (e.g., 48-hour post-discharge check-in).

Delivery lifecycle:
    PENDING → SENT         (dispatched successfully by NotificationService)
           → OPTED_OUT     (patient.notification_opt_out=True at dispatch time)
           → FAILED        (all retries exhausted — manual care-team follow-up)

Idempotency key format: CHK48-{encounter_id}
    Ensures the 48-hour check-in is created exactly once per encounter even
    if the A03 Pub/Sub message is redelivered (ADR-001 at-least-once delivery).

Design refs:
    US-041 AC Scenarios 1, 4 — type, send_at, channel, delivery_status
    US-041 Technical Notes — send_at = encounter.discharge_time + timedelta(hours=48)
    design.md §6.1 DR-001 — all DDL via Alembic
    design.md §6.1 DR-005 — soft delete (deleted_at)
    ADR-007 — PHI not duplicated here; phone/email resolved at dispatch time
               from the encrypted patient record
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NotificationType(str, Enum):
    """Notification category types."""

    CHECK_IN_48H = "CHECK_IN_48H"
    MEDICATION_REMINDER = "MEDICATION_REMINDER"


class NotificationChannel(str, Enum):
    """Delivery channel for notifications."""

    SMS = "SMS"
    EMAIL = "EMAIL"


class DeliveryStatus(str, Enum):
    """Notification delivery lifecycle states."""

    PENDING = "PENDING"
    SENT = "SENT"
    OPTED_OUT = "OPTED_OUT"
    FAILED = "FAILED"


class ScheduledNotification(Base):
    """One row per future notification to be dispatched by the NotificationService.
    
    Used by FollowUpCareAgent to schedule post-discharge check-ins and medication
    reminders. The NotificationService polls this table for notifications where
    send_at <= NOW() AND delivery_status = 'PENDING'.
    
    Attributes:
        id: UUID primary key
        idempotency_key: Prevents duplicate creation on Pub/Sub redelivery
        type: Notification category (CHECK_IN_48H, MEDICATION_REMINDER)
        send_at: UTC timestamp for dispatch (e.g., discharge_time + 48 hours)
        channel: Dispatch channel (SMS, EMAIL) from patient.preferred_contact
        delivery_status: Current state (PENDING, SENT, OPTED_OUT, FAILED)
        patient_id: FK to patient (for opt-out check)
        encounter_id: FK to encounter (for audit traceability)
        deleted_at: Soft delete timestamp (DR-005)
        created_at: Record creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "scheduled_notification"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="CHK48-{encounter_id} — prevents duplicate creation on Pub/Sub redelivery",
    )
    type: Mapped[NotificationType] = mapped_column(
        nullable=False,
        comment="Notification category; CHECK_IN_48H for US-041",
    )
    send_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="UTC timestamp at which the NotificationService should dispatch; "
                "= encounter.discharge_time + 48 hours",
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        nullable=False,
        comment="Dispatch channel resolved from patient.preferred_contact at creation time",
    )
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        nullable=False,
        default=DeliveryStatus.PENDING,
        index=True,
        comment="Updated by NotificationService after dispatch attempt",
    )

    # Foreign keys
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patient.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("encounter.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Soft delete (DR-005)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships (lazy="raise" to prevent N+1 in polling loop — use explicit joinedload)
    patient = relationship("Patient", lazy="raise")
    encounter = relationship("Encounter", lazy="raise")
