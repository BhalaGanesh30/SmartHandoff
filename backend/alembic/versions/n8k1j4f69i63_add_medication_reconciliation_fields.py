"""US-030 TASK-001: Add medication reconciliation fields and enums

Adds reconciliation support to the medication table:

New ENUM types:
    - ReconciliationCategory: CONTINUED | NEW | STOPPED | DOSE_CHANGED
    - ReconciliationFlag: DUPLICATE | STOPPED_WITHOUT_ORDER
    - MedicationListSource: PRE_ADMIT | INPATIENT | DISCHARGE

Medication table changes:
    - rxnorm_cui: VARCHAR(20) NULL
      RxNorm Concept Unique Identifier from RxNav API for drug normalization
    
    - reconciliation_category: ReconciliationCategory NULL
      Outcome of three-way reconciliation (pre-admit → inpatient → discharge)
    
    - flags: ReconciliationFlag[] NOT NULL DEFAULT '{}'
      Alert flags raised during reconciliation (DUPLICATE, STOPPED_WITHOUT_ORDER)
    
    - dose_value: FLOAT NULL
      Parsed numeric dose value
    
    - dose_unit: VARCHAR(20) NULL
      Dose unit (e.g., mg, mL)
    
    - sources: MedicationListSource[] NOT NULL DEFAULT '{}'
      Which FHIR medication lists this drug appears on
    
    - reconciliation_completed_at: TIMESTAMPTZ NULL
      UTC timestamp when reconciliation was completed for this medication

Indexes:
    - ix_medication_rxnorm_cui on rxnorm_cui
    - ix_medication_reconciliation_category on reconciliation_category

Revision ID: n8k1j4f69i63
Revises:     m7j0i3e58h62
Create Date: 2026-07-26

Design refs:
    US-030 — Medication Reconciliation Agent
    TASK-001 — Medication ORM Models, Enums, and Alembic Migration
    FR-030–FR-035 — Medication reconciliation functional requirements
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic
revision = "n8k1j4f69i63"
down_revision = "m7j0i3e58h62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add medication reconciliation enums and fields."""
    
    # 1. Create ENUM types
    reconciliation_category = postgresql.ENUM(
        "CONTINUED", "NEW", "STOPPED", "DOSE_CHANGED",
        name="reconciliationcategory",
        create_type=True,
    )
    reconciliation_category.create(op.get_bind(), checkfirst=True)
    
    reconciliation_flag = postgresql.ENUM(
        "DUPLICATE", "STOPPED_WITHOUT_ORDER",
        name="reconciliationflag",
        create_type=True,
    )
    reconciliation_flag.create(op.get_bind(), checkfirst=True)
    
    medication_list_source = postgresql.ENUM(
        "PRE_ADMIT", "INPATIENT", "DISCHARGE",
        name="medicationlistsource",
        create_type=True,
    )
    medication_list_source.create(op.get_bind(), checkfirst=True)
    
    # 2. Add rxnorm_cui column with index
    op.add_column(
        "medication",
        sa.Column(
            "rxnorm_cui",
            sa.String(20),
            nullable=True,
            comment="RxNorm CUI from RxNav API for drug normalization",
        ),
    )
    op.create_index(
        "ix_medication_rxnorm_cui",
        "medication",
        ["rxnorm_cui"],
        unique=False,
    )
    
    # 3. Add reconciliation_category column with index
    op.add_column(
        "medication",
        sa.Column(
            "reconciliation_category",
            postgresql.ENUM(
                "CONTINUED", "NEW", "STOPPED", "DOSE_CHANGED",
                name="reconciliationcategory",
                create_type=False,
            ),
            nullable=True,
            comment="CONTINUED | NEW | STOPPED | DOSE_CHANGED",
        ),
    )
    op.create_index(
        "ix_medication_reconciliation_category",
        "medication",
        ["reconciliation_category"],
        unique=False,
    )
    
    # 4. Add flags array column
    op.add_column(
        "medication",
        sa.Column(
            "flags",
            postgresql.ARRAY(
                postgresql.ENUM(
                    "DUPLICATE", "STOPPED_WITHOUT_ORDER",
                    name="reconciliationflag",
                    create_type=False,
                )
            ),
            nullable=False,
            server_default="{}",
            comment="DUPLICATE, STOPPED_WITHOUT_ORDER flags",
        ),
    )
    
    # 5. Add dose_value column
    op.add_column(
        "medication",
        sa.Column(
            "dose_value",
            sa.Float(),
            nullable=True,
            comment="Parsed numeric dose value",
        ),
    )
    
    # 6. Add dose_unit column
    op.add_column(
        "medication",
        sa.Column(
            "dose_unit",
            sa.String(20),
            nullable=True,
            comment="Dose unit e.g. mg",
        ),
    )
    
    # 7. Add sources array column
    op.add_column(
        "medication",
        sa.Column(
            "sources",
            postgresql.ARRAY(
                postgresql.ENUM(
                    "PRE_ADMIT", "INPATIENT", "DISCHARGE",
                    name="medicationlistsource",
                    create_type=False,
                )
            ),
            nullable=False,
            server_default="{}",
            comment="Which FHIR lists this drug appears on",
        ),
    )
    
    # 8. Add reconciliation_completed_at column
    op.add_column(
        "medication",
        sa.Column(
            "reconciliation_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when reconciliation was completed for this medication",
        ),
    )


def downgrade() -> None:
    """Remove medication reconciliation enums and fields."""
    
    # Remove columns (reverse order)
    op.drop_column("medication", "reconciliation_completed_at")
    op.drop_column("medication", "sources")
    op.drop_column("medication", "dose_unit")
    op.drop_column("medication", "dose_value")
    op.drop_column("medication", "flags")
    
    # Remove indexes
    op.drop_index("ix_medication_reconciliation_category", table_name="medication")
    op.drop_column("medication", "reconciliation_category")
    
    op.drop_index("ix_medication_rxnorm_cui", table_name="medication")
    op.drop_column("medication", "rxnorm_cui")
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS medicationlistsource")
    op.execute("DROP TYPE IF EXISTS reconciliationflag")
    op.execute("DROP TYPE IF EXISTS reconciliationcategory")
