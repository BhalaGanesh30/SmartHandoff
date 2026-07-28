"""Encounter model for SLA Monitor service.

Minimal ORM model with only the fields needed for medication reconciliation
admission SLA checking (US-034).

Matches the schema in backend/app/models/encounter.py but excludes
unnecessary relationships and fields.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent_task import Base


class Encounter(Base):
    """Hospital encounter (admission episode) — read-only for SLA Monitor.

    US-034: MedRecSLAMonitor uses this model to join to AgentTask and retrieve
    admit_date for 24-hour admission SLA calculations.
    """

    __tablename__ = "encounter"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
    )

    # US-034: SLA start time for medication reconciliation admission SLA
    admit_date: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Admission timestamp; used as SLA start for US-034 24-hour medication reconciliation requirement",
    )

    # US-034: Required for escalation payload (patient_unit)
    unit: Mapped[str | None] = mapped_column(
        sa.String(64),
        nullable=True,
        comment="Current unit assignment (e.g., '3N', 'ICU-2')",
    )
