"""Care escalation monitoring module.

Processes URGENCY_FLAG_SET events from the chatbot agent and creates
initial care team escalation notifications.

Design refs:
    US-042 — Care escalation monitoring for urgent patient flags
    design.md §3.2 — Agent container pattern
"""
from __future__ import annotations

from app.agents.followup_care.escalation.monitor import CareEscalationMonitor
from app.agents.followup_care.escalation.reescalation_job import ReEscalationJob
from app.agents.followup_care.escalation.schemas import (
    CareTeamEscalationMessage,
    UrgencyFlagSetEvent,
)

__all__ = [
    "CareEscalationMonitor",
    "CareTeamEscalationMessage",
    "ReEscalationJob",
    "UrgencyFlagSetEvent",
]
