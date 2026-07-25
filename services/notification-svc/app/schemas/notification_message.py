"""Pydantic v2 schema for the Notification Pub/Sub message payload.

This schema represents the JSON structure published to the Pub/Sub
``notifications`` topic and consumed by the NotificationService dispatcher.

Design refs:
    US-064 DoD (idempotency_key, type, channel, template_name, recipient_id)
    US-067 DoD (urgency_override — agent-set only; bypasses patient opt-out)
    ADR-001 (Pub/Sub event bus)
    design.md §3.1 (Notification Service component)

Security note:
    ``urgency_override`` is set exclusively by sending agents (Transition
    Coordinator, Follow-up Care Agent). The patient portal endpoint
    ``PATCH /api/v1/portal/preferences`` does NOT expose this field.
"""
from __future__ import annotations

import enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationChannel(str, enum.Enum):
    SMS = "SMS"
    EMAIL = "EMAIL"


class NotificationMessage(BaseModel):
    """Pub/Sub message payload for a notification dispatch request.

    Publishers:
        - TransitionCoordinatorAgent
        - FollowUpCareAgent
        - PatientCommunicationAgent

    Consumer:
        - NotificationService (notification-service Cloud Run service)
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    idempotency_key: str = Field(
        ...,
        description="Unique key; duplicate messages with same key are discarded (US-064 Scenario 2)",
    )
    notification_type: str = Field(
        ...,
        alias="type",
        description="Notification type e.g. 'medication_reminder', 'CARE_TEAM_URGENCY_ALERT'",
    )
    channel: NotificationChannel = Field(
        ...,
        description="Dispatch channel: SMS or EMAIL",
    )
    recipient_id: UUID = Field(
        ...,
        description="patient.id — used to look up opt-out preference and hashed recipient contact",
    )
    encounter_id: Optional[UUID] = Field(
        default=None,
        description="encounter.id — linked encounter for audit log query (US-067 Scenario 1)",
    )
    template_name: str = Field(
        ...,
        description="SendGrid Dynamic Template key (maps to config/sendgrid_templates.yaml)",
    )
    template_data: dict = Field(
        default_factory=dict,
        description="Pydantic-validated substitution payload (US-066 SendGrid schemas)",
    )
    urgency_override: bool = Field(
        default=False,
        description=(
            "When True, notification bypasses patient opt-out (US-067 Scenario 3). "
            "MUST be set only by authorised sending agents — never by patient-facing APIs."
        ),
    )
