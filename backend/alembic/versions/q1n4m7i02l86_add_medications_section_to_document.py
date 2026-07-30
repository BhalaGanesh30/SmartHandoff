"""add medications_section to document

Revision ID: q1n4m7i02l86
Revises: p0m3l6h91k75
Create Date: 2026-07-28 14:30:00.000000

US-033 TASK-004: Add medications_section JSONB column to document table
for storing patient-readable medication change summaries.

Design refs:
    US-033 AC Scenario 3 — medications_section stored in Document record
    design.md §6         — Document table with JSONB content fields
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'q1n4m7i02l86'
down_revision = 'p0m3l6h91k75'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add medications_section JSONB column to document table."""
    op.add_column(
        "document",
        sa.Column(
            "medications_section",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Patient-readable medication change summary (MedicationSummaryOutput schema). "
                "Populated by MedicationSummaryGenerator after reconciliation. "
                "Keys: new, stopped, changed, continued (each a list of medication dicts)."
            ),
        ),
    )


def downgrade() -> None:
    """Remove medications_section column from document table."""
    op.drop_column("document", "medications_section")
