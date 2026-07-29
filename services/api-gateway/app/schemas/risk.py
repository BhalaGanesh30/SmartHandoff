"""Response schemas for the risk assessment endpoint.

Design refs:
    US-039 AC Scenario 4
    design.md §3.3 — FastAPI routers
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RiskTier(str, Enum):
    """Risk tier classification for readmission probability."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class ContributingFactor(BaseModel):
    """Individual SHAP feature contribution to risk score."""
    feature: str = Field(..., description="Human-readable feature label")
    shap_value: float
    feature_value: float
    direction: str = Field(..., description="'increases_risk' or 'decreases_risk'")


class EncounterRiskResponse(BaseModel):
    """Response body for GET /api/v1/encounters/{id}/risk."""

    encounter_id: str
    risk_score: float | None = Field(None, ge=0.0, le=1.0)
    risk_tier: RiskTier = RiskTier.UNKNOWN
    contributing_factors: list[ContributingFactor] = Field(default_factory=list)
    model_version: str | None = None
    assessed_at: str | None = Field(
        None,
        description="ISO 8601 timestamp of when the risk was last assessed (from AgentTask.completed_at)",
    )
