"""Pydantic schemas for URGENCY_FLAG_SET and CARE_TEAM_ESCALATION events.

Design refs:
    US-042 Technical Notes — event envelope formats
    design.md §3.2 — Pydantic structured output per agent pattern
    ADR-001 — Pub/Sub event contracts
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class UrgencyFlagSetEvent(BaseModel):
    """Inbound Pub/Sub event published by the chatbot agent (EP-008).
    
    Attributes:
        event_type: Always "URGENCY_FLAG_SET"
        encounter_id: UUID of the encounter where urgency flag was set
        patient_id: UUID of the patient
        chatbot_transcript_id: UUID of the chatbot conversation that triggered the flag
        urgency_flag_set_at: UTC timestamp when the chatbot set urgency_flag=True
    """

    event_type: Literal["URGENCY_FLAG_SET"]
    encounter_id: UUID
    patient_id: UUID
    chatbot_transcript_id: UUID
    urgency_flag_set_at: datetime = Field(
        description="UTC timestamp when the chatbot set urgency_flag=True"
    )


class CareTeamEscalationMessage(BaseModel):
    """Outbound message published to the notification-requests Pub/Sub topic.

    PHI policy:
        nurse_user_id is a UUID reference only. The Notification Service resolves
        the nurse's phone number from app_user at dispatch time (ADR-007).
    
    Attributes:
        event_type: Always "CARE_TEAM_ESCALATION"
        escalation_id: UUID of the created care_escalation record
        encounter_id: UUID of the encounter that triggered the escalation
        patient_id: UUID of the patient
        nurse_user_id: UUID of the on-call nurse to notify
        channel: Notification channel, always "SMS"
        idempotency_key: Format: NOTIF-ESC-{escalation_id}. Prevents duplicate SMS on notification redelivery
    """

    event_type: Literal["CARE_TEAM_ESCALATION"] = "CARE_TEAM_ESCALATION"
    escalation_id: UUID
    encounter_id: UUID
    patient_id: UUID
    nurse_user_id: UUID
    channel: Literal["SMS"] = "SMS"
    idempotency_key: str = Field(
        description="Format: NOTIF-ESC-{escalation_id}. Prevents duplicate SMS on notification redelivery"
    )
