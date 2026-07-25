"""Create notification table.

Revision ID: 0001
Revises:
Create Date: 2026-07-16

US-064: notification table for SMS/email dispatch tracking with
idempotency enforcement via UNIQUE constraint on idempotency_key.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column(
            "type",
            sa.Enum("SMS", "EMAIL", name="notification_type"),
            nullable=False,
        ),
        sa.Column("recipient_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("phone_or_email", sa.String(512), nullable=True,
                  comment="AES-256-GCM encrypted (ADR-007)"),
        sa.Column("template", sa.String(128), nullable=False),
        sa.Column("substitutions", sa.JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "SENT", "DELIVERED", "FAILED", "OPTED_OUT",
                name="notification_status",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("twilio_message_sid", sa.String(64), nullable=True),
        sa.Column("sendgrid_message_id", sa.String(128), nullable=True),
        sa.Column("retry_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_notification_idempotency_key", "notification", ["idempotency_key"]
    )
    op.create_index(
        "ix_notification_recipient_status", "notification", ["recipient_id", "status"]
    )
    op.create_index(
        "ix_notification_twilio_sid", "notification", ["twilio_message_sid"]
    )
    op.create_foreign_key(
        "fk_notification_patient",
        "notification",
        "patient",
        ["recipient_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_notification_patient", "notification", type_="foreignkey")
    op.drop_index("ix_notification_twilio_sid", table_name="notification")
    op.drop_index("ix_notification_recipient_status", table_name="notification")
    op.drop_constraint("uq_notification_idempotency_key", "notification", type_="unique")
    op.drop_table("notification")
    op.execute("DROP TYPE IF EXISTS notification_type")
    op.execute("DROP TYPE IF EXISTS notification_status")
