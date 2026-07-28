"""add scheduled_notification table

Revision ID: v6s9r2q57o21
Revises: u5r8q1p46n10
Create Date: 2026-07-28

Design refs:
    US-041 — 48-hour post-discharge check-in scheduling
    design.md §6.1 DR-001 — all DDL via Alembic
    design.md §6.1 DR-005 — soft delete with deleted_at
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = "v6s9r2q57o21"
down_revision = "u5r8q1p46n10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create scheduled_notification table with enums and indexes."""
    
    # Create enums before the table
    notification_type = postgresql.ENUM(
        "CHECK_IN_48H",
        "MEDICATION_REMINDER",
        name="notificationtype",
        create_type=True,
    )
    notification_channel = postgresql.ENUM(
        "SMS",
        "EMAIL",
        name="notificationchannel",
        create_type=True,
    )
    delivery_status = postgresql.ENUM(
        "PENDING",
        "SENT",
        "OPTED_OUT",
        "FAILED",
        name="deliverystatus",
        create_type=True,
    )
    notification_type.create(op.get_bind(), checkfirst=True)
    notification_channel.create(op.get_bind(), checkfirst=True)
    delivery_status.create(op.get_bind(), checkfirst=True)

    # Create table
    op.create_table(
        "scheduled_notification",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column(
            "type",
            sa.Enum("CHECK_IN_48H", "MEDICATION_REMINDER", name="notificationtype"),
            nullable=False,
        ),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("SMS", "EMAIL", name="notificationchannel"),
            nullable=False,
        ),
        sa.Column(
            "delivery_status",
            sa.Enum("PENDING", "SENT", "OPTED_OUT", "FAILED", name="deliverystatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patient.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "encounter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("encounter.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # Add unique constraint on idempotency_key
    op.create_unique_constraint(
        "uq_scheduled_notification_idempotency_key",
        "scheduled_notification",
        ["idempotency_key"],
    )

    # Create indexes for polling query: WHERE send_at <= NOW() AND delivery_status = 'PENDING'
    op.create_index(
        "ix_scheduled_notification_send_at",
        "scheduled_notification",
        ["send_at"],
    )
    op.create_index(
        "ix_scheduled_notification_delivery_status",
        "scheduled_notification",
        ["delivery_status"],
    )
    op.create_index(
        "ix_scheduled_notification_patient_id",
        "scheduled_notification",
        ["patient_id"],
    )
    op.create_index(
        "ix_scheduled_notification_encounter_id",
        "scheduled_notification",
        ["encounter_id"],
    )


def downgrade() -> None:
    """Drop scheduled_notification table and enums."""
    
    # Drop table first
    op.drop_table("scheduled_notification")
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS deliverystatus")
    op.execute("DROP TYPE IF EXISTS notificationchannel")
    op.execute("DROP TYPE IF EXISTS notificationtype")
