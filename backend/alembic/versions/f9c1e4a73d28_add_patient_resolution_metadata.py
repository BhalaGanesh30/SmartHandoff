"""US-019 TASK-001: Add patient resolution metadata and encounter status

Adds patient identity resolution tracking fields to support MRN primary lookup
and name+DOB fallback resolution strategies (US-019):

Patient table changes:
    - resolution_method: VARCHAR(16) — tracks how patient was resolved (MRN, NAME_DOB, UNRESOLVED)
    - partial_match: BOOLEAN — flags fallback resolution via name+DOB
    - resolved_at: TIMESTAMP WITH TIME ZONE — timestamp of identity resolution

Encounter table changes:
    - patient_resolution_status: VARCHAR(16) — tracks resolution outcome (RESOLVED, AMBIGUOUS, UNRESOLVED)
    - Indexed for query performance on ambiguous/unresolved encounter filtering

Revision ID: f9c1e4a73d28
Revises:     f7a3e9c01d2b
Create Date: 2026-07-24 00:00:00.000000

Design refs:
    US-019 AC1  — Patient resolution metadata tracking
    US-019 AC6  — Encounter resolution status field
    DR-024      — Patient identity resolution requirements
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "f9c1e4a73d28"
down_revision: Union[str, None] = "f7a3e9c01d2b"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """Add patient resolution metadata fields to patient and encounter tables."""
    
    # Add resolution tracking fields to patient table
    op.add_column(
        "patient",
        sa.Column(
            "resolution_method",
            sa.String(length=16),
            nullable=False,
            server_default="MRN",
            comment="Method used to resolve patient identity: MRN, NAME_DOB, or UNRESOLVED (US-019)",
        ),
    )
    
    op.add_column(
        "patient",
        sa.Column(
            "partial_match",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="True if patient was resolved via fallback method (name+DOB) (US-019)",
        ),
    )
    
    op.add_column(
        "patient",
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when patient identity was resolved (US-019)",
        ),
    )
    
    # Add resolution status to encounter table
    op.add_column(
        "encounter",
        sa.Column(
            "patient_resolution_status",
            sa.String(length=16),
            nullable=False,
            server_default="RESOLVED",
            comment="Status of patient identity resolution: RESOLVED, AMBIGUOUS, or UNRESOLVED (US-019)",
        ),
    )
    
    # Create index on patient_resolution_status for query performance
    op.create_index(
        "ix_encounter_patient_resolution_status",
        "encounter",
        ["patient_resolution_status"],
        unique=False,
    )


def downgrade() -> None:
    """Remove patient resolution metadata fields from patient and encounter tables."""
    
    # Drop encounter index and column
    op.drop_index("ix_encounter_patient_resolution_status", table_name="encounter")
    op.drop_column("encounter", "patient_resolution_status")
    
    # Drop patient columns
    op.drop_column("patient", "resolved_at")
    op.drop_column("patient", "partial_match")
    op.drop_column("patient", "resolution_method")
