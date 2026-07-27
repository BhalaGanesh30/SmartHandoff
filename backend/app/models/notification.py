"""Notification ORM model — read-only view for audit log queries.

This model maps to the `notification` table owned by the notification-service
microservice. The backend uses this model for read-only queries (US-067 TASK-004:
notification audit log API).

PHI minimisation:
    - `phone_or_email` is encrypted (EncryptedString type) but this model does
      NOT decrypt it — the encrypted bytes are never exposed via the API.
    - `recipient_phone_hash` and `recipient_email_hash` are SHA-256 hashes of
      the plaintext values, safe to return in API responses.

Design refs:
    US-067 AC Scenario 1, design.md §3.1 (Notification Service), ADR-006, SEC-006.

Note:
    Write operations (INSERT, UPDATE) should only be performed by the notification
    service. This model is provided for read-only access by the backend API.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationType(str, enum.Enum):
    """Notification channel type."""

    SMS = "SMS"
    EMAIL = "EMAIL"


class NotificationStatus(str, enum.Enum):
    """Delivery lifecycle states."""

    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    OPTED_OUT = "OPTED_OUT"


class Notification(Base):
    """Read-only model for notification records.

    Maps to the `notification` table managed by the notification-service.
    Used by the backend for audit log queries (GET /api/v1/notifications).
    """

    __tablename__ = "notification"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )

    type: Mapped[NotificationType] = mapped_column(
        sa.Enum(NotificationType, name="notification_type"),
        nullable=False,
    )

    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        nullable=True,
    )

    template: Mapped[str] = mapped_column(
        sa.String(128),
        nullable=False,
    )

    delivery_status: Mapped[NotificationStatus] = mapped_column(
        sa.Enum(NotificationStatus, name="notification_status"),
        nullable=False,
        default=NotificationStatus.PENDING,
    )

    urgency_override: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
    )

    recipient_phone_hash: Mapped[str | None] = mapped_column(
        sa.String(64),
        nullable=True,
        comment="SHA-256 hash of recipient phone (safe to return in API)",
    )

    recipient_email_hash: Mapped[str | None] = mapped_column(
        sa.String(64),
        nullable=True,
        comment="SHA-256 hash of recipient email (safe to return in API)",
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
