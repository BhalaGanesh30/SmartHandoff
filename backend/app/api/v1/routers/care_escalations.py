"""FastAPI router for care escalation acknowledgement.

Endpoint:
    PATCH /api/v1/care/escalations/{escalation_id}/acknowledge

RBAC:
    Admin        : ✓
    Physician    : ✓
    Nurse        : ✓
    Charge Nurse : ✓
    Pharmacist   : ✗ (403)
    Bed Manager  : ✗ (403)
    Patient      : ✗ (403)

Business rules:
    200 OK        : Acknowledged successfully; status=ACKNOWLEDGED, acknowledged_at set.
    403 Forbidden : Role not permitted (patient, pharmacist, bed_manager).
    404 Not Found : escalation_id not found or soft-deleted.
    409 Conflict  : Escalation already acknowledged (status=ACKNOWLEDGED).

Design refs:
    design.md §3.3 — FastAPI routers
    design.md §8.3 — RBAC permission matrix
    US-042 AC Scenarios 2, 4
    ADR-006 — write path uses primary DB session
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.jwt import TokenClaims, get_current_user
from app.db.deps import get_write_db
from app.models.care_escalation import CareEscalation, CareEscalationStatus
from app.schemas.care_escalation import CareEscalationAcknowledgeResponse

router = APIRouter(prefix="/care", tags=["care-escalations"])
logger = logging.getLogger(__name__)

# Allowed roles for acknowledgement endpoint (US-042 AC Scenario 4)
_ALLOWED_ROLES = {"admin", "physician", "nurse", "charge_nurse"}


def _require_any_role(allowed_roles: set[str]) -> callable:
    """Dependency factory to enforce role membership check.
    
    Returns a FastAPI dependency that raises 403 if the current user's role
    is not in the allowed set.
    
    Args:
        allowed_roles: Set of role strings that are permitted
        
    Returns:
        Async dependency callable
    """
    async def _check_role(
        current_user: TokenClaims = Depends(get_current_user),
    ) -> TokenClaims:
        if current_user.role not in allowed_roles:
            logger.info(
                "care_escalation.rbac_denial",
                extra={
                    "user_id": current_user.sub,
                    "role": current_user.role,
                    "required_roles": list(allowed_roles),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return current_user
    return _check_role


@router.patch(
    "/escalations/{escalation_id}/acknowledge",
    response_model=CareEscalationAcknowledgeResponse,
    status_code=status.HTTP_200_OK,
    summary="Acknowledge an urgent patient escalation alert",
    responses={
        200: {"description": "Escalation acknowledged successfully"},
        401: {"description": "Missing or invalid JWT"},
        403: {"description": "Role not permitted (patient, pharmacist, bed_manager)"},
        404: {"description": "Escalation not found or soft-deleted"},
        409: {"description": "Escalation already acknowledged"},
    },
)
async def acknowledge_escalation(
    escalation_id: UUID,
    session: AsyncSession = Depends(get_write_db),
    current_user: TokenClaims = Depends(_require_any_role(_ALLOWED_ROLES)),
) -> CareEscalationAcknowledgeResponse:
    """Mark a care escalation as acknowledged by a staff member.

    Sets status=ACKNOWLEDGED, acknowledged_at=now(), acknowledged_by=current_user.sub.
    Returns 409 Conflict if already acknowledged (prevents double-counting).
    The HIPAA audit middleware logs this access automatically — no manual audit write needed.

    Args:
        escalation_id: UUID of the care escalation to acknowledge.
        session:       Async write DB session (primary PostgreSQL).
        current_user:  Validated JWT payload (injected by auth middleware).

    Returns:
        CareEscalationAcknowledgeResponse with updated fields.

    Raises:
        HTTPException(403): Role not permitted.
        HTTPException(404): Escalation not found or soft-deleted.
        HTTPException(409): Escalation already acknowledged.
    """
    # Fetch from write replica to avoid replication lag on the acknowledged_at check
    result = await session.execute(
        select(CareEscalation).where(
            CareEscalation.id == escalation_id,
            CareEscalation.deleted_at.is_(None),
        )
    )
    escalation: CareEscalation | None = result.scalar_one_or_none()

    if escalation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Care escalation {escalation_id} not found.",
        )

    if escalation.status == CareEscalationStatus.ACKNOWLEDGED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Escalation has already been acknowledged.",
        )

    now = datetime.now(tz=timezone.utc)
    escalation.status = CareEscalationStatus.ACKNOWLEDGED
    escalation.acknowledged_at = now
    escalation.acknowledged_by = UUID(current_user.sub)

    session.add(escalation)
    await session.commit()
    await session.refresh(escalation)

    logger.info(
        "care_escalation.acknowledged",
        extra={
            "escalation_id": str(escalation.id),
            "encounter_id": str(escalation.encounter_id),
            "acknowledged_by": current_user.sub,
        },
    )

    return CareEscalationAcknowledgeResponse.model_validate(escalation)
