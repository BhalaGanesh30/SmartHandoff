"""Pydantic schemas for encounter API responses.

Used by bed management and dashboard endpoints to expose encounter data
including ML-predicted discharge times (US-036).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EncounterDetail(BaseModel):
    """Detailed encounter response including ML prediction fields.
    
    Returned by encounter detail endpoints and bed board API.
    Includes predicted discharge time from ML Inference Service (US-036).
    """

    id: UUID = Field(
        ...,
        description="Unique encounter identifier",
    )
    
    patient_id: UUID = Field(
        ...,
        description="Patient ID associated with this encounter",
    )
    
    status: str = Field(
        ...,
        description="Encounter status: REGISTERED | ADMITTED | TRANSFERRED | DISCHARGED",
    )
    
    admit_date: Optional[datetime] = Field(
        default=None,
        description="Admission datetime (UTC)",
    )
    
    discharge_date: Optional[datetime] = Field(
        default=None,
        description="Discharge datetime (UTC)",
    )
    
    admitting_diagnosis: Optional[str] = Field(
        default=None,
        description="Primary admitting diagnosis from ADT",
    )
    
    unit: Optional[str] = Field(
        default=None,
        description="Current unit assignment",
    )
    
    risk_tier: str = Field(
        ...,
        description="Readmission risk tier: HIGH | MEDIUM | LOW | UNKNOWN",
    )
    
    risk_score: Optional[float] = Field(
        default=None,
        description="Predicted readmission probability (0.0-1.0)",
    )
    
    # US-036: ML-predicted discharge time fields
    predicted_discharge_time: Optional[datetime] = Field(
        default=None,
        description="ML-predicted discharge datetime (UTC). NULL if not yet predicted (US-036).",
    )
    
    discharge_prediction_confidence: Optional[Literal["high", "medium", "low"]] = Field(
        default=None,
        description="Confidence tier from ML Inference Service: high | medium | low (US-036).",
    )
    
    discharge_prediction_interval_hours: Optional[float] = Field(
        default=None,
        description="±hours confidence interval from ML Inference Service (US-036).",
    )

    model_config = {"from_attributes": True}


class EncounterSummary(BaseModel):
    """Lightweight encounter summary for list views.
    
    Used in bed board and dashboard list endpoints where full details
    are not required.
    """

    id: UUID = Field(
        ...,
        description="Unique encounter identifier",
    )
    
    patient_id: UUID = Field(
        ...,
        description="Patient ID",
    )
    
    status: str = Field(
        ...,
        description="Encounter status",
    )
    
    unit: Optional[str] = Field(
        default=None,
        description="Current unit assignment",
    )
    
    predicted_discharge_time: Optional[datetime] = Field(
        default=None,
        description="ML-predicted discharge datetime (US-036)",
    )
    
    discharge_prediction_confidence: Optional[Literal["high", "medium", "low"]] = Field(
        default=None,
        description="Prediction confidence level (US-036)",
    )

    model_config = {"from_attributes": True}
