"""US-067 TASK-001: Add notification_opt_out to patient table

Adds notification preference tracking to support patient opt-out of non-urgent
notifications (US-067):

Patient table changes:
    - notification_opt_out: BOOLEAN NOT NULL DEFAULT FALSE
      Patient can opt out of non-urgent notifications via portal.
      Urgent messages with urgency_override=True bypass this flag.

Revision ID: j4g7f0b35e49
Revises:     i3f6e9b24d48
Create Date: 2026-07-25

Design refs:
    US-067 AC2  — Patient opt-out suppresses non-urgent notifications
    US-067 AC4  — Opt-out preference persisted on patient table
    US-067 DoD  — notification_opt_out boolean on patient, not notification table
    US-006      — Patient ORM model foundation
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "j4g7f0b35e49"
down_revision: Union[str, None] = "i3f6e9b24d48"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Add notification_opt_out column to patient table."""
    op.add_column(
        "patient",
        sa.Column(
            "notification_opt_out",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="Patient opted out of non-urgent notifications (US-067)",
        ),
    )


def downgrade() -> None:
    """Remove notification_opt_out column from patient table."""
    op.drop_column("patient", "notification_opt_out")
