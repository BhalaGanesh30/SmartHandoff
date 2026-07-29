"""Pydantic schemas for pharmacist alert create/read operations.

Design refs:
    US-031 AC Scenario 1 — request/response shape (drug interaction alerts)
    US-032 AC Scenario 1 — create payload shape (HIGH_RISK_DRUG_CLASS alerts)
    US-032 AC Scenario 2 — resolve payload and response shape
    design.md §4.1        — Pydantic v2; FastAPI OpenAPI generation
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PharmacistAlertCreate(BaseModel):
    """Request body for ``POST /api/v1/encounters/{id}/alerts``."""

    alert_type: str = Field(default="PHARMACIST_ALERT")
    severity: str = Field(..., pattern="^(HIGH|MEDIUM|LOW)$")
    drug_pair: list[str] | None = Field(default=None, max_length=2)
    interaction_description: str | None = None
    source: str = Field(default="RXNAV", pattern="^(RXNAV|OPENFDA|SYSTEM)$")
    interaction_check_status: str = Field(
        default="COMPLETE", pattern="^(COMPLETE|INCOMPLETE)$"
    )
    metadata_: dict[str, Any] | None = Field(default=None, alias="metadata")

    model_config = {"populate_by_name": True}


class PharmacistAlertRead(PharmacistAlertCreate):
    """Response body for a created alert."""

    id: uuid.UUID
    encounter_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class HighRiskDrugClassAlertCreate(BaseModel):
    """Request body for creating a HIGH_RISK_DRUG_CLASS alert.

    Used internally by the Medication Reconciliation Agent pipeline.
    Design ref: US-032 AC Scenario 1
    """

    alert_type: Literal["HIGH_RISK_DRUG_CLASS"] = "HIGH_RISK_DRUG_CLASS"
    drug_class: str = Field(
        ...,
        pattern="^(ANTICOAGULANT|INSULIN|OPIOID|CHEMOTHERAPY)$",
        description="ISMP high-risk class identifier",
    )
    drug_name: str = Field(..., max_length=255)
    severity: Literal["HIGH"] = "HIGH"


class AlertResolveRequest(BaseModel):
    """Request body for PATCH /api/v1/alerts/{id}/resolve.

    Design ref: US-032 AC Scenario 2
    """

    resolution_type: str = Field(
        ...,
        pattern="^(REVIEWED_ACCEPTABLE|DOSE_ADJUSTED|DRUG_CHANGED|DISCONTINUED)$",
    )
    resolution_note: str | None = Field(default=None, max_length=2000)


class AlertRead(BaseModel):
    """Unified read schema for both alert types.

    Supports both PHARMACIST_ALERT (US-031) and HIGH_RISK_DRUG_CLASS (US-032) alerts.
    """

    id: uuid.UUID
    encounter_id: uuid.UUID
    alert_type: str
    severity: str
    status: str
    drug_class: str | None = None
    drug_name: str | None = None
    drug_pair: list[str] | None = None
    interaction_description: str | None = None
    source: str
    sla_breached: bool
    resolved_by_user_id: uuid.UUID | None = None
    resolved_at: datetime | None = None
    resolution_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
