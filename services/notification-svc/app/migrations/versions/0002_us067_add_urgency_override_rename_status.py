"""US-067: Add urgency_override and rename status to delivery_status.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-25

US-067 TASK-001: Alembic migration for notification table schema changes:
1. Rename `status` column to `delivery_status` for consistency with US-067 spec
2. Add `urgency_override` boolean column (default FALSE)

The notification_status enum already includes OPTED_OUT from US-064, so no enum
extension is needed.

Design refs: US-067 DoD, US-064 TASK-001, ADR-003, ADR-007
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply US-067 schema changes to notification table."""
    # 1. Rename status column to delivery_status
    op.alter_column(
        "notification",
        "status",
        new_column_name="delivery_status",
    )

    # 2. Add urgency_override column
    op.add_column(
        "notification",
        sa.Column(
            "urgency_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="True bypasses patient opt-out; set by sending agent only (US-067)",
        ),
    )


def downgrade() -> None:
    """Revert US-067 schema changes."""
    # Remove urgency_override column
    op.drop_column("notification", "urgency_override")

    # Rename delivery_status back to status
    op.alter_column(
        "notification",
        "delivery_status",
        new_column_name="status",
    )
