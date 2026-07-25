"""US-029 TASK-001: Add ai_assisted_label, approved_at, and reviewed_by_user_id to document table

Adds three fields to support AI provenance tracking and approval workflow:

Document table changes:
    - ai_assisted_label: BOOLEAN NOT NULL DEFAULT FALSE
      Permanent provenance flag set to TRUE for all AI-generated documents.
      Never reset after approval (BR-011).
    
    - approved_at: TIMESTAMPTZ NULL
      UTC timestamp of clinician approval. NULL until approved.
    
    - reviewed_by_user_id: UUID NULL FK → app_user(id)
      Identity of the approving clinician for the "Approved by" footer.
      SET NULL on user deletion.

Backfills ai_assisted_label=TRUE for existing AI-generated documents based on
generation_type='LLM' field.

Revision ID: m7j0i3e58h62
Revises:     b8e2f5c93a17
Create Date: 2026-07-16

Design refs:
    US-029 AC Scenario 4 — Approval metadata tracking
    US-029 DoD — Document.ai_assisted_label boolean field
    BR-011 — AI-generated content provenance
    TASK-029-001 — Schema extension for approval workflow
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic
revision = "m7j0i3e58h62"
down_revision = "b8e2f5c93a17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add ai_assisted_label, approved_at, and reviewed_by_user_id to document table."""
    
    # 1. Add ai_assisted_label with server default FALSE
    op.add_column(
        "document",
        sa.Column(
            "ai_assisted_label",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="TRUE for all AI-generated documents (permanent provenance flag).",
        ),
    )

    # 2. Add approved_at (nullable timestamptz)
    op.add_column(
        "document",
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC timestamp of clinician approval; NULL for unapproved documents.",
        ),
    )

    # 3. Add reviewed_by_user_id FK → app_user(id)
    op.add_column(
        "document",
        sa.Column(
            "reviewed_by_user_id",
            sa.UUID(),
            nullable=True,
            comment="UUID of the approving clinician.",
        ),
    )
    
    op.create_foreign_key(
        "fk_document_reviewed_by_user_id",
        "document",
        "app_user",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. Backfill: set ai_assisted_label=TRUE for all AI-generated documents
    #    (generation_type='LLM' indicates AI generation vs 'TEMPLATE' fallback)
    op.execute(
        """
        UPDATE document
        SET    ai_assisted_label = TRUE
        WHERE  generation_type = 'LLM'
           AND ai_assisted_label = FALSE
        """
    )


def downgrade() -> None:
    """Remove ai_assisted_label, approved_at, and reviewed_by_user_id from document table."""
    op.drop_constraint("fk_document_reviewed_by_user_id", "document", type_="foreignkey")
    op.drop_column("document", "reviewed_by_user_id")
    op.drop_column("document", "approved_at")
    op.drop_column("document", "ai_assisted_label")
