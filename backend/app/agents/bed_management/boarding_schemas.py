"""Pydantic schemas and dataclasses for ED boarding alert workflow.

Shared between BoardingMonitor (detection) and BoardingAlertPublisher (dispatch).

Design refs:
    US-038 AC Scenario 1 — BoardingCandidate fields
    US-038 AC Scenario 4 — idempotency_key construction
    US-038 TASK-002 — BoardingCandidate dataclass definition
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True, slots=True)
class BoardingCandidate:
    """Encounter identified by BoardingMonitor as eligible for a boarding alert.

    Immutable — produced by the monitor; consumed by the publisher.

    Fields:
        encounter_id: UUID string of the encounter
        patient_id: UUID string of the patient
        ed_arrival_time: Datetime when patient arrived in ED
        minutes_elapsed: Minutes patient has been waiting in ED
        target_unit: Requested admission unit (if known)
        boarding_alert_sent_at: Timestamp when alert was first sent (None if not yet sent)
        current_location: Current patient location code (ED code)

    Design refs:
        US-038 AC Scenario 1 — candidate detection criteria
        US-038 AC Scenario 4 — idempotency via boarding_alert_sent_at field
    """

    encounter_id: str
    patient_id: str
    ed_arrival_time: datetime
    minutes_elapsed: int
    target_unit: str | None
    boarding_alert_sent_at: datetime | None  # None → alert not yet sent
    current_location: str

    @property
    def idempotency_key(self) -> str:
        """Deterministic key scoped to encounter + boarding start time.

        Format: boarding:{encounter_id}:{boarding_start_iso}

        Design ref: US-038 AC Scenario 4.

        Returns:
            Idempotency key string for deduplication.
        """
        start_iso = self.ed_arrival_time.isoformat()
        return f"boarding:{self.encounter_id}:{start_iso}"

    @property
    def already_alerted(self) -> bool:
        """True if a boarding alert was already sent for this ED stay.

        Returns:
            True if boarding_alert_sent_at is not None, False otherwise.
        """
        return self.boarding_alert_sent_at is not None


class BoardingAlertPayload(BaseModel):
    """Pub/Sub payload published to ``notification-requests`` on boarding threshold breach.

    Contains no PHI beyond the opaque ``patient_id`` UUID and ``encounter_id`` UUID.
    All fields are non-identifiable clinical metadata.

    Design refs:
        US-038 AC Scenario 1 — required payload fields
        US-038 Technical Notes — priority=IMMEDIATE
        design.md §7.5 AIR-040 — idempotency_key prevents duplicate sends
        BR-020 — no PHI in Pub/Sub payloads

    Attributes:
        notification_type: Fixed value "ED_BOARDING_ALERT"
        priority: Fixed value "IMMEDIATE"
        patient_id: Opaque UUID — not a human-readable MRN
        encounter_id: Opaque UUID
        ed_arrival_time: ISO-8601 UTC timestamp of ED arrival
        minutes_elapsed: Minutes patient has waited in ED (≥120)
        target_unit: Requested admission unit, if known
        idempotency_key: boarding:{encounter_id}:{ed_arrival_time_iso} — prevents duplicates
    """

    notification_type: Literal["ED_BOARDING_ALERT"] = "ED_BOARDING_ALERT"
    priority: Literal["IMMEDIATE"] = "IMMEDIATE"
    patient_id: str = Field(..., description="Opaque UUID — not a human-readable MRN")
    encounter_id: str = Field(..., description="Opaque UUID")
    ed_arrival_time: str = Field(
        ..., description="ISO-8601 UTC timestamp of ED arrival"
    )
    minutes_elapsed: int = Field(
        ..., ge=120, description="Minutes patient has waited in ED"
    )
    target_unit: str | None = Field(
        None, description="Requested admission unit, if known"
    )
    idempotency_key: str = Field(
        ...,
        description="boarding:{encounter_id}:{ed_arrival_time_iso} — prevents duplicate notifications",
    )
