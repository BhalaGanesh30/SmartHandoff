"""US-031 TASK-006: Add pharmacist_alerts table

Adds pharmacist_alerts table for drug-drug interaction alert storage:

New ENUM types:
    - alert_severity_enum: HIGH | MEDIUM | LOW
    - check_status_enum: COMPLETE | INCOMPLETE

pharmacist_alerts table:
    - id: UUID PRIMARY KEY
      Unique alert identifier
    
    - encounter_id: UUID NOT NULL FK(encounters.id) ON DELETE CASCADE
      Reference to the encounter this alert belongs to
    
    - alert_type: VARCHAR(64) NOT NULL DEFAULT 'PHARMACIST_ALERT'
      Alert classification type
    
    - severity: alert_severity_enum NOT NULL
      Interaction severity level (HIGH, MEDIUM, LOW)
    
    - drug_pair: JSON NULL
      Array of drug names involved in the interaction (max 2)
    
    - interaction_description: TEXT NULL
      Free-text description of the interaction
    
    - source: VARCHAR(32) NOT NULL DEFAULT 'RXNAV'
      Data source (RXNAV | OPENFDA | SYSTEM)
    
    - interaction_check_status: check_status_enum NOT NULL DEFAULT 'COMPLETE'
      Status of interaction check (COMPLETE | INCOMPLETE for degraded service)
    
    - metadata: JSON NULL
      Additional metadata (rxcui1, rxcui2, degradation_notice, etc.)
    
    - created_at: TIMESTAMPTZ NOT NULL DEFAULT NOW()
      UTC timestamp when alert was created

Indexes:
    - ix_pharmacist_alerts_encounter_id on encounter_id (query by encounter)
    - ix_pharmacist_alerts_severity on severity (filter high-priority alerts)

Revision ID: o9l2k5g80j74
Revises:     n8k1j4f69i63
Create Date: 2026-07-28

Design refs:
    US-031 — Drug-Drug Interaction Detection
    TASK-005 — Pharmacist Alert Endpoint
    TASK-006 — Alembic Migration for pharmacist_alerts table
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic
revision = "o9l2k5g80j74"
down_revision = "n8k1j4f69i63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add pharmacist_alerts table with enums and indexes."""
    
    # 1. Create ENUM types for alert severity and check status
    alert_severity_enum = postgresql.ENUM(
        "HIGH", "MEDIUM", "LOW",
        name="alert_severity_enum",
        create_type=True,
    )
    alert_severity_enum.create(op.get_bind(), checkfirst=True)
    
    check_status_enum = postgresql.ENUM(
        "COMPLETE", "INCOMPLETE",
        name="check_status_enum",
        create_type=True,
    )
    check_status_enum.create(op.get_bind(), checkfirst=True)
    
    # 2. Create pharmacist_alerts table
    op.create_table(
        "pharmacist_alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique alert identifier",
        ),
        sa.Column(
            "encounter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("encounter.id", ondelete="CASCADE"),
            nullable=False,
            comment="Reference to encounter",
        ),
        sa.Column(
            "alert_type",
            sa.String(64),
            nullable=False,
            server_default="PHARMACIST_ALERT",
            comment="Alert classification type",
        ),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "HIGH", "MEDIUM", "LOW",
                name="alert_severity_enum",
                create_type=False,  # Already created above
            ),
            nullable=False,
            comment="Interaction severity level",
        ),
        sa.Column(
            "drug_pair",
            postgresql.JSON(),
            nullable=True,
            comment="Array of drug names in the interaction (max 2)",
        ),
        sa.Column(
            "interaction_description",
            sa.Text(),
            nullable=True,
            comment="Free-text description of the interaction",
        ),
        sa.Column(
            "source",
            sa.String(32),
            nullable=False,
            server_default="RXNAV",
            comment="Data source: RXNAV | OPENFDA | SYSTEM",
        ),
        sa.Column(
            "interaction_check_status",
            postgresql.ENUM(
                "COMPLETE", "INCOMPLETE",
                name="check_status_enum",
                create_type=False,  # Already created above
            ),
            nullable=False,
            server_default="COMPLETE",
            comment="Status of interaction check",
        ),
        sa.Column(
            "metadata",
            postgresql.JSON(),
            nullable=True,
            comment="Additional metadata (rxcui1, rxcui2, degradation_notice)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="UTC timestamp when alert was created",
        ),
    )
    
    # 3. Create indexes for query performance
    op.create_index(
        "ix_pharmacist_alerts_encounter_id",
        "pharmacist_alerts",
        ["encounter_id"],
        unique=False,
    )
    op.create_index(
        "ix_pharmacist_alerts_severity",
        "pharmacist_alerts",
        ["severity"],
        unique=False,
    )


def downgrade() -> None:
    """Drop pharmacist_alerts table and associated enums."""
    
    # 1. Drop indexes
    op.drop_index(
        "ix_pharmacist_alerts_severity",
        table_name="pharmacist_alerts",
    )
    op.drop_index(
        "ix_pharmacist_alerts_encounter_id",
        table_name="pharmacist_alerts",
    )
    
    # 2. Drop table (CASCADE will drop FK constraints)
    op.drop_table("pharmacist_alerts")
    
    # 3. Drop ENUM types
    op.execute("DROP TYPE IF EXISTS check_status_enum")
    op.execute("DROP TYPE IF EXISTS alert_severity_enum")
