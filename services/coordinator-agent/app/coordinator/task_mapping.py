"""Event-type to agent-task-type mapping configuration.

Defines which ``AgentTaskType`` values are created for each ADT event type.
This is the sole source-of-truth for coordinator routing logic; adding a new
ADT event type or new agent only requires updating ``TASK_TYPE_MAP``.

Design refs:
    FR-010  — coordinator orchestrates task assignment to all 5 specialist agents
    US-020  — SC-2: only relevant tasks created per event type
"""
from __future__ import annotations

from enum import StrEnum


class ADTEventType(StrEnum):
    """ADT event type codes from HL7 MSH-9 message type."""

    ADMIT = "ADT^A01"
    TRANSFER = "ADT^A02"
    DISCHARGE = "ADT^A03"
    CANCEL_ADMIT = "ADT^A11"
    CANCEL_DISCHARGE = "ADT^A13"


class AgentTaskType(StrEnum):
    """Agent task type identifiers — align with downstream agent subscriptions."""

    DOCUMENTATION = "DOCUMENTATION"
    MEDICATION_RECONCILIATION = "MEDICATION_RECONCILIATION"
    BED_MANAGEMENT = "BED_MANAGEMENT"
    FOLLOW_UP_CARE = "FOLLOW_UP_CARE"
    PATIENT_COMMUNICATION = "PATIENT_COMMUNICATION"
    TRANSFER_NOTE = "TRANSFER_NOTE"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"


# ---------------------------------------------------------------------------
# Task routing map — event type → list of task types to create
# ---------------------------------------------------------------------------

TASK_TYPE_MAP: dict[ADTEventType, list[AgentTaskType]] = {
    ADTEventType.ADMIT: [
        AgentTaskType.DOCUMENTATION,
        AgentTaskType.MEDICATION_RECONCILIATION,
        AgentTaskType.BED_MANAGEMENT,
        AgentTaskType.FOLLOW_UP_CARE,
        AgentTaskType.PATIENT_COMMUNICATION,
    ],
    ADTEventType.TRANSFER: [
        AgentTaskType.TRANSFER_NOTE,
        AgentTaskType.BED_MANAGEMENT,
    ],
    ADTEventType.DISCHARGE: [
        AgentTaskType.DISCHARGE_SUMMARY,
        AgentTaskType.MEDICATION_RECONCILIATION,
        AgentTaskType.FOLLOW_UP_CARE,
        AgentTaskType.PATIENT_COMMUNICATION,
    ],
    ADTEventType.CANCEL_ADMIT: [
        AgentTaskType.BED_MANAGEMENT,
    ],
    ADTEventType.CANCEL_DISCHARGE: [
        AgentTaskType.BED_MANAGEMENT,
        AgentTaskType.FOLLOW_UP_CARE,
    ],
}


def get_task_types_for_event(event_type: str) -> list[AgentTaskType]:
    """Return the list of ``AgentTaskType`` values for a given ADT event type.

    Args:
        event_type: ADT event type string, e.g. ``"ADT^A01"``.

    Returns:
        List of ``AgentTaskType`` enum members. Returns empty list for
        unrecognised event types (no tasks created — logged as warning).
    """
    try:
        adt_type = ADTEventType(event_type)
    except ValueError:
        return []
    return TASK_TYPE_MAP.get(adt_type, [])
