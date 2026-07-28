"""Request/response Pydantic schemas for the ML Inference Service.

Design refs:
    US-039 AC Scenario 1, 2, 4
    US-039 Technical Notes — 7 features; risk tier thresholds
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class RiskTier(str, Enum):
    """Risk tier classification for readmission probability."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReadmissionFeatures(BaseModel):
    """Input feature vector for 30-day readmission risk prediction.

    Feature order must match training.feature_schema.FEATURE_NAMES.
    All values must be present — no imputation in the inference service.
    """

    age: Annotated[float, Field(ge=0, le=120, description="Patient age in years at admission")]
    los_days: Annotated[float, Field(ge=0, description="Length of stay in days")]
    num_comorbidities: Annotated[float, Field(ge=0, description="Active Condition resource count")]
    num_prior_admissions_12mo: Annotated[float, Field(ge=0, description="Prior admissions in last 12 months")]
    medication_count: Annotated[float, Field(ge=0, description="Active medication count at discharge")]
    discharge_disposition: Annotated[
        float,
        Field(ge=0, le=4, description="0=home,1=SNF,2=rehab,3=home_health,4=AMA"),
    ]
    primary_diagnosis_group: Annotated[
        float,
        Field(ge=0, le=19, description="Ordinal-encoded diagnosis group (0–19)"),
    ]


class ContributingFactor(BaseModel):
    """Single SHAP-derived contributing factor with human-readable label."""

    feature: str = Field(..., description="Human-readable feature label from config/feature_labels.yaml")
    shap_value: float = Field(..., description="SHAP value for this feature (positive = increases risk)")
    feature_value: float = Field(..., description="Raw feature value from the input payload")
    direction: str = Field(..., description="'increases_risk' or 'decreases_risk'")


class ReadmissionPredictionResponse(BaseModel):
    """Response from POST /ml-inference/predict/readmission."""

    risk_score: float = Field(..., ge=0.0, le=1.0, description="Predicted 30-day readmission probability")
    risk_tier: RiskTier
    contributing_factors: list[ContributingFactor] = Field(
        ..., max_length=5, description="Top 5 contributing features by absolute SHAP value"
    )
    model_version: str = Field(..., description="Semantic version of the loaded model artifact")


# Risk tier thresholds per US-039 DoD
def assign_risk_tier(probability: float) -> RiskTier:
    """Assign risk tier based on predicted probability.

    Thresholds per US-039:
        LOW    : probability < 0.30
        MEDIUM : 0.30 ≤ probability < 0.70
        HIGH   : probability ≥ 0.70
    """
    if probability >= 0.70:
        return RiskTier.HIGH
    if probability >= 0.30:
        return RiskTier.MEDIUM
    return RiskTier.LOW
