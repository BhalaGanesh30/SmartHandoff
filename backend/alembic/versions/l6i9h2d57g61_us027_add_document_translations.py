"""US-027 TASK-005: Add translations and metadata JSONB columns to document table

Adds translations and metadata columns to support multi-language patient
instructions (US-027):

Document table changes:
    - translations: JSONB NULL
      Per-language patient instruction content keyed by BCP-47 code.
      JSON schema: Dict[str, TranslationEntry].
      Populated by PatientInstructionsGenerator.
    
    - metadata: JSONB NULL
      Document-level metadata dict.
      Keys for US-027: language_fallback (bool), requested_language (str | null).
      Also used by future agents for document-type-specific metadata.

Revision ID: l6i9h2d57g61
Revises:     k5h8g1c46f50
Create Date: 2026-07-25

Design refs:
    US-027 AC3  — Document.translations stores per-language content
    US-027 AC4  — Document.metadata records language_fallback and requested_language
    US-027 DoD  — Patient instructions persisted with translation quality metadata
    TASK-027-004 — PatientInstructionsTranslator produces translations dict
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic
revision = "l6i9h2d57g61"
down_revision = "k5h8g1c46f50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add translations and metadata JSONB columns to document table."""
    op.add_column(
        "document",
        sa.Column(
            "translations",
            JSONB,
            nullable=True,
            comment="Per-language patient instruction content keyed by BCP-47 code.",
        ),
    )
    op.add_column(
        "document",
        sa.Column(
            "metadata",
            JSONB,
            nullable=True,
            comment="Document-level metadata flags (language_fallback, requested_language, etc.).",
        ),
    )


def downgrade() -> None:
    """Remove translations and metadata columns from document table."""
    op.drop_column("document", "metadata")
    op.drop_column("document", "translations")
