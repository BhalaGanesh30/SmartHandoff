"""Prediction logic: feature scaling, LogisticRegression inference, and SHAP explanations.

Design refs:
    US-039 Technical Notes — SHAP explainer.shap_values(); map to human-readable labels
    US-039 AC Scenario 4   — contributing_factors: top 5 feature importances as human-readable labels
    design.md TR-007       — inference latency < 500ms; model pre-loaded in memory
"""
from __future__ import annotations

import logging

import numpy as np
import shap

from app.model_loader import get_model, get_model_version, get_scaler
from app.schemas import (
    ContributingFactor,
    ReadmissionFeatures,
    ReadmissionPredictionResponse,
    assign_risk_tier,
)

logger = logging.getLogger(__name__)

# SHAP explainer is initialised lazily on first request and cached
_shap_explainer: shap.LinearExplainer | None = None


def _get_shap_explainer() -> shap.LinearExplainer:
    """Return cached SHAP LinearExplainer (instantiated once)."""
    global _shap_explainer
    if _shap_explainer is None:
        # Import here to avoid circular dependency
        import sys
        import pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
        from training.feature_schema import FEATURE_NAMES
        
        model = get_model()
        # LinearExplainer for LogisticRegression
        # Use Independent masker for feature independence assumption
        _shap_explainer = shap.LinearExplainer(
            model,
            masker=shap.maskers.Independent(np.zeros((1, len(FEATURE_NAMES))))
        )
        logger.info("SHAP LinearExplainer initialized")
    return _shap_explainer


def predict(features: ReadmissionFeatures, feature_labels: dict[str, str]) -> ReadmissionPredictionResponse:
    """Run inference and compute SHAP explanations.

    Args:
        features: Validated ``ReadmissionFeatures`` input.
        feature_labels: Mapping of raw feature name → human-readable label
            from ``config/feature_labels.yaml``.

    Returns:
        ``ReadmissionPredictionResponse`` with risk_score, risk_tier,
        contributing_factors (top 5), and model_version.
    """
    # Import here to avoid circular dependency
    import sys
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    from training.feature_schema import FEATURE_NAMES
    
    model = get_model()
    scaler = get_scaler()
    model_version = get_model_version()

    # Build feature vector in the order expected by the model
    raw_values: dict[str, float] = features.model_dump()
    feature_vector = np.array([raw_values[f] for f in FEATURE_NAMES]).reshape(1, -1)

    # Scale numeric features
    scaled_vector = scaler.transform(feature_vector)

    # Predict probability
    probability = float(model.predict_proba(scaled_vector)[0, 1])
    risk_tier = assign_risk_tier(probability)

    logger.debug("Prediction complete: probability=%.4f tier=%s", probability, risk_tier)

    # SHAP values — top 5 contributing factors
    explainer = _get_shap_explainer()
    shap_values = explainer.shap_values(scaled_vector)[0]  # 1D array of length n_features

    # Sort by absolute SHAP value, descending; take top 5
    sorted_indices = np.argsort(np.abs(shap_values))[::-1][:5]

    contributing_factors: list[ContributingFactor] = []
    for idx in sorted_indices:
        feature_name = FEATURE_NAMES[idx]
        shap_val = float(shap_values[idx])
        contributing_factors.append(
            ContributingFactor(
                feature=feature_labels.get(feature_name, feature_name),
                shap_value=round(shap_val, 4),
                feature_value=float(feature_vector[0, idx]),
                direction="increases_risk" if shap_val > 0 else "decreases_risk",
            )
        )

    return ReadmissionPredictionResponse(
        risk_score=round(probability, 4),
        risk_tier=risk_tier,
        contributing_factors=contributing_factors,
        model_version=model_version,
    )
