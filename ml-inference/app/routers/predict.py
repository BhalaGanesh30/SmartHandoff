"""FastAPI router for readmission risk prediction.

Endpoint:
    POST /ml-inference/predict/readmission

Design refs:
    US-039 DoD — ML Inference endpoint POST /ml-inference/predict/readmission
    design.md §3.1 — ML Inference Service serves Scikit-learn models via FastAPI
    SEC: endpoint is internal-only (no public ingress); Cloud Run VPC connector; no JWT required
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.predictor import predict
from app.schemas import ReadmissionFeatures, ReadmissionPredictionResponse

router = APIRouter(prefix="/ml-inference", tags=["inference"])
logger = logging.getLogger(__name__)


def _get_feature_labels(request: Request) -> dict[str, str]:
    """Retrieve feature label mapping loaded at startup from app state."""
    return request.app.state.feature_labels


@router.post(
    "/predict/readmission",
    response_model=ReadmissionPredictionResponse,
    summary="Predict 30-day readmission risk",
    description=(
        "Accepts a 7-feature vector, runs LogisticRegression inference, computes SHAP explanations, "
        "and returns risk_score (0.0–1.0), risk_tier (LOW/MEDIUM/HIGH), top-5 contributing_factors, "
        "and model_version. Internal endpoint — no external JWT required; secured by VPC."
    ),
)
async def predict_readmission(
    features: ReadmissionFeatures,
    feature_labels: dict[str, str] = Depends(_get_feature_labels),
) -> ReadmissionPredictionResponse:
    """Run readmission risk prediction for a discharged encounter."""
    try:
        return predict(features, feature_labels)
    except Exception as exc:
        logger.exception("Prediction failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Readmission risk prediction failed. Check ml-inference service logs.",
        ) from exc
