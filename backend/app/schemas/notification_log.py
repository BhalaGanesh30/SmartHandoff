"""Response schemas for the notification audit log API.

PHI minimisation (US-067 Technical Notes):
    - ``recipient_phone`` and ``recipient_email`` are NEVER returned.
    - Only ``recipient_phone_hash`` and ``recipient_email_hash`` (SHA-256 hex)
      are included for correlation purposes.
    - No patient name, DOB, or MRN in any field.

Design refs:
    US-067 AC Scenario 1, US-067 Technical Notes, ADR-007, SEC-006.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationLogItem(BaseModel):
    """Single notification delivery record returned by the audit log API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(description="Notification record UUID")
    notification_type: str = Field(
        alias="type",
        description="Notification type e.g. 'medication_reminder'",
    )
    channel: str = Field(description="SMS or EMAIL")
    sent_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when dispatch was attempted (None for OPTED_OUT)",
    )
    delivery_status: str = Field(
        description="PENDING | SENT | DELIVERED | FAILED | OPTED_OUT",
    )
    template_name: str = Field(description="SendGrid template key used for this notification")
    urgency_override: bool = Field(
        description="True if notification bypassed patient opt-out",
    )
    recipient_phone_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 hash of recipient phone number (no plaintext PHI)",
    )
    recipient_email_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 hash of recipient email address (no plaintext PHI)",
    )


class NotificationLogResponse(BaseModel):
    """Paginated notification audit log response."""

    encounter_id: UUID
    total: int = Field(description="Total number of notification records for this encounter")
    items: list[NotificationLogItem]
