"""CarePathwayService — care manager assignment and appointment record creation.

Called by FollowUpCareAgent.process() after risk score persistence (US-039/TASK-004)
to activate the appropriate care pathway based on the calculated risk tier.

Responsibilities:
    1. Resolve care manager: round-robin from app_user WHERE role='CARE_MANAGER'
       AND unit = encounter.unit (HIGH tier only; None for MEDIUM/LOW).
    2. Create appointment record with tier-specific target_date and appointment_type.

Care manager assignment uses deterministic round-robin:
    pool_index = hash(str(encounter_id)) % len(care_manager_pool)
This ensures the same encounter always maps to the same care manager on retry,
preventing duplicate assignments on Pub/Sub redelivery (idempotency guarantee).

Phase 1 constraint: no FHIR write-back (C-03). Appointment is an internal record only.

Design refs:
    US-040 AC Scenarios 2, 3, 4
    US-040 Technical Notes — round-robin care manager assignment by unit
    design.md §6.1 DR-001 — all writes through ORM; no raw SQL in services
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.care_pathways import CarePathwayConfig, TierPathwayConfig
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.app_user import AppUser
from app.models.encounter import Encounter

logger = logging.getLogger(__name__)


class CarePathwayService:
    """Stateless service for care pathway activation.

    All methods are async and accept an injected `AsyncSession` — the session
    lifecycle (commit/rollback) is managed by the caller (FollowUpCareAgent).

    Args:
        pathways: Loaded CarePathwayConfig from config/care_pathways.yaml (TASK-002).
    """

    def __init__(self, pathways: CarePathwayConfig) -> None:
        self._pathways = pathways

    async def activate_pathway(
        self,
        encounter: Encounter,
        risk_tier: str,
        discharge_date: date,
        db: AsyncSession,
    ) -> Appointment:
        """Create appointment record and assign care manager for HIGH risk tier.

        Args:
            encounter:      ORM Encounter object (must have .id, .unit loaded).
            risk_tier:      Risk tier string: HIGH | MEDIUM | LOW.
            discharge_date: Date of discharge from the A03 ADT event.
            db:             Async database session (write path — Cloud SQL Primary).

        Returns:
            The newly created and flushed (not yet committed) Appointment ORM object.

        Raises:
            KeyError: If risk_tier is not in care_pathways.yaml (unexpected tier value).
            sqlalchemy.exc.IntegrityError: On duplicate (encounter_id, appointment_type)
                — indicates Pub/Sub redelivery; caller should treat as idempotent and skip.
        """
        pathway_config: TierPathwayConfig = self._pathways[risk_tier]

        assigned_user_id: uuid.UUID | None = None
        if pathway_config.alert_care_manager:
            assigned_user_id = await self._assign_care_manager(
                encounter_id=encounter.id,
                unit=encounter.unit,
                db=db,
            )

        target_date = discharge_date + timedelta(days=pathway_config.followup_days)

        appointment = Appointment(
            encounter_id=encounter.id,
            appointment_type=AppointmentType(pathway_config.appointment_type).value,
            target_date=target_date,
            status=AppointmentStatus.SCHEDULED.value,
            assigned_user_id=assigned_user_id,
        )
        db.add(appointment)
        await db.flush()  # Populates appointment.id without committing

        logger.info(
            "Care pathway activated",
            extra={
                "encounter_id": str(encounter.id),
                "risk_tier": risk_tier,
                "appointment_type": appointment.appointment_type,
                "target_date": str(target_date),
                "assigned_user_id": str(assigned_user_id) if assigned_user_id else None,
            },
        )
        return appointment

    async def _assign_care_manager(
        self,
        encounter_id: uuid.UUID,
        unit: str,
        db: AsyncSession,
    ) -> uuid.UUID | None:
        """Deterministic round-robin care manager selection by unit.

        Queries app_user WHERE role='CARE_MANAGER' AND unit = encounter.unit,
        ordered by id ASC for stable ordering across instances.

        Uses hash(str(encounter_id)) % len(pool) for deterministic assignment —
        the same encounter always maps to the same care manager on retry,
        preventing duplicate notifications on Pub/Sub redelivery.

        Args:
            encounter_id: UUID of the encounter (used as hash seed).
            unit:         Hospital unit string from encounter.unit.
            db:           Async DB session (read-only path within this method).

        Returns:
            UUID of the assigned care manager, or None if no care managers exist for the unit.
        """
        result = await db.execute(
            select(AppUser.id)
            .where(
                AppUser.role == "CARE_MANAGER",
                AppUser.unit == unit,
                AppUser.is_active == True,  # noqa: E712
            )
            .order_by(AppUser.id.asc())
        )
        pool: list[uuid.UUID] = list(result.scalars().all())

        if not pool:
            logger.warning(
                "No CARE_MANAGER users found for unit — appointment created without assignment",
                extra={"unit": unit, "encounter_id": str(encounter_id)},
            )
            return None

        pool_index = hash(str(encounter_id)) % len(pool)
        selected_id: uuid.UUID = pool[pool_index]

        logger.info(
            "Care manager assigned",
            extra={
                "assigned_user_id": str(selected_id),
                "pool_size": len(pool),
                "unit": unit,
            },
        )
        return selected_id
