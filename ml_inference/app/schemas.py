"""Pydantic request/response schemas for the ML Inference Service.

Design refs:
    US-036 AC Scenario 1 — predicted_discharge_time (ISO datetime) + confidence_interval
    US-036 Technical Notes — confidence thresholds (high <1 h, medium 1-2 h, low >2 h)
    ADR-004 — Pydantic structured output for all AI/ML services
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    """Confidence tier for discharge time prediction."""
    HIGH = "high"      # std_dev < 1 hour
    MEDIUM = "medium"  # std_dev 1–2 hours
    LOW = "low"        # std_dev > 2 hours
    UNKNOWN = "unknown"


class DischargeTimePredictionRequest(BaseModel):
    """Feature vector for discharge time inference.

    All features match the training pipeline (train.py). The caller
    (BedManagementAgent) constructs this from the encounter record at inference time.
    """

    encounter_id: str = Field(..., description="Encounter UUID — used for audit and response correlation")
    admit_time: datetime = Field(..., description="UTC-aware admit datetime of the encounter")
    patient_dob: datetime = Field(..., description="Patient date of birth (UTC-aware or date-only)")
    admit_diagnosis_group: str = Field(
        ...,
        description="Broad diagnostic category, e.g. 'CARDIAC', 'ORTHO', 'PULMONARY'",
    )
    unit: str = Field(..., description="Inpatient unit code, e.g. 'ICU', '3A', 'ED'")
    pending_procedures_count: int = Field(
        default=0,
        ge=0,
        description="Number of pending clinical procedures for this encounter",
    )


class DischargeTimePredictionResponse(BaseModel):
    """Discharge time prediction result.

    ``confidence_interval_hours`` drives the ``confidence_level`` shown in the bed board UI.
    """

    encounter_id: str
    predicted_discharge_time: datetime = Field(
        ...,
        description="Predicted UTC datetime of patient discharge",
    )
    confidence_interval_hours: float = Field(
        ...,
        description="±hours radius of the 80th-percentile prediction interval",
    )
    confidence_level: ConfidenceLevel = Field(
        ...,
        description="Colour-coded confidence tier derived from confidence_interval_hours",
    )
    model_version: str = Field(..., description="Version tag of the model used for this prediction")
