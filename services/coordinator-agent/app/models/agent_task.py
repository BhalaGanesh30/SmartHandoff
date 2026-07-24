"""AgentTask stub model for coordinator-agent.

This is a minimal SQLAlchemy Table definition used for INSERT operations
in the coordinator service. Full ORM model lives in backend/app/models.
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy import MetaData

metadata = MetaData()

AgentTask = sa.Table(
    "agent_task",
    metadata,
    sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sa.Column("encounter_id", sa.UUID(as_uuid=True), nullable=False),
    sa.Column("agent_type", sa.String(64), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
    sa.Column("event_type", sa.String(8), nullable=False),
)

# Make columns accessible as attributes for easier access in code
AgentTask.id = AgentTask.c.id
AgentTask.encounter_id = AgentTask.c.encounter_id
AgentTask.agent_type = AgentTask.c.agent_type
AgentTask.status = AgentTask.c.status
AgentTask.event_type = AgentTask.c.event_type
