"""add_boarding_alert_fields_to_encounter

Revision ID: t4q7p0l35o09
Revises: s3p6o9k24n98
Create Date: 2026-07-28

US-038 TASK-001: Adds boarding alert timestamp columns to the encounter table
to support idempotent ED boarding alert dispatch.

Columns added:
    - boarding_alert_sent_at: UTC timestamp when the first boarding alert was
      published to notification-requests. NULL means no alert has been sent yet
      for this encounter's ED stay. Used as idempotency guard (US-038 AC Scenario 4).
    - boarding_alert_resolved_at: UTC timestamp when the boarding alert was
      resolved (patient assigned to a bed via PATCH /api/v1/beds/{id}/status →
      RESERVED). NULL means the alert is still active or has not been triggered.

Index created:
    - ix_encounter_boarding_active: Partial index on boarding_alert_sent_at
      for encounters where alert was sent but not yet resolved. Speeds up the
      BoardingMonitor idempotency check query.

Design refs:
    US-038 AC Scenario 3 — boarding_alert_resolved_at for resolution tracking
    US-038 AC Scenario 4 — boarding_alert_sent_at for idempotency
    design.md §6.1 DR-001 — Alembic-managed DDL
    design.md §6.1 DR-002 — New columns contain timestamps only; no PHI
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "t4q7p0l35o09"
down_revision: Union[str, None] = "s3p6o9k24n98"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add boarding alert timestamp columns and partial index to encounter table."""
    
    # ────────────────────────────────────────────────────────────────────────
    # 1. Add boarding_alert_sent_at column (idempotency guard)
    # ────────────────────────────────────────────────────────────────────────
    op.add_column(
        "encounter",
        sa.Column(
            "boarding_alert_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "UTC timestamp when the ED boarding alert was first published to "
                "notification-requests. NULL means no alert has been sent yet for "
                "this encounter's ED stay. Used as idempotency guard (US-038 AC Scenario 4)."
            ),
        ),
    )
    
    # ────────────────────────────────────────────────────────────────────────
    # 2. Add boarding_alert_resolved_at column (resolution tracking)
    # ────────────────────────────────────────────────────────────────────────
    op.add_column(
        "encounter",
        sa.Column(
            "boarding_alert_resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "UTC timestamp when the boarding alert was resolved (patient assigned to "
                "a bed via PATCH /api/v1/beds/{id}/status → RESERVED). NULL means the "
                "alert is still active or has not been triggered."
            ),
        ),
    )
    
    # ────────────────────────────────────────────────────────────────────────
    # 3. Create partial index for active boarding alerts
    # ────────────────────────────────────────────────────────────────────────
    # Partial index — only index encounters where alert was sent but not yet resolved.
    # Speeds up the BoardingMonitor idempotency check query:
    #   SELECT * FROM encounter WHERE boarding_alert_sent_at IS NOT NULL
    #                             AND boarding_alert_resolved_at IS NULL
    op.create_index(
        "ix_encounter_boarding_active",
        "encounter",
        ["boarding_alert_sent_at"],
        postgresql_where=sa.text(
            "boarding_alert_sent_at IS NOT NULL AND boarding_alert_resolved_at IS NULL"
        ),
    )


def downgrade() -> None:
    """Remove boarding alert columns and index from encounter table."""
    op.drop_index("ix_encounter_boarding_active", table_name="encounter")
    op.drop_column("encounter", "boarding_alert_resolved_at")
    op.drop_column("encounter", "boarding_alert_sent_at")
