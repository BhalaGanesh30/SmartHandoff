"""US-040 TASK-001: Add appointment table

Adds the `appointment` table for follow-up care pathway records
created by the FollowUpCareAgent (US-040).

Columns:
    id               UUID PK
    encounter_id     UUID FK → encounter.id (CASCADE DELETE)
    appointment_type VARCHAR(40) NOT NULL — AppointmentType enum
    target_date      DATE NOT NULL
    status           VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED'
    assigned_user_id UUID FK → app_user.id (SET NULL) — care manager
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
    deleted_at       TIMESTAMPTZ NULL

Indexes:
    idx_appointment_encounter_id   — appointment.encounter_id (FK lookups)
    idx_appointment_assigned_user  — appointment.assigned_user_id (care manager workload queries)
    uq_appointment_encounter_type  — UNIQUE (encounter_id, appointment_type)

Revision ID: u5r8q1p46n10
Revises: t4q7p0l35o09
Create Date: 2026-07-28

Design refs:
    US-040 AC Scenarios 2, 3, 4 — appointment_type, target_date, status, assigned_user_id
    US-040 Technical Notes — status lifecycle; care manager assignment
    design.md §6.1 DR-001 — all DDL via Alembic
    design.md §6.1 DR-005 — soft delete (deleted_at)
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = "u5r8q1p46n10"
down_revision: Union[str, None] = "t4q7p0l35o09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create appointment table with indexes and constraints."""
    op.create_table(
        "appointment",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "encounter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("encounter.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "appointment_type",
            sa.String(40),
            nullable=False,
            comment="AppointmentType enum value",
        ),
        sa.Column(
            "target_date",
            sa.Date(),
            nullable=False,
            comment="Calendar date by which follow-up must occur",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="SCHEDULED",
            comment="AppointmentStatus lifecycle value",
        ),
        sa.Column(
            "assigned_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
            comment="Care manager assigned for HIGH-risk follow-up; NULL for MEDIUM/LOW",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Soft-delete timestamp (DR-005); NULL = active",
        ),
    )

    # Create indexes for query performance
    op.create_index(
        "idx_appointment_encounter_id",
        "appointment",
        ["encounter_id"],
    )
    op.create_index(
        "idx_appointment_assigned_user",
        "appointment",
        ["assigned_user_id"],
    )
    op.create_index(
        "idx_appointment_deleted_at",
        "appointment",
        ["deleted_at"],
    )

    # Create unique constraint to prevent duplicate appointments per encounter/type
    op.create_unique_constraint(
        "uq_appointment_encounter_type",
        "appointment",
        ["encounter_id", "appointment_type"],
    )


def downgrade() -> None:
    """Drop appointment table and all associated indexes/constraints."""
    op.drop_constraint("uq_appointment_encounter_type", "appointment", type_="unique")
    op.drop_index("idx_appointment_deleted_at", table_name="appointment")
    op.drop_index("idx_appointment_assigned_user", table_name="appointment")
    op.create_index("idx_appointment_encounter_id", table_name="appointment")
    op.drop_table("appointment")
