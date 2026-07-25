"""ADTEvent domain model — Pydantic model for ADT event payloads.

This is the domain model deserialized from Pub/Sub message bodies.
For the ORM (database) model, see backend/app/models/adt_event.py.
"""
from __future__ import annotations

from pydantic import BaseModel


class ADTEvent(BaseModel):
    """ADT event payload deserialized from Pub/Sub message.

    Represents a single HL7 ADT event (A01, A02, A03, A13, etc.) parsed
    by the HL7 Listener and published to the ``adt-events`` topic.
    """

    encounter_id: str
    event_type: str
    patient_id: str
    unit: str | None = None
    timestamp: str

    class Config:
        """Pydantic model configuration."""

        from_attributes = True
