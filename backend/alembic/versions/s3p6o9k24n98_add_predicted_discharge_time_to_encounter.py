"""add_predicted_discharge_time_to_encounter

Revision ID: s3p6o9k24n98
Revises: r2o5n8j13m87
Create Date: 2026-07-28

US-036 TASK-003: Adds discharge time prediction columns to encounter and
updates mv_bed_board to include these fields for dashboard display.

Columns added:
    - predicted_discharge_time: ML-predicted discharge datetime (UTC)
    - discharge_prediction_confidence: 'high', 'medium', 'low', or NULL
    - discharge_prediction_interval_hours: ±hours confidence interval from ML

Design refs:
    US-036 DoD — predicted_discharge_time + mv_bed_board projection
    US-036 AC Scenario 3 — prediction stored in encounter
    US-036 AC Scenario 4 — confidence level displayed on bed board
    TR-007 — ML inference service p95 latency <500ms
    DR-002 — No PHI in prediction columns (datetime + confidence only)
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "s3p6o9k24n98"
down_revision: Union[str, None] = "r2o5n8j13m87"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add predicted_discharge_time columns to encounter and update mv_bed_board view."""
    
    # ────────────────────────────────────────────────────────────────────────
    # 1. Extend encounter table with ML prediction columns
    # ────────────────────────────────────────────────────────────────────────
    op.add_column(
        "encounter",
        sa.Column(
            "predicted_discharge_time",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="ML-predicted discharge datetime (UTC). NULL if not yet predicted.",
        ),
    )
    op.add_column(
        "encounter",
        sa.Column(
            "discharge_prediction_confidence",
            sa.String(10),
            nullable=True,
            comment="Confidence tier: 'high', 'medium', 'low', or NULL if unpredicted.",
        ),
    )
    op.add_column(
        "encounter",
        sa.Column(
            "discharge_prediction_interval_hours",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="±hours confidence interval returned by ML Inference Service.",
        ),
    )

    # ────────────────────────────────────────────────────────────────────────
    # 2. Create partial index on predicted_discharge_time for dashboard queries
    #    Index only ADMITTED encounters with non-null predictions (US-036)
    # ────────────────────────────────────────────────────────────────────────
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_encounter_predicted_discharge
        ON encounter (predicted_discharge_time)
        WHERE predicted_discharge_time IS NOT NULL
          AND status = 'ADMITTED'
          AND deleted_at IS NULL
    """)

    # ────────────────────────────────────────────────────────────────────────
    # 3. Drop and recreate mv_bed_board with prediction columns
    #    NOTE: Cannot use CONCURRENTLY on DROP; use transaction-safe plain drop.
    #    The view will be recreated WITH DATA immediately below.
    # ────────────────────────────────────────────────────────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_bed_board")

    op.execute("""
        CREATE MATERIALIZED VIEW mv_bed_board AS
        SELECT
            b.unit,
            b.id                                AS bed_id,
            b.label                             AS bed_label,
            e.id                                AS encounter_id,
            e.patient_id,
            p.first_name                        AS patient_first_name_enc,
            p.last_name                         AS patient_last_name_enc,
            e.admit_time,
            e.status                            AS encounter_status,
            e.expected_discharge_date,
            e.risk_tier,
            e.predicted_discharge_time,
            e.discharge_prediction_confidence,
            e.discharge_prediction_interval_hours
        FROM bed b
        LEFT JOIN encounter e
               ON e.bed_id = b.id
              AND e.status IN ('ADMITTED', 'TRANSFERRED')
              AND e.deleted_at IS NULL
        LEFT JOIN patient p
               ON p.id = e.patient_id
              AND p.deleted_at IS NULL
        WITH DATA
    """)

    # ────────────────────────────────────────────────────────────────────────
    # 4. Recreate indexes on mv_bed_board
    #    UNIQUE index is required for REFRESH MATERIALIZED VIEW CONCURRENTLY
    #    (US-035/TASK-002 pg_cron job)
    # ────────────────────────────────────────────────────────────────────────
    op.execute("""
        CREATE UNIQUE INDEX mv_bed_board_bed_id_idx ON mv_bed_board (bed_id)
    """)

    op.execute("""
        CREATE INDEX mv_bed_board_unit_idx ON mv_bed_board (unit)
    """)


def downgrade() -> None:
    """Remove prediction columns and restore mv_bed_board to original schema."""
    
    # ────────────────────────────────────────────────────────────────────────
    # 1. Drop and recreate mv_bed_board without prediction columns
    # ────────────────────────────────────────────────────────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_bed_board")

    op.execute("""
        CREATE MATERIALIZED VIEW mv_bed_board AS
        SELECT
            b.unit,
            b.id            AS bed_id,
            b.label         AS bed_label,
            e.id            AS encounter_id,
            e.patient_id,
            p.first_name    AS patient_first_name_enc,
            p.last_name     AS patient_last_name_enc,
            e.admit_time,
            e.status        AS encounter_status,
            e.expected_discharge_date,
            e.risk_tier
        FROM bed b
        LEFT JOIN encounter e
               ON e.bed_id = b.id
              AND e.status IN ('ADMITTED', 'TRANSFERRED')
              AND e.deleted_at IS NULL
        LEFT JOIN patient p
               ON p.id = e.patient_id
              AND p.deleted_at IS NULL
        WITH DATA
    """)

    # Recreate indexes
    op.execute("""
        CREATE UNIQUE INDEX mv_bed_board_bed_id_idx ON mv_bed_board (bed_id)
    """)

    op.execute("""
        CREATE INDEX mv_bed_board_unit_idx ON mv_bed_board (unit)
    """)

    # ────────────────────────────────────────────────────────────────────────
    # 2. Drop partial index on encounter.predicted_discharge_time
    # ────────────────────────────────────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS idx_encounter_predicted_discharge")

    # ────────────────────────────────────────────────────────────────────────
    # 3. Remove prediction columns from encounter table
    # ────────────────────────────────────────────────────────────────────────
    op.drop_column("encounter", "discharge_prediction_interval_hours")
    op.drop_column("encounter", "discharge_prediction_confidence")
    op.drop_column("encounter", "predicted_discharge_time")
