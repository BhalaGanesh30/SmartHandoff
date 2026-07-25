"""Pydantic schemas for notification-requests Pub/Sub messages.

Pub/Sub message schema (US-064 Technical Notes):
    {
        "idempotency_key": "NOTIF-001",
        "type": "SMS",                          # or "EMAIL"
        "priority": "HIGH",                     # optional
        "recipient_id": "uuid-string",
        "template": "medication_reminder",
        "substitutions": {"patient_name": "John"}
    }

Validation:
    - `idempotency_key` required, max 255 chars
    - `type` must be "SMS" or "EMAIL"
    - `phone` required when type=SMS; `email` required when type=EMAIL
    - `template` required
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, model_validator


class NotificationTypeEnum(str, Enum):
    """Notification channel type — must match ORM NotificationType."""
    SMS = "SMS"
    EMAIL = "EMAIL"


class NotificationPriority(str, Enum):
    """Notification priority level."""
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class NotificationRequest(BaseModel):
    """Validated Pub/Sub `notification-requests` message payload."""

    idempotency_key: str = Field(..., max_length=255)
    type: NotificationTypeEnum
    priority: NotificationPriority = NotificationPriority.NORMAL
    recipient_id: str | None = None
    phone: str | None = Field(
        default=None,
        description="E.164 phone number, required when type=SMS",
    )
    email: EmailStr | None = Field(
        default=None,
        description="Recipient email, required when type=EMAIL",
    )
    template: str = Field(..., max_length=128)
    substitutions: dict[str, Any] = Field(default_factory=dict)
    urgency_override: bool = False

    @model_validator(mode="after")
    def _validate_recipient_address(self) -> "NotificationRequest":
        """Ensure phone is provided for SMS and email for EMAIL."""
        if self.type == NotificationTypeEnum.SMS and not self.phone:
            raise ValueError("phone is required when type=SMS")
        if self.type == NotificationTypeEnum.EMAIL and not self.email:
            raise ValueError("email is required when type=EMAIL")
        return self
