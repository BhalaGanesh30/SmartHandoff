"""SQLAlchemy ORM model for the care_escalation table.

Tracks the lifecycle of urgent patient escalations triggered by chatbot urgency flags.

Design refs:
    US-042 AC Scenarios 2, 3
    design.md §6.1 DR-001 (Alembic), DR-005 (soft deletes)
    ADR-001 (idempotency), ADR-007 (PHI containment)
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.app_user import AppUser
    from app.models.encounter import Encounter
    from app.models.patient import Patient


class CareEscalationStatus(str, enum.Enum):
    """Lifecycle states for a care escalation triggered by patient urgency flag.

    PENDING               : Initial notification sent to on-call nurse; awaiting acknowledgement.
    ACKNOWLEDGED          : Nurse acknowledged via PATCH /api/v1/care/escalations/{id}/acknowledge.
    ESCALATED_TO_SUPERVISOR: 15-minute SLA breached; supervisor notified; original escalation tagged.
    """

    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ESCALATED_TO_SUPERVISOR = "ESCALATED_TO_SUPERVISOR"


class CareEscalation(Base):
    """System-of-record for urgent patient escalations.

    Lifecycle:
        PENDING → ACKNOWLEDGED         (nurse acknowledges within 15 min)
        PENDING → ESCALATED_TO_SUPERVISOR  (APScheduler triggers after 15-min SLA breach)

    PHI policy:
        No patient PHI stored in this table. Patient name and contact details are
        resolved at notification dispatch time from the encrypted `patient` record
        (ADR-007). Only `patient_id` (UUID FK) is stored here for RBAC join queries.
    
    Attributes:
        id: UUID primary key
        encounter_id: FK to encounter that generated the urgency flag
        patient_id: FK to patient (used for RBAC scope checks)
        notified_nurse_user_id: FK to the on-call nurse who received the initial SMS alert
        status: Current lifecycle state (PENDING, ACKNOWLEDGED, ESCALATED_TO_SUPERVISOR)
        sent_at: UTC timestamp when initial CARE_TEAM_ESCALATION notification was published
        acknowledged_at: UTC timestamp when nurse acknowledged (null until acknowledged)
        acknowledged_by: FK to app_user who acknowledged (null until acknowledged)
        escalated_to_supervisor: True after 15-minute SLA breach and SUPERVISOR_ESCALATION published
        escalated_at: UTC timestamp when supervisor escalation triggered (null until escalated)
        idempotency_key: Prevents duplicate escalations on Pub/Sub redelivery. Format: ESC-{encounter_id}
        created_at: Record creation timestamp
        updated_at: Last update timestamp
        deleted_at: Soft-delete timestamp (DR-005). Active records have deleted_at=NULL
    """

    __tablename__ = "care_escalation"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_care_escalation_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Surrogate primary key",
    )
    
    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("encounter.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="FK to encounter that generated the urgency flag",
    )
    
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patient.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="FK to patient; used for RBAC scope checks",
    )
    
    notified_nurse_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to the on-call nurse who received the initial SMS alert",
    )
    
    status: Mapped[CareEscalationStatus] = mapped_column(
        nullable=False,
        default=CareEscalationStatus.PENDING,
        server_default="PENDING",
        comment="Current lifecycle state of the escalation",
    )
    
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="UTC timestamp when the initial CARE_TEAM_ESCALATION notification was published",
    )
    
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when the nurse acknowledged (via PATCH endpoint). Null until acknowledged",
    )
    
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to the app_user who acknowledged. Null until acknowledged",
    )
    
    escalated_to_supervisor: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True after the 15-minute SLA is breached and a SUPERVISOR_ESCALATION is published",
    )
    
    escalated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when the supervisor escalation was triggered. Null until escalated",
    )
    
    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="Idempotency key preventing duplicate escalations on Pub/Sub redelivery. Format: ESC-{encounter_id}",
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Soft-delete timestamp (DR-005). Active records have deleted_at=NULL",
    )

    # Relationships
    encounter: Mapped[Encounter] = relationship(
        "Encounter",
        foreign_keys=[encounter_id],
        lazy="select",
    )
    
    patient: Mapped[Patient] = relationship(
        "Patient",
        foreign_keys=[patient_id],
        lazy="select",
    )
    
    notified_nurse: Mapped[AppUser | None] = relationship(
        "AppUser",
        foreign_keys=[notified_nurse_user_id],
        lazy="select",
    )
    
    acknowledging_user: Mapped[AppUser | None] = relationship(
        "AppUser",
        foreign_keys=[acknowledged_by],
        lazy="select",
    )
