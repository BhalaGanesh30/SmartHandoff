"""Medication ORM model — patient medication list per encounter.

Used by the Medication Reconciliation Agent (FR-030–FR-035).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.encounter import Encounter


class ReconciliationCategory(str, enum.Enum):
    """Three-way medication reconciliation outcome category."""
    CONTINUED = "CONTINUED"
    NEW = "NEW"
    STOPPED = "STOPPED"
    DOSE_CHANGED = "DOSE_CHANGED"


class ReconciliationFlag(str, enum.Enum):
    """Special alert flags raised during reconciliation."""
    DUPLICATE = "DUPLICATE"
    STOPPED_WITHOUT_ORDER = "STOPPED_WITHOUT_ORDER"


class MedicationListSource(str, enum.Enum):
    """FHIR list from which a medication was sourced."""
    PRE_ADMIT = "PRE_ADMIT"
    INPATIENT = "INPATIENT"
    DISCHARGE = "DISCHARGE"


class Medication(Base, TimestampMixin):
    """A medication record associated with a patient encounter.

    Populated by the Medication Reconciliation Agent from FHIR
    MedicationRequest resources. Interaction severity set by RxNav API (AIR-050).
    """

    __tablename__ = "medication"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("encounter.id", ondelete="CASCADE"),
        nullable=False,
    )

    drug_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    rxcui: Mapped[str | None] = mapped_column(
        sa.String(32),
        nullable=True,
        comment="RxNorm Concept Unique Identifier for drug interaction lookups (AIR-050)",
    )
    dose: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    route: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    frequency: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)

    source: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        server_default="admission",
        comment="One of: admission, discharge, home — reconciliation list source",
    )

    interaction_severity: Mapped[str | None] = mapped_column(
        sa.String(16),
        nullable=True,
        comment="One of: HIGH, MEDIUM, LOW — from RxNav interaction check (AIR-051)",
    )

    reconciliation_status: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        server_default="pending",
        comment="One of: pending, reconciled, flagged, incomplete",
    )

    # US-030 TASK-001: New reconciliation fields
    rxnorm_cui: Mapped[str | None] = mapped_column(
        sa.String(20),
        nullable=True,
        index=True,
        comment="RxNorm CUI from RxNav API for drug normalization",
    )
    
    reconciliation_category: Mapped[ReconciliationCategory | None] = mapped_column(
        sa.Enum(ReconciliationCategory),
        nullable=True,
        index=True,
        comment="CONTINUED | NEW | STOPPED | DOSE_CHANGED",
    )
    
    flags: Mapped[list[ReconciliationFlag]] = mapped_column(
        ARRAY(sa.Enum(ReconciliationFlag, name="reconciliationflag")),
        nullable=False,
        server_default="{}",
        comment="DUPLICATE, STOPPED_WITHOUT_ORDER flags",
    )
    
    dose_value: Mapped[float | None] = mapped_column(
        sa.Float,
        nullable=True,
        comment="Parsed numeric dose value",
    )
    
    dose_unit: Mapped[str | None] = mapped_column(
        sa.String(20),
        nullable=True,
        comment="Dose unit e.g. mg",
    )
    
    sources: Mapped[list[MedicationListSource]] = mapped_column(
        ARRAY(sa.Enum(MedicationListSource, name="medicationlistsource")),
        nullable=False,
        server_default="{}",
        comment="Which FHIR lists this drug appears on",
    )
    
    reconciliation_completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when reconciliation was completed for this medication",
    )

    encounter: Mapped["Encounter"] = relationship(
        "Encounter",
        back_populates="medications",
        lazy="select",
    )

    __table_args__ = (
        sa.Index("ix_medication_encounter_id", "encounter_id"),
        sa.Index("ix_medication_rxcui", "rxcui"),
        sa.Index("ix_medication_severity", "interaction_severity"),
    )
