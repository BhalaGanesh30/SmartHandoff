"""Pydantic schemas for the care escalation acknowledgement endpoint.

Design refs:
    US-042 AC Scenarios 2, 4
    design.md §3.3 — FastAPI routers
    design.md §8.3 — RBAC
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.care_escalation import CareEscalationStatus


class CareEscalationAcknowledgeResponse(BaseModel):
    """Response body for PATCH /api/v1/care/escalations/{id}/acknowledge."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    encounter_id: UUID
    patient_id: UUID
    status: CareEscalationStatus
    sent_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: UUID | None
    escalated_to_supervisor: bool
    escalated_at: datetime | None
