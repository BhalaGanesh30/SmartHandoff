"""Document ORM model — AI-generated clinical documents.

DR-013: Document content (PHI) encrypted at rest via EncryptedString (US-007).
DR-013: Retained 7 years with encounter.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.encryption import EncryptedText
from app.db.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.app_user import AppUser
    from app.models.encounter import Encounter


class DocumentStatus(str, enum.Enum):
    """Valid document lifecycle statuses.

    CANCELLED is set by US-015 CancellationService (A11/A13 events).
    Content is retained on CANCELLED — no hard delete (DR-005, US-015 DoD).
    """

    DRAFT            = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED         = "approved"
    REJECTED         = "rejected"
    CANCELLED        = "cancelled"   # US-015: soft-cancel on A11/A13


class Document(Base, TimestampMixin):
    """AI-generated clinical document (discharge summary, patient instructions, etc.).

    `content` is encrypted via EncryptedString TypeDecorator (US-007).
    Human approval is required before status transitions to 'approved' (FR-020).
    """

    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("encounter.id", ondelete="RESTRICT"),
        nullable=False,
    )

    document_type: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        comment=(
            "One of: discharge_summary, patient_instructions, "
            "medication_reconciliation, follow_up_plan"
        ),
    )

    # PHI content encrypted via US-007 EncryptedText (DR-002, DR-013)
    # EncryptedText uses PostgreSQL TEXT (no length cap) to accommodate
    # multi-KB discharge summaries without VARCHAR truncation.
    content: Mapped[str] = mapped_column(
        EncryptedText(),
        nullable=False,
        comment="Document body — AES-256-GCM encrypted (US-007)",
    )

    language_code: Mapped[str] = mapped_column(
        sa.String(8),
        nullable=False,
        server_default="en",
        comment="Document language (FR-022): en, es, fr, zh, pt",
    )

    status: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        server_default="draft",
        comment="One of: draft, pending_approval, approved, rejected",
    )

    generation_type: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        server_default="LLM",
        comment="One of: LLM, TEMPLATE — TEMPLATE set on Vertex AI fallback (AIR-022)",
    )

    # Completeness validation result (populated by CompletenessValidator post-generation)
    completeness_status: Mapped[str | None] = mapped_column(
        sa.String(20),
        nullable=True,
        default=None,
        comment="COMPLETE or INCOMPLETE — set by CompletenessValidator after document generation",
    )

    missing_fields: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        server_default="'[]'::jsonb",
        comment="Ordered list of field names absent from the document. Empty list when COMPLETE.",
    )

    # US-027: Per-language patient instructions (PatientInstructionsDocument.translations)
    translations: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment=(
            "Per-language patient instruction content keyed by BCP-47 code. "
            "JSON schema: Dict[str, TranslationEntry]. Populated by PatientInstructionsGenerator."
        ),
    )

    # US-027: Document-level metadata flags including language_fallback and requested_language
    # Also used by future agents for document-type-specific metadata
    document_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=None,
        comment=(
            "Arbitrary document metadata dict. "
            "Keys for US-027: language_fallback (bool), requested_language (str | null)."
        ),
    )

    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── US-029 fields ──────────────────────────────────────────────────────────
    ai_assisted_label: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("FALSE"),
        comment="TRUE for all AI-generated documents. Permanent — never reset after approval.",
    )
    """Permanent AI provenance flag (BR-011). Set by the Documentation Agent on insert."""

    approved_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="UTC timestamp when a physician approved this document.",
    )
    """NULL until a physician calls PATCH …/approve (US-029 Scenario 4)."""

    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment="FK to the approving clinician; drives the 'Approved by …' footer.",
    )
    """References app_user.id. Populated together with approved_at."""

    encounter: Mapped["Encounter"] = relationship(
        "Encounter",
        back_populates="documents",
        lazy="select",
    )

    reviewed_by_user: Mapped["AppUser | None"] = relationship(
        "AppUser",
        foreign_keys=[reviewed_by_user_id],
        lazy="joined",  # Eager-load for the 'Approved by' footer
    )

    __table_args__ = (
        sa.Index("ix_document_encounter_type", "encounter_id", "document_type"),
        sa.Index("ix_document_status", "status"),
    )
