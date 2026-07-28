"""FastAPI router for discharge time prediction endpoint.

Endpoint: POST /ml-inference/predict/discharge-time

Design refs:
    US-036 AC Scenario 1 — returns predicted_discharge_time + confidence_interval within 500 ms
    US-036 Technical Notes — confidence thresholds; los_so_far_hours = (now - admit_time) / 3600
    design.md §5.1 (TR-007) — <500 ms inference latency
    SEC-001 — service account JWT required; validated by FastAPI dependency
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import verify_service_account_jwt
from app.model_loader import get_model_version, load_model
from app.schemas import (
    ConfidenceLevel,
    DischargeTimePredictionRequest,
    DischargeTimePredictionResponse,
)

router = APIRouter(prefix="/ml-inference", tags=["ML Inference"])
logger = logging.getLogger(__name__)

_CONFIDENCE_HIGH_THRESHOLD_H = 1.0
_CONFIDENCE_MEDIUM_THRESHOLD_H = 2.0


def _derive_confidence_level(confidence_interval_hours: float) -> ConfidenceLevel:
    """Map ±hours confidence interval to a colour-coded tier.

    Thresholds per US-036 Technical Notes:
        high   if std_dev < 1 h  → confidence_interval < 1 h
        medium if std_dev 1-2 h  → confidence_interval 1-2 h
        low    if std_dev > 2 h  → confidence_interval > 2 h
    """
    if confidence_interval_hours < _CONFIDENCE_HIGH_THRESHOLD_H:
        return ConfidenceLevel.HIGH
    if confidence_interval_hours < _CONFIDENCE_MEDIUM_THRESHOLD_H:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


@router.post(
    "/predict/discharge-time",
    response_model=DischargeTimePredictionResponse,
    summary="Predict patient discharge time",
    description=(
        "Accepts encounter feature vector and returns the predicted discharge datetime "
        "and ±hour confidence interval. Authenticated via service account JWT."
    ),
    status_code=status.HTTP_200_OK,
)
async def predict_discharge_time(
    request: DischargeTimePredictionRequest,
    _: None = Depends(verify_service_account_jwt),
) -> DischargeTimePredictionResponse:
    """Run inference and return discharge time prediction.

    Args:
        request: Encounter feature vector.

    Returns:
        ``DischargeTimePredictionResponse`` with ISO datetime and confidence tier.

    Raises:
        HTTPException 503: If model is not loaded (startup failure).
        HTTPException 422: FastAPI auto-raises for invalid request body.
    """
    try:
        pipeline = load_model()
    except RuntimeError as exc:
        logger.error("Model unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML model is currently unavailable. Retry after a few seconds.",
        ) from exc

    # Build feature vector — matches train.py feature engineering exactly
    now = datetime.now(timezone.utc)
    admit_time = request.admit_time.replace(tzinfo=timezone.utc) if request.admit_time.tzinfo is None else request.admit_time
    dob = request.patient_dob.replace(tzinfo=timezone.utc) if request.patient_dob.tzinfo is None else request.patient_dob

    los_so_far_hours = max((now - admit_time).total_seconds() / 3600.0, 0.0)
    patient_age = math.floor((admit_time - dob).days / 365.25)

    feature_df = pd.DataFrame([{
        "patient_age": float(patient_age),
        "los_so_far_hours": los_so_far_hours,
        "pending_procedures": float(request.pending_procedures_count),
        "day_of_week": float(admit_time.weekday()),
        "admit_diagnosis_group": request.admit_diagnosis_group,
        "unit": request.unit,
    }])

    # Predict: model returns hours_to_discharge from admit_time
    predicted_hours_from_admit: float = float(pipeline.predict(feature_df)[0])
    predicted_hours_from_admit = max(predicted_hours_from_admit, 0.0)

    predicted_discharge_time = admit_time + timedelta(hours=predicted_hours_from_admit)

    # Derive confidence interval from remaining hours (heuristic: 15% of prediction)
    confidence_interval_hours = round(predicted_hours_from_admit * 0.15, 2)
    confidence_level = _derive_confidence_level(confidence_interval_hours)

    model_version = get_model_version()

    logger.info(
        "Prediction: encounter_id=%s predicted_discharge=%s confidence=%s",
        request.encounter_id,
        predicted_discharge_time.isoformat(),
        confidence_level.value,
    )

    return DischargeTimePredictionResponse(
        encounter_id=request.encounter_id,
        predicted_discharge_time=predicted_discharge_time,
        confidence_interval_hours=confidence_interval_hours,
        confidence_level=confidence_level,
        model_version=model_version,
    )
