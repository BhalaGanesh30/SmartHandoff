"""AgentTask model for SLA Monitor service.

Minimal ORM model with only the fields needed for SLA breach detection.
Matches the schema in backend/app/models/agent_task.py but excludes
unnecessary relationships and fields.

US-021: SLA Monitor queries only (id, encounter_id, agent_type, status,
         created_at, sla_breached, sla_threshold_minutes, supervisor_id).
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""
    pass


class AgentTask(Base):
    """Agent task execution record (read-only for SLA Monitor).

    SLA Monitor uses this model to query active tasks and update breach flags.
    This is a simplified model containing only fields required for SLA operations.
    """

    __tablename__ = "agent_task"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        nullable=False,
    )

    agent_type: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        server_default="queued",
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    # SLA fields — populated by SLAMonitor
    sla_threshold_minutes: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    sla_breached: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
    )

    # US-034: SLA escalation idempotency timestamp
    sla_escalation_sent_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when CHARGE_PHARMACIST_ESCALATION notification was last sent (US-034)",
    )

    # Supervisor assignment for escalation
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        nullable=True,
    )
