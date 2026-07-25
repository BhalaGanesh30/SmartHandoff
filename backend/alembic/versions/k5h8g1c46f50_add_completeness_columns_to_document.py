"""US-026 TASK-003: Add completeness tracking to document table

Adds completeness_status and missing_fields columns to support document
validation (US-026):

Document table changes:
    - completeness_status: VARCHAR(20) NULL
      Either "COMPLETE" or "INCOMPLETE" — set by CompletenessValidator
      after document generation. NULL until validation runs.
    
    - missing_fields: JSONB NULL DEFAULT '[]'::jsonb
      Ordered list of required field names that are absent from the document.
      Empty array when COMPLETE or not yet validated.

Revision ID: k5h8g1c46f50
Revises:     j4g7f0b35e49
Create Date: 2026-07-25

Design refs:
    US-026 AC1  — Document.completeness_status = "COMPLETE" on complete doc
    US-026 AC2  — Document.completeness_status = "INCOMPLETE" + missing_fields list
    US-026 AC4  — Tasks API reads completeness_status and missing_fields
    US-026 DoD  — Completeness result persisted on Document model
    TASK-026-002 — CompletenessValidator produces CompletenessResult
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "k5h8g1c46f50"
down_revision: Union[str, None] = "j4g7f0b35e49"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Add completeness_status and missing_fields columns to document table."""
    op.add_column(
        "document",
        sa.Column(
            "completeness_status",
            sa.String(length=20),
            nullable=True,
            comment="COMPLETE or INCOMPLETE — set by CompletenessValidator after document generation",
        ),
    )
    op.add_column(
        "document",
        sa.Column(
            "missing_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
            comment="Ordered list of field names absent from the document. Empty list when COMPLETE.",
        ),
    )


def downgrade() -> None:
    """Remove completeness_status and missing_fields columns from document table."""
    op.drop_column("document", "missing_fields")
    op.drop_column("document", "completeness_status")
