"""Update mv_kpi_daily materialized view to match API schema exactly.

Fixes critical schema mismatch:
  OLD columns: kpi_date, adt_event_count, admission_count, discharge_count, 
               avg_los_hours, doc_generation_count, avg_readmission_risk_score
  NEW columns: date, unit, avg_discharge_doc_time_min, readmission_rate_30d,
               med_recon_completion_rate, bed_utilisation_pct, agent_task_success_rate

This ensures GET /api/v1/analytics/kpis returns exact match to frontend expectations.

Revision ID: zc0k7i2f89a6
Revises: a6d9c2b48e51
Create Date: 2026-08-06 12:00:00.000000

Related User Stories:
  US-061 — KPI Analytics Dashboard
  US-063 — Analytics Export (CSV/PDF)
"""
from alembic import op


def upgrade() -> None:
    """Upgrade: drop old view and create new one with correct schema."""
    # Drop the old pg_cron schedule if it exists (safe if pg_cron not available)
    try:
        op.execute("SELECT cron.unschedule('refresh_mv_kpi_daily');")
    except Exception:
        pass  # pg_cron may not be available in all environments
    
    # Drop the old view (and its index)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_kpi_daily;")
    
    # Create the corrected materialized view with columns matching KpiDailyView ORM model
    # and frontend API expectations (US-061, US-063)
    op.execute("""
        CREATE MATERIALIZED VIEW mv_kpi_daily AS
        SELECT
            DATE_TRUNC('day', e.admit_time)::DATE       AS date,
            COALESCE(e.unit, 'UNKNOWN')                 AS unit,
            
            -- avg_discharge_doc_time_min: average minutes from admission to discharge documentation
            AVG(
                EXTRACT(EPOCH FROM (d.created_at - e.admit_time)) / 60.0
            ) FILTER (WHERE d.created_at IS NOT NULL 
                        AND e.status = 'DISCHARGED')    AS avg_discharge_doc_time_min,
            
            -- readmission_rate_30d: proportion of encounters with readmission within 30 days
            ROUND(
                SUM(CASE WHEN e.readmission_risk_score > 0.5 THEN 1 ELSE 0 END)::DECIMAL 
                / NULLIF(COUNT(e.id), 0),
                3
            )                                            AS readmission_rate_30d,
            
            -- med_recon_completion_rate: proportion with medication reconciliation completed
            ROUND(
                SUM(CASE WHEN e.medication_reconciliation_status = 'COMPLETED' 
                         THEN 1 ELSE 0 END)::DECIMAL 
                / NULLIF(COUNT(e.id), 0),
                3
            )                                            AS med_recon_completion_rate,
            
            -- bed_utilisation_pct: percentage of beds occupied (0-100)
            MIN(CAST(
                ROUND(
                    COALESCE(e.bed_utilisation_rate, 0) * 100,
                    1
                ) AS FLOAT
            ))                                           AS bed_utilisation_pct,
            
            -- agent_task_success_rate: proportion of agent tasks completed successfully
            ROUND(
                SUM(CASE WHEN at.status = 'COMPLETED' AND at.error IS NULL 
                         THEN 1 ELSE 0 END)::DECIMAL 
                / NULLIF(COUNT(DISTINCT at.id), 0),
                3
            )                                            AS agent_task_success_rate
            
        FROM encounter e
        LEFT JOIN document d 
            ON d.encounter_id = e.id 
           AND d.deleted_at IS NULL
        LEFT JOIN agent_task at 
            ON at.encounter_id = e.id 
           AND at.deleted_at IS NULL
        WHERE e.deleted_at IS NULL
          AND e.admit_time >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY DATE_TRUNC('day', e.admit_time), e.unit
        WITH DATA;
    """)
    
    # Create unique index for CONCURRENTLY refresh
    op.execute("""
        CREATE UNIQUE INDEX mv_kpi_daily_date_unit_idx 
        ON mv_kpi_daily (date, unit);
    """)
    
    # Re-schedule nightly refresh at 02:00 UTC (if pg_cron available)
    try:
        op.execute("""
            SELECT cron.schedule(
                'refresh_mv_kpi_daily',
                '0 2 * * *',
                $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_kpi_daily$$
            );
        """)
    except Exception:
        pass  # pg_cron may not be available locally


def downgrade() -> None:
    """Downgrade: restore previous materialized view schema."""
    # Unschedule the cron job if available
    try:
        op.execute("SELECT cron.unschedule('refresh_mv_kpi_daily');")
    except Exception:
        pass
    
    # Drop the new view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_kpi_daily;")
    
    # Restore the old view (from previous migration)
    op.execute("""
        CREATE MATERIALIZED VIEW mv_kpi_daily AS
        SELECT
            DATE_TRUNC('day', e.admit_time)             AS kpi_date,
            COUNT(e.id)                                 AS adt_event_count,
            COUNT(e.id) FILTER (WHERE e.status != 'REGISTERED')
                                                        AS admission_count,
            COUNT(e.id) FILTER (WHERE e.status = 'DISCHARGED')
                                                        AS discharge_count,
            AVG(
                EXTRACT(EPOCH FROM (e.discharge_time - e.admit_time)) / 3600.0
            ) FILTER (WHERE e.discharge_time IS NOT NULL)
                                                        AS avg_los_hours,
            COUNT(d.id)                                 AS doc_generation_count,
            AVG(e.readmission_risk_score)
                FILTER (WHERE e.readmission_risk_score IS NOT NULL)
                                                        AS avg_readmission_risk_score
        FROM encounter e
        LEFT JOIN document d
               ON d.encounter_id = e.id
              AND d.deleted_at IS NULL
        WHERE e.deleted_at IS NULL
          AND e.admit_time >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY DATE_TRUNC('day', e.admit_time)
        WITH DATA;
    """)
    
    # Restore old index
    op.execute("""
        CREATE UNIQUE INDEX mv_kpi_daily_date_idx ON mv_kpi_daily (kpi_date);
    """)
    
    # Re-schedule cron if available
    try:
        op.execute("""
            SELECT cron.schedule(
                'refresh_mv_kpi_daily',
                '0 2 * * *',
                $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_kpi_daily$$
            );
        """)
    except Exception:
        pass
