"""add care_escalation table

Revision ID: w7t0s3r68p22
Revises: v6s9r2q57o21
Create Date: 2026-07-28

Design refs:
    US-042 — Care escalation monitoring for urgent patient flags
    design.md §6.1 DR-001 — all DDL via Alembic
    design.md §6.1 DR-005 — soft delete with deleted_at
    ADR-001 — idempotency key prevents duplicate escalations on Pub/Sub redelivery
    ADR-007 — PHI containment (no patient PHI in escalation table)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = "w7t0s3r68p22"
down_revision = "v6s9r2q57o21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create care_escalation table with status enum and indexes."""
    
    # Create enum before the table
    care_escalation_status = postgresql.ENUM(
        "PENDING",
        "ACKNOWLEDGED",
        "ESCALATED_TO_SUPERVISOR",
        name="care_escalation_status",
        create_type=True,
    )
    care_escalation_status.create(op.get_bind(), checkfirst=True)

    # Create table
    op.create_table(
        "care_escalation",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Surrogate primary key",
        ),
        sa.Column(
            "encounter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("encounter.id", ondelete="RESTRICT"),
            nullable=False,
            comment="FK to encounter that generated the urgency flag",
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patient.id", ondelete="RESTRICT"),
            nullable=False,
            comment="FK to patient; used for RBAC scope checks",
        ),
        sa.Column(
            "notified_nurse_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to the on-call nurse who received the initial SMS alert",
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACKNOWLEDGED", "ESCALATED_TO_SUPERVISOR", name="care_escalation_status"),
            nullable=False,
            server_default="PENDING",
            comment="Current lifecycle state of the escalation",
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="UTC timestamp when the initial CARE_TEAM_ESCALATION notification was published",
        ),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC timestamp when the nurse acknowledged (via PATCH endpoint). Null until acknowledged",
        ),
        sa.Column(
            "acknowledged_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to the app_user who acknowledged. Null until acknowledged",
        ),
        sa.Column(
            "escalated_to_supervisor",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="True after the 15-minute SLA is breached and a SUPERVISOR_ESCALATION is published",
        ),
        sa.Column(
            "escalated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC timestamp when the supervisor escalation was triggered. Null until escalated",
        ),
        sa.Column(
            "idempotency_key",
            sa.String(64),
            nullable=False,
            comment="Idempotency key preventing duplicate escalations on Pub/Sub redelivery. Format: ESC-{encounter_id}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Soft-delete timestamp (DR-005). Active records have deleted_at=NULL",
        ),
    )

    # Add unique constraint on idempotency_key
    op.create_unique_constraint(
        "uq_care_escalation_idempotency_key",
        "care_escalation",
        ["idempotency_key"],
    )

    # Create indexes for query performance
    op.create_index(
        "ix_care_escalation_encounter_id",
        "care_escalation",
        ["encounter_id"],
    )
    op.create_index(
        "ix_care_escalation_patient_id",
        "care_escalation",
        ["patient_id"],
    )


def downgrade() -> None:
    """Drop care_escalation table and enum."""
    
    # Drop table first
    op.drop_table("care_escalation")
    
    # Drop enum
    op.execute("DROP TYPE IF EXISTS care_escalation_status")
