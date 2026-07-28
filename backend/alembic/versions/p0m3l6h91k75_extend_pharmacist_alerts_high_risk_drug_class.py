"""US-032 TASK-004: Extend pharmacist_alerts for HIGH_RISK_DRUG_CLASS

Extends pharmacist_alerts table to support HIGH_RISK_DRUG_CLASS alert type
and the pharmacist resolution workflow.

Changes:
    1. Convert alert_type from VARCHAR(64) to ENUM type
    2. Extend alert_type_enum with HIGH_RISK_DRUG_CLASS value
    3. Add drug_class VARCHAR(64) NULL (ISMP class identifier)
    4. Add drug_name VARCHAR(255) NULL (single drug name for HIGH_RISK alerts)
    5. Add status alert_status_enum NOT NULL DEFAULT 'ACTIVE'
    6. Add resolution_type alert_resolution_type_enum NULL
    7. Add resolution_note TEXT NULL
    8. Add resolved_by_user_id UUID NULL FK(users.id) SET NULL
    9. Add resolved_at TIMESTAMPTZ NULL
    10. Add sla_breached BOOLEAN NOT NULL DEFAULT FALSE

New ENUM types:
    - alert_type_enum: PHARMACIST_ALERT | HIGH_RISK_DRUG_CLASS
    - alert_status_enum: ACTIVE | RESOLVED
    - alert_resolution_type_enum: REVIEWED_ACCEPTABLE | DOSE_ADJUSTED | 
                                   DRUG_CHANGED | DISCONTINUED

New Indexes:
    - ix_pharmacist_alerts_drug_class on drug_class (filter by ISMP class)
    - ix_pharmacist_alerts_status on status (filter active/resolved)
    - ix_pharmacist_alerts_resolved_by_user_id on resolved_by_user_id (pharmacist workload)

Backfill:
    - All existing rows: status = 'ACTIVE', sla_breached = FALSE

Revision ID: p0m3l6h91k75
Revises:     o9l2k5g80j74
Create Date: 2026-07-28

Design refs:
    US-032 AC Scenario 1 — HIGH_RISK_DRUG_CLASS alert fields
    US-032 AC Scenario 2 — Resolution workflow fields
    US-032 AC Scenario 3 — SLA monitoring (sla_breached)
    TASK-003 — PharmacistAlert ORM model extension
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic
revision = "p0m3l6h91k75"
down_revision = "o9l2k5g80j74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend pharmacist_alerts table for HIGH_RISK_DRUG_CLASS alerts and resolution workflow."""
    
    # 1. Create alert_type_enum and convert alert_type column from VARCHAR to ENUM
    # First, create the ENUM type with current value
    alert_type_enum = postgresql.ENUM(
        "PHARMACIST_ALERT",
        "HIGH_RISK_DRUG_CLASS",
        name="alert_type_enum",
        create_type=True,
    )
    alert_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Convert alert_type column from VARCHAR to ENUM using ALTER COLUMN
    op.execute(
        """
        ALTER TABLE pharmacist_alerts 
        ALTER COLUMN alert_type TYPE alert_type_enum 
        USING alert_type::text::alert_type_enum
        """
    )
    
    # 2. Create new ENUM types for status and resolution workflow
    alert_status_enum = postgresql.ENUM(
        "ACTIVE", "RESOLVED",
        name="alert_status_enum",
        create_type=True,
    )
    alert_status_enum.create(op.get_bind(), checkfirst=True)
    
    alert_resolution_type_enum = postgresql.ENUM(
        "REVIEWED_ACCEPTABLE",
        "DOSE_ADJUSTED",
        "DRUG_CHANGED",
        "DISCONTINUED",
        name="alert_resolution_type_enum",
        create_type=True,
    )
    alert_resolution_type_enum.create(op.get_bind(), checkfirst=True)
    
    # 3. Add new columns for HIGH_RISK_DRUG_CLASS alerts
    op.add_column(
        "pharmacist_alerts",
        sa.Column(
            "drug_class",
            sa.String(64),
            nullable=True,
            comment="ISMP high-risk class: ANTICOAGULANT | INSULIN | OPIOID | CHEMOTHERAPY",
        ),
    )
    op.add_column(
        "pharmacist_alerts",
        sa.Column(
            "drug_name",
            sa.String(255),
            nullable=True,
            comment="Single drug name triggering a HIGH_RISK_DRUG_CLASS alert",
        ),
    )
    
    # 4. Add resolution workflow columns
    op.add_column(
        "pharmacist_alerts",
        sa.Column(
            "status",
            postgresql.ENUM(
                "ACTIVE", "RESOLVED",
                name="alert_status_enum",
                create_type=False,  # Already created above
            ),
            nullable=False,
            server_default="ACTIVE",
            comment="Alert lifecycle status",
        ),
    )
    op.add_column(
        "pharmacist_alerts",
        sa.Column(
            "resolution_type",
            postgresql.ENUM(
                "REVIEWED_ACCEPTABLE",
                "DOSE_ADJUSTED",
                "DRUG_CHANGED",
                "DISCONTINUED",
                name="alert_resolution_type_enum",
                create_type=False,  # Already created above
            ),
            nullable=True,
            comment="How the pharmacist resolved the alert",
        ),
    )
    op.add_column(
        "pharmacist_alerts",
        sa.Column(
            "resolution_note",
            sa.Text(),
            nullable=True,
            comment="Free-text pharmacist note at resolution",
        ),
    )
    op.add_column(
        "pharmacist_alerts",
        sa.Column(
            "resolved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to users.id of resolving pharmacist",
        ),
    )
    op.add_column(
        "pharmacist_alerts",
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC timestamp when alert was resolved",
        ),
    )
    
    # 5. Add SLA monitoring column
    op.add_column(
        "pharmacist_alerts",
        sa.Column(
            "sla_breached",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Set True by SLA monitor when alert exceeds 24h unresolved threshold",
        ),
    )
    
    # 6. Create indexes for query performance
    op.create_index(
        "ix_pharmacist_alerts_drug_class",
        "pharmacist_alerts",
        ["drug_class"],
        unique=False,
    )
    op.create_index(
        "ix_pharmacist_alerts_status",
        "pharmacist_alerts",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_pharmacist_alerts_resolved_by_user_id",
        "pharmacist_alerts",
        ["resolved_by_user_id"],
        unique=False,
    )
    
    # 7. Backfill existing rows (status already has server_default='ACTIVE')
    # This is a safety measure to ensure no NULL values exist
    op.execute(
        "UPDATE pharmacist_alerts SET status = 'ACTIVE' WHERE status IS NULL"
    )


