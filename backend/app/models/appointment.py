"""SQLAlchemy ORM model for the `appointment` table.

Stores follow-up appointment records created by the FollowUpCareAgent
after risk score calculation at patient discharge (A03 event).

Appointment lifecycle:
    SCHEDULED → CONFIRMED → COMPLETED
                          → MISSED

Phase 1 constraint (C-03): internal SmartHandoff record only.
FHIR write-back deferred to Phase 2.

Design refs:
    US-040 AC Scenarios 2, 3, 4 — appointment_type, target_date, status, assigned_user_id
    US-040 Technical Notes — status lifecycle; care manager assignment
    design.md §6.1 DR-001 — all DDL via Alembic
    design.md §6.1 DR-005 — soft delete (deleted_at)
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.app_user import AppUser
    from app.models.encounter import Encounter


class AppointmentType(str, enum.Enum):
    """Follow-up appointment type determined by risk tier (US-040).
    
    Mapping to risk tier and target date offset:
        HIGH_RISK_FOLLOW_UP   → risk_tier = HIGH,   target_date = discharge_date + 7 days
        STANDARD_FOLLOW_UP    → risk_tier = MEDIUM, target_date = discharge_date + 14 days
        ROUTINE_FOLLOW_UP     → risk_tier = LOW,    target_date = discharge_date + 30 days
    """

    HIGH_RISK_FOLLOW_UP = "HIGH_RISK_FOLLOW_UP"
    STANDARD_FOLLOW_UP = "STANDARD_FOLLOW_UP"
    ROUTINE_FOLLOW_UP = "ROUTINE_FOLLOW_UP"


class AppointmentStatus(str, enum.Enum):
    """Appointment lifecycle status (US-040 Technical Notes).
    
    Lifecycle transitions:
        SCHEDULED → CONFIRMED → COMPLETED
                              → MISSED
    
    Status definitions:
        SCHEDULED: Initial status when appointment created by FollowUpCareAgent
        CONFIRMED: Patient/care manager confirmed attendance (manual update)
        COMPLETED: Follow-up visit completed (manual update)
        MISSED: Patient did not attend scheduled appointment (manual update)
    """

    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"


class Appointment(Base, TimestampMixin, SoftDeleteMixin):
    """Follow-up appointment created by the FollowUpCareAgent post-discharge.

    One appointment record is created per encounter per discharge event.
    Additional appointments may be created if a re-admission occurs.

    Attributes:
        id:               UUID primary key.
        encounter_id:     FK → encounter.id. Cascade delete follows encounter.
        appointment_type: Tier-determined type (HIGH_RISK_FOLLOW_UP / STANDARD / ROUTINE).
        target_date:      Calendar date of the required follow-up appointment.
        status:           Current status in the lifecycle (SCHEDULED | CONFIRMED | COMPLETED | MISSED).
        assigned_user_id: FK → app_user.id — care manager assigned for HIGH-risk tier.
                          NULL for MEDIUM and LOW tiers (no mandatory care manager).
        created_at:       Server-side UTC timestamp at record creation (from TimestampMixin).
        updated_at:       Server-side UTC timestamp updated on every change (from TimestampMixin).
        deleted_at:       Soft-delete timestamp; NULL for active records (from SoftDeleteMixin, DR-005).
    """

    __tablename__ = "appointment"
    __table_args__ = (
        sa.UniqueConstraint(
            "encounter_id",
            "appointment_type",
            name="uq_appointment_encounter_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    encounter_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("encounter.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_type: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        comment="AppointmentType enum value",
    )
    target_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        comment="Calendar date by which follow-up must occur",
    )
    status: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default=AppointmentStatus.SCHEDULED.value,
        comment="AppointmentStatus lifecycle value",
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Care manager assigned for HIGH-risk follow-up; NULL for MEDIUM/LOW",
    )

    # Relationships (lazy by default — do not eager-load in agent context)
    encounter: Mapped["Encounter"] = relationship(
        "Encounter",
        back_populates="appointments",
        lazy="select",
    )
    assigned_user: Mapped["AppUser | None"] = relationship(
        "AppUser",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id} "
            f"encounter_id={self.encounter_id} "
            f"type={self.appointment_type} "
            f"status={self.status} "
            f"target_date={self.target_date}>"
        )
