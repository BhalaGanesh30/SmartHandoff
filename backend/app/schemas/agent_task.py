"""Pydantic response schemas for AgentTask API endpoints.

US-021 Scenario 2: Response must include id, agent_type, status, start_time,
completed_time, sla_threshold_minutes, sla_breached.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.config.sla_loader import load_sla_config


class AgentTaskResponse(BaseModel):
    """Response schema for a single AgentTask.

    All seven fields required by US-021 Scenario 2 are present.
    `sla_threshold_minutes` is backfilled from SLAConfig if NULL in DB
    (handles tasks created before TASK-002 migration).
    """

    id: UUID
    agent_type: str
    status: str
    start_time: datetime = Field(alias="created_at")
    completed_time: datetime | None = Field(None, alias="completed_at")
    sla_threshold_minutes: int | None
    sla_breached: bool

    model_config = {"populate_by_name": True, "from_attributes": True}

    @model_validator(mode="after")
    def _backfill_sla_threshold(self) -> "AgentTaskResponse":
        """Backfill sla_threshold_minutes from SLAConfig if not yet set in DB."""
        if self.sla_threshold_minutes is None:
            config = load_sla_config()
            self.sla_threshold_minutes = config.threshold_for(self.agent_type)
        return self


class AgentTaskListResponse(BaseModel):
    """Paginated list of AgentTask records for an encounter."""

    encounter_id: UUID
    tasks: list[AgentTaskResponse]
    total: int
