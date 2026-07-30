"""Pydantic payload schemas for Pub/Sub escalation messages.

US-021/TASK-004: SUPERVISOR_ESCALATION schema
US-034/TASK-004: CHARGE_PHARMACIST_ESCALATION schema
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChargePharmacistEscalationPayload(BaseModel):
    """Pub/Sub message payload for CHARGE_PHARMACIST_ESCALATION.

    Published to the ``notification-requests`` topic by ``MedRecSLAMonitor``
    when a MEDICATION_RECONCILIATION AgentTask remains non-COMPLETED ≥ 24 hours
    after encounter.admit_time.

    US-034 Scenario 1 required fields: encounter_id, patient_unit, hours_elapsed.
    """

    notification_type: Literal["CHARGE_PHARMACIST_ESCALATION"] = (
        "CHARGE_PHARMACIST_ESCALATION"
    )
    priority: Literal["HIGH"] = "HIGH"
    encounter_id: UUID
    task_id: UUID
    patient_unit: str
    hours_elapsed: int
    sent_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
