"""Notification ORM model — tracks every SMS and email dispatch attempt.

DR-002 / ADR-007: `phone_or_email` is encrypted with AES-256-GCM via the
shared `EncryptedString` custom SQLAlchemy type. The raw value is never
stored in plaintext.

Idempotency strategy (US-064 AC Scenario 2):
    The `idempotency_key` column carries a UNIQUE constraint.
    The dispatcher uses:
        INSERT INTO notification ... ON CONFLICT (idempotency_key) DO NOTHING
    to guarantee at-most-once dispatch even under Pub/Sub at-least-once delivery.

Delivery status lifecycle:
    PENDING → SENT (Twilio/SendGrid accepted)
             → DELIVERED (Twilio delivery webhook received)
             → FAILED (all 3 retry attempts exhausted)
    PENDING → OPTED_OUT (patient.notification_opt_out=True, non-urgent)

Design refs:
    US-064 DoD, US-067 DoD, ADR-007, design.md §3.1 (Notification Service component)
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.encryption import EncryptedString


class NotificationType(str, enum.Enum):
    """Notification channel type — matches Pub/Sub message schema `type` field."""

    SMS = "SMS"
    EMAIL = "EMAIL"


class NotificationStatus(str, enum.Enum):
    """Delivery lifecycle states.

    PENDING     — created, not yet dispatched.
    SENT        — Twilio/SendGrid accepted the request (2xx response).
    DELIVERED   — Twilio delivery webhook confirmed delivery.
    FAILED      — All retry attempts exhausted; CARE_TEAM_ALERT published.
    OPTED_OUT   — Patient opt-out suppressed dispatch (non-urgent only).
    """

    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    OPTED_OUT = "OPTED_OUT"


class Notification(Base):
    """One row per notification dispatch attempt.

    Idempotency is enforced at the DB level via the UNIQUE constraint on
    `idempotency_key`. The application layer uses
    ``INSERT ... ON CONFLICT (idempotency_key) DO NOTHING`` so that
    Pub/Sub message redeliveries are safely ignored without a SELECT-first
    round-trip.
    """

    __tablename__ = "notification"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Surrogate PK — stable identifier for webhook correlation",
    )

    # -----------------------------------------------------------------------
    # Idempotency
    # -----------------------------------------------------------------------
    idempotency_key: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Caller-supplied idempotency key from Pub/Sub message (US-064 AC2)",
    )

    # -----------------------------------------------------------------------
    # Routing
    # -----------------------------------------------------------------------
    type: Mapped[NotificationType] = mapped_column(
        sa.Enum(NotificationType, name="notification_type"),
        nullable=False,
        comment="Dispatch channel: SMS or EMAIL",
    )

    recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("patient.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="FK to patient — used for opt-out check and audit correlation",
    )

    phone_or_email: Mapped[str | None] = mapped_column(
        EncryptedString(length=512),
        nullable=True,
        comment="AES-256-GCM encrypted recipient address (ADR-007 PHI field)",
    )

    template: Mapped[str] = mapped_column(
        sa.String(128),
        nullable=False,
        comment="Template identifier, e.g. medication_reminder (Twilio) or d-xxx (SendGrid)",
    )

    substitutions: Mapped[dict | None] = mapped_column(
        sa.JSON,
        nullable=True,
        comment="Template variable substitution map from Pub/Sub message",
    )

    # -----------------------------------------------------------------------
    # Delivery status
    # -----------------------------------------------------------------------
    delivery_status: Mapped[NotificationStatus] = mapped_column(
        sa.Enum(NotificationStatus, name="notification_status"),
        nullable=False,
        default=NotificationStatus.PENDING,
        server_default=NotificationStatus.PENDING.value,
        index=True,
        comment="Delivery lifecycle state (US-067)",
    )

    urgency_override: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("FALSE"),
        comment="True if set by sending agent to bypass patient opt-out (US-067)",
    )

    twilio_message_sid: Mapped[str | None] = mapped_column(
        sa.String(64),
        nullable=True,
        comment="Twilio MessageSid returned by messages.create(); used for webhook correlation",
    )

    sendgrid_message_id: Mapped[str | None] = mapped_column(
        sa.String(128),
        nullable=True,
        comment="SendGrid X-Message-Id response header value",
    )

    retry_count: Mapped[int] = mapped_column(
        sa.SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of dispatch retry attempts completed",
    )

    last_error: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Last error message when status=FAILED",
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when Twilio/SendGrid accepted the request",
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Timestamp from Twilio delivery webhook (AC Scenario 3)",
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.UniqueConstraint("idempotency_key", name="uq_notification_idempotency_key"),
        sa.Index("ix_notification_recipient_status", "recipient_id", "delivery_status"),
        sa.Index("ix_notification_twilio_sid", "twilio_message_sid"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Notification id={self.id} type={self.type.value} "
            f"delivery_status={self.delivery_status.value} key={self.idempotency_key!r}>"
        )
