"""Pydantic schemas for the KPI analytics API.

IMPORTANT — PHI guardrail:
    These schemas intentionally contain ONLY aggregated metrics.
    No encounter IDs, patient names, MRNs, DOBs, or any individually
    identifiable information may be added here.
    See US-061 AC Scenario 3 and design.md §8.3.

Design refs:
    US-061 AC Scenario 3 — de-identified aggregated response
    design.md §3.3 — FastAPI backend structure
"""
from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class KpiDataPoint(BaseModel):
    """A single aggregated KPI data point for one date/unit combination.

    All fields are aggregated metrics only — no PHI is present.
    """

    date: datetime.date
    unit: str
    avg_discharge_doc_time_min: float | None = Field(
        None,
        description="Average time (minutes) from encounter creation to discharge documentation completion",
        ge=0,
    )
    readmission_rate_30d: float | None = Field(
        None,
        description="30-day readmission rate as a proportion (0.0–1.0)",
        ge=0.0,
        le=1.0,
    )
    med_recon_completion_rate: float | None = Field(
        None,
        description="Medication reconciliation completion rate as a proportion (0.0–1.0)",
        ge=0.0,
        le=1.0,
    )
    bed_utilisation_pct: float | None = Field(
        None,
        description="Bed utilisation percentage (0.0–100.0)",
        ge=0.0,
        le=100.0,
    )
    agent_task_success_rate: float | None = Field(
        None,
        description="AI agent task success rate as a proportion (0.0–1.0)",
        ge=0.0,
        le=1.0,
    )
    discharge_volume: int | None = Field(
        None,
        description="Number of discharged encounters on this date/unit",
        ge=0,
    )

    model_config = {"from_attributes": True}


class KpiResponse(BaseModel):
    """Top-level response envelope for GET /api/v1/analytics/kpis.

    Contains only aggregated, de-identified metrics.
    from_date and to_date echo the filter applied so clients can
    verify the effective range.
    """

    from_date: datetime.date
    to_date: datetime.date
    unit: str | None = Field(None, description="Unit filter applied; null means all accessible units")
    data: list[KpiDataPoint] = Field(default_factory=list)
    total_rows: int = Field(0, description="Total data points returned")


class RiskDistributionBucket(BaseModel):
    """A single bucket in the readmission risk distribution."""

    tier: str = Field(..., description="Risk tier: LOW | MEDIUM | HIGH")
    count: int = Field(..., ge=0, description="Number of encounters in this tier")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of total encounters")


class RiskDistributionResponse(BaseModel):
    """Top-level response for GET /api/v1/analytics/risk-distribution."""

    from_date: datetime.date
    to_date: datetime.date
    unit: str | None = Field(None, description="Unit filter applied; null means all accessible units")
    buckets: list[RiskDistributionBucket] = Field(default_factory=list)
    total: int = Field(0, description="Total encounters represented")


class HighRiskEncounter(BaseModel):
    """De-identified high-risk encounter row for the analytics dashboard.

    Contains no PHI — patient identifier is masked to the last 4 digits of the MRN.
    """

    masked_id: str = Field(..., description="Masked patient identifier, e.g. ●●● #2041")
    unit: str | None = Field(None, description="Encounter unit")
    risk_score: float | None = Field(None, ge=0.0, le=1.0, description="Predicted 30-day readmission probability")
    risk_tier: str = Field(..., description="Risk tier: HIGH | MEDIUM | LOW")
    discharge_date: datetime.date | None = Field(None, description="Discharge date")
    follow_up_status: str = Field(..., description="Follow-up appointment status label")


class HighRiskEncountersResponse(BaseModel):
    """Top-level response for GET /api/v1/analytics/high-risk-encounters."""

    from_date: datetime.date
    to_date: datetime.date
    unit: str | None = Field(None, description="Unit filter applied; null means all accessible units")
    encounters: list[HighRiskEncounter] = Field(default_factory=list)
    total: int = Field(0, description="Total high-risk encounters returned")


class ExportJobStatus(BaseModel):
    """Status response for async PDF export jobs."""

    job_id: str = Field(..., description="Unique export job identifier")
    status: str = Field(..., description="Job status: processing | complete | error")
    download_url: str | None = Field(None, description="URL to download the generated file")
    poll_url: str | None = Field(None, description="URL to poll for status updates")
