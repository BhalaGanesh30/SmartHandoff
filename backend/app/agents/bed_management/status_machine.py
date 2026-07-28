"""Bed status state machine for ADT event-driven transitions.

Enforces allowed status transitions per event type:
    A01 (admit)     : any → OCCUPIED
    A02 (transfer)  : old bed OCCUPIED → DIRTY; new bed any → OCCUPIED
    A03 (discharge) : OCCUPIED → DIRTY

Design refs:
    US-035 Technical Notes — status enum and transition rules
    US-035 AC Scenario 1   — A01 → OCCUPIED
    US-035 AC Scenario 2   — A03 → DIRTY
"""
from __future__ import annotations

import logging

from app.agents.bed_management.schemas import BedStatus
from app.exceptions import BedStatusTransitionError

logger = logging.getLogger(__name__)

# Mapping: event_type → (required current statuses, target status)
# None in current_statuses means any status is valid (e.g. force-admit)
_TRANSITION_MAP: dict[str, tuple[set[BedStatus] | None, BedStatus]] = {
    "A01": (None, BedStatus.OCCUPIED),           # admit — any → OCCUPIED
    "A03": ({BedStatus.OCCUPIED}, BedStatus.DIRTY),  # discharge — OCCUPIED → DIRTY
}


def resolve_target_status(event_type: str, current_status: BedStatus) -> BedStatus:
    """Return the target BedStatus for a given ADT event type.

    Args:
        event_type: HL7 ADT message type (e.g. ``"A01"``).
        current_status: The bed's current status before the event.

    Returns:
        Target ``BedStatus`` after the transition.

    Raises:
        BedStatusTransitionError: If the transition is not permitted.
        ValueError: If the ``event_type`` is not handled by this agent.
    """
    if event_type not in _TRANSITION_MAP and event_type != "A02":
        raise ValueError(f"BedManagementAgent does not handle event type: {event_type}")

    if event_type == "A02":
        # A02 (transfer): handled separately — two bed updates required
        return BedStatus.OCCUPIED

    allowed_current, target = _TRANSITION_MAP[event_type]
    if allowed_current is not None and current_status not in allowed_current:
        raise BedStatusTransitionError(
            f"Cannot transition bed from {current_status} via {event_type}. "
            f"Allowed current statuses: {allowed_current}"
        )
    logger.debug(
        "Bed status transition approved: %s → %s (event=%s)",
        current_status,
        target,
        event_type,
    )
    return target
