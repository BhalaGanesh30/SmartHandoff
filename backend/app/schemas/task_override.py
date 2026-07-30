"""Task override request/response schemas.

US-034/TASK-005: Manual task completion endpoint schemas.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TaskOverrideRequest(BaseModel):
    """Request body for PATCH /api/v1/encounters/{id}/tasks/{task_id}/override.

    US-034 Scenario 4: manual completion by charge pharmacist.
    """

    note: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Free-text justification for manual override (stored in audit log).",
        json_schema_extra={
            "examples": ["Reconciliation completed offline with attending; documented in EHR."]
        },
    )


class TaskOverrideResponse(BaseModel):
    """Response body for successful task override."""

    task_id: UUID
    encounter_id: UUID
    agent_type: str
    status: str  # COMPLETED
    completed_at: datetime
    sla_escalation_sent_at: datetime | None  # always None after override
    overridden_by: UUID  # actor_id
    note: str

    model_config = {"from_attributes": True}
