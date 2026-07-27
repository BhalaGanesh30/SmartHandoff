"""Request and response schemas for the patient portal preferences API.

Security:
    ``urgency_override`` is intentionally excluded from this schema.
    That field is set exclusively by sending agents, never by patients.

Design refs:
    US-067 AC Scenario 4, US-067 Technical Notes.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PortalPreferencesUpdateRequest(BaseModel):
    """Request body for PATCH /api/v1/portal/preferences."""

    notification_opt_out: bool = Field(
        ...,
        description="True to opt out of non-urgent notifications; False to opt back in",
    )


class PortalPreferencesResponse(BaseModel):
    """Response body for PATCH /api/v1/portal/preferences."""

    notification_opt_out: bool = Field(
        description="Current opt-out preference as persisted",
    )
    message: str = Field(
        default="Preferences updated successfully",
        description="Human-readable confirmation",
    )