def downgrade() -> None:
    """Revert pharmacist_alerts table to pre-US-032 state."""
    
    # 1. Drop indexes
    op.drop_index(
        "ix_pharmacist_alerts_resolved_by_user_id",
        table_name="pharmacist_alerts",
    )
    op.drop_index(
        "ix_pharmacist_alerts_status",
        table_name="pharmacist_alerts",
    )
    op.drop_index(
        "ix_pharmacist_alerts_drug_class",
        table_name="pharmacist_alerts",
    )
    
    # 2. Drop columns (in reverse order of addition)
    for col in [
        "sla_breached",
        "resolved_at",
        "resolved_by_user_id",
        "resolution_note",
        "resolution_type",
        "status",
        "drug_name",
        "drug_class",
    ]:
        op.drop_column("pharmacist_alerts", col)
    
    # 3. Convert alert_type column back from ENUM to VARCHAR(64)
    op.execute(
        """
        ALTER TABLE pharmacist_alerts 
        ALTER COLUMN alert_type TYPE VARCHAR(64) 
        USING alert_type::text
        """
    )
    op.execute(
        """
        ALTER TABLE pharmacist_alerts 
        ALTER COLUMN alert_type SET DEFAULT 'PHARMACIST_ALERT'
        """
    )
    
    # 4. Drop ENUM types
    op.execute("DROP TYPE IF EXISTS alert_resolution_type_enum")
    op.execute("DROP TYPE IF EXISTS alert_status_enum")
    op.execute("DROP TYPE IF EXISTS alert_type_enum")
