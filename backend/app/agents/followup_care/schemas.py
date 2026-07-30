"""Pydantic schemas for FollowUpCareAgent structured output.

Design refs:
    US-039 AC Scenarios 1, 2
    ADR-004 — structured Pydantic output enforced for all agents
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RiskTier(str, Enum):
    """Risk tier classification for readmission probability."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class RiskAssessmentResult(BaseModel):
    """Structured output produced after completing a risk assessment task."""

    encounter_id: str = Field(..., description="UUID of the assessed encounter")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Predicted 30-day readmission probability")
    risk_tier: RiskTier
    model_version: str
    contributing_factors: list[dict] = Field(
        default_factory=list,
        description="Top 5 SHAP contributing factors returned by the ML Inference Service",
    )
    db_updated: bool = False
    agent_task_id: str | None = None
    checkin_scheduled: bool = Field(
        default=False,
        description="Whether a 48-hour check-in notification was scheduled (US-041)",
    )
    scheduled_notification_id: str | None = Field(
        default=None,
        description="UUID of the created ScheduledNotification record (US-041)",
    )


class CareManagerAlertPayload(BaseModel):
    """Pub/Sub message payload for CARE_MANAGER_ALERT notifications.

    Published to the `notification-requests` topic when a HIGH-risk patient
    is discharged. Consumed by the Notification Service (AIR-040).

    Fields match US-040 AC Scenario 1 payload specification exactly.
    """

    alert_type: str = Field(default="CARE_MANAGER_ALERT", description="Notification type discriminator")
    encounter_id: str = Field(..., description="UUID of the high-risk encounter")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Predicted 30-day readmission probability")
    risk_tier: str = Field(default="HIGH", description="Risk tier — always HIGH for this alert type")
    required_followup_days: int = Field(..., description="Days within which follow-up must occur (=7 for HIGH)")
    appointment_id: str = Field(..., description="UUID of the created appointment record")
    idempotency_key: str = Field(
        ...,
        description="Unique key to prevent duplicate alert sends (AIR-040). "
        "Format: CARE_MANAGER_ALERT:{encounter_id}:{appointment_id}",
    )
