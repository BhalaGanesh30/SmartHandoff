"""Notification audit log API router.

Endpoints:
    GET /api/v1/notifications — Returns notification delivery history for an encounter.

Auth:
    Staff JWT required. Patient JWTs are rejected (role guard).

Query:
    Routes to PostgreSQL read replica (ADR-006, TR-010) via ``get_read_db``.

PHI minimisation:
    Response never includes plaintext phone or email.
    Only hashed values (recipient_phone_hash, recipient_email_hash) are returned.

Design refs:
    US-067 AC Scenario 1, design.md §3.3, ADR-006, SEC-006.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import require_role
from app.db.deps import get_read_db
from app.models.notification import Notification
from app.schemas.notification_log import NotificationLogItem, NotificationLogResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])

STAFF_ROLES = ["NURSE", "PHYSICIAN", "CARE_COORDINATOR", "ADMIN"]


@router.get(
    "",
    response_model=NotificationLogResponse,
    summary="List notification delivery history for an encounter",
    description=(
        "Returns all notification records for the specified encounter. "
        "Staff JWT required. PHI is excluded from all response fields."
    ),
)
async def list_notifications(
    encounter_id: UUID = Query(..., description="Encounter UUID to retrieve notifications for"),
    db: AsyncSession = Depends(get_read_db),
    _current_user=Depends(require_role(STAFF_ROLES)),
) -> NotificationLogResponse:
    """Return notification delivery history for an encounter.

    Queries the PostgreSQL read replica for performance (TR-010).
    Returns notification records ordered by ``sent_at`` descending.
    No PHI is included in the response body.

    Args:
        encounter_id: Required. Filters notifications to this encounter.
        db: Read-replica AsyncSession (injected via dependency).
        _current_user: Enforces staff role; raises 403 if patient JWT.

    Returns:
        NotificationLogResponse with total count and list of delivery records.
    """
    stmt = (
        select(Notification)
        .where(Notification.encounter_id == encounter_id)
        .order_by(Notification.sent_at.desc().nullslast())
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    items = [
        NotificationLogItem.model_validate(
            {
                "id": record.id,
                "type": record.type.value,
                "channel": record.type.value,  # type is the channel (SMS/EMAIL)
                "sent_at": record.sent_at,
                "delivery_status": record.delivery_status.value,
                "template_name": record.template,
                "urgency_override": record.urgency_override,
                "recipient_phone_hash": record.recipient_phone_hash,
                "recipient_email_hash": record.recipient_email_hash,
            }
        )
        for record in records
    ]

    return NotificationLogResponse(
        encounter_id=encounter_id,
        total=len(items),
        items=items,
    )
