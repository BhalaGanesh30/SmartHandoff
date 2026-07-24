"""ADTEvent stub model for coordinator-agent.

This is a minimal Pydantic model used for type checking and
deserialization in the coordinator service.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ADTEventType(StrEnum):
    """ADT event type codes."""
    ADMIT = "ADT^A01"
    TRANSFER = "ADT^A02"
    DISCHARGE = "ADT^A03"
    REGISTER = "ADT^A04"
    UPDATE = "ADT^A08"
    CANCEL_ADMIT = "ADT^A11"
    CANCEL_TRANSFER = "ADT^A12"
    CANCEL_DISCHARGE = "ADT^A13"


class ADTEvent(BaseModel):
    """ADT event domain model for Pub/Sub deserialization."""
    
    model_config = ConfigDict(from_attributes=True)
    
    encounter_id: uuid.UUID
    event_type: ADTEventType
    event_timestamp: datetime
    source_message_id: str | None = None
