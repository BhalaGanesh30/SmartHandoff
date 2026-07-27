"""add_unit_id_target_role_to_agent_task

Adds unit_id and target_role denormalised columns to agent_task table.
These fields enable SignalR group routing without requiring JOINs.

US-022: SignalR broadcast requires unit_id and role_name for group routing.

Revision ID: i3f6e9b24d48
Revises: h2e5d8a14c37
Create Date: 2026-07-25 00:00:00.000000
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "i3f6e9b24d48"
down_revision: Union[str, None] = "h2e5d8a14c37"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Add SignalR routing columns to agent_task table.
    
    Note: Uses server_default temporarily for the NOT NULL constraint during migration.
    Existing rows get 'UNKNOWN' for unit_id and 'nurse' for target_role.
    New rows must provide these values from the application layer.
    """
    op.add_column(
        "agent_task",
        sa.Column(
            "unit_id",
            sa.String(length=20),
            nullable=False,
            server_default="UNKNOWN",
            comment="Hospital unit ID for SignalR group routing (US-022)",
        ),
    )
    op.add_column(
        "agent_task",
        sa.Column(
            "target_role",
            sa.String(length=50),
            nullable=False,
            server_default="nurse",
            comment="Target clinical role for SignalR group routing (US-022)",
        ),
    )
    # Remove server defaults after migration — values must come from application.
    op.alter_column("agent_task", "unit_id", server_default=None)
    op.alter_column("agent_task", "target_role", server_default=None)


def downgrade() -> None:
    """Remove SignalR routing columns from agent_task table."""
    op.drop_column("agent_task", "target_role")
    op.drop_column("agent_task", "unit_id")
