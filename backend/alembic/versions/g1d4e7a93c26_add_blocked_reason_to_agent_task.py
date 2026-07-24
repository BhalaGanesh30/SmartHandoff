"""add blocked_reason to agent_task — US-019 patient resolution blocking

Adds a nullable ``blocked_reason`` column to the ``agent_task`` table.
The column stores the reason a task is blocked (e.g., patient identity
ambiguous or unresolved), allowing staff to understand why agent execution
cannot proceed.

Revision ID: g1d4e7a93c26
Revises:     f9c1e4a73d28
Create Date: 2026-07-24 00:00:00.000000

Design refs:
    US-019 TASK-003 — Agent task blocking for unresolved patients
    AC5             — Tasks must include blocked_reason field
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "g1d4e7a93c26"
down_revision: Union[str, None] = "f9c1e4a73d28"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """Add nullable ``blocked_reason`` column to ``agent_task``."""
    op.add_column(
        "agent_task",
        sa.Column(
            "blocked_reason",
            sa.String(),
            nullable=True,
            comment=(
                "Reason task is blocked (e.g., patient identity ambiguous "
                "or unresolved) - US-019"
            ),
        ),
    )


def downgrade() -> None:
    """Drop ``blocked_reason`` column from ``agent_task``."""
    op.drop_column("agent_task", "blocked_reason")
