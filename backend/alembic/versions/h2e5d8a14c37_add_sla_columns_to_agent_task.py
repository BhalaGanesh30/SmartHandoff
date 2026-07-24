"""add_sla_columns_to_agent_task

Adds sla_threshold_minutes and sla_breached columns to agent_task table.
Adds partial index to support SLAMonitor active-task polling query.

US-021: SLA monitoring requires these fields for breach detection and API response.

Revision ID: h2e5d8a14c37
Revises: g1d4e7a93c26
Create Date: 2026-07-24 00:00:00.000000
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "h2e5d8a14c37"
down_revision: Union[str, None] = "g1d4e7a93c26"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Add SLA tracking columns and index to agent_task table."""
    op.add_column(
        "agent_task",
        sa.Column(
            "sla_threshold_minutes",
            sa.Integer(),
            nullable=True,
            comment="SLA threshold in minutes for this agent type.",
        ),
    )
    op.add_column(
        "agent_task",
        sa.Column(
            "sla_breached",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Set to TRUE by SLAMonitor when task exceeds its SLA threshold.",
        ),
    )
    op.create_index(
        "ix_agent_task_active_status_created",
        "agent_task",
        ["status", "created_at"],
        postgresql_where=sa.text("status IN ('IN_PROGRESS', 'PENDING')"),
    )


def downgrade() -> None:
    """Remove SLA tracking columns and index from agent_task table."""
    op.drop_index(
        "ix_agent_task_active_status_created",
        table_name="agent_task",
    )
    op.drop_column("agent_task", "sla_breached")
    op.drop_column("agent_task", "sla_threshold_minutes")
