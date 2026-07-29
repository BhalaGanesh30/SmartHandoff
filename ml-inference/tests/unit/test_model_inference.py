"""Unit tests for the inference predictor (predictor.py).

Verifies: feature vector assembly, SHAP computation, label mapping, response schema.
"""
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from app.schemas import ReadmissionFeatures, RiskTier


SAMPLE_FEATURES = ReadmissionFeatures(
    age=72.0,
    los_days=6.0,
    num_comorbidities=4.0,
    num_prior_admissions_12mo=2.0,
    medication_count=8.0,
    discharge_disposition=1.0,
    primary_diagnosis_group=0.0,
)

SAMPLE_LABELS = {
    "age": "Patient Age (Years)",
    "los_days": "Length of Stay (Days)",
    "num_comorbidities": "Number of Active Comorbidities",
    "num_prior_admissions_12mo": "Prior Hospital Admissions (12 Months)",
    "medication_count": "Active Medication Count at Discharge",
    "discharge_disposition": "Discharge Destination",
    "primary_diagnosis_group": "Primary Diagnosis Category",
}


@pytest.fixture
def mock_model():
    model = MagicMock()
    # Return probability 0.72 → HIGH tier
    model.predict_proba.return_value = np.array([[0.28, 0.72]])
    return model


@pytest.fixture
def mock_scaler():
    scaler = MagicMock()
    # Return input unchanged (identity transform for testing)
    scaler.transform.side_effect = lambda x: x
    return scaler


@pytest.fixture
def mock_shap_explainer():
    explainer = MagicMock()
    # Simulate SHAP values with 7 features; prior admissions has highest absolute value
    shap_vals = np.array([[0.05, 0.10, 0.15, 0.35, 0.08, 0.12, -0.03]])
    explainer.shap_values.return_value = shap_vals
    return explainer


def test_predict_returns_high_tier_for_probability_072(mock_model, mock_scaler, mock_shap_explainer):
    with (
        patch("app.predictor.get_model", return_value=mock_model),
        patch("app.predictor.get_scaler", return_value=mock_scaler),
        patch("app.predictor.get_model_version", return_value="1.0.0"),
        patch("app.predictor._get_shap_explainer", return_value=mock_shap_explainer),
    ):
        from app.predictor import predict
        result = predict(SAMPLE_FEATURES, SAMPLE_LABELS)

    assert result.risk_score == pytest.approx(0.72, abs=0.01)
    assert result.risk_tier == RiskTier.HIGH
    assert result.model_version == "1.0.0"


def test_predict_returns_five_contributing_factors(mock_model, mock_scaler, mock_shap_explainer):
    with (
        patch("app.predictor.get_model", return_value=mock_model),
        patch("app.predictor.get_scaler", return_value=mock_scaler),
        patch("app.predictor.get_model_version", return_value="1.0.0"),
        patch("app.predictor._get_shap_explainer", return_value=mock_shap_explainer),
    ):
        from app.predictor import predict
        result = predict(SAMPLE_FEATURES, SAMPLE_LABELS)

    assert len(result.contributing_factors) == 5


def test_predict_contributing_factors_use_human_readable_labels(mock_model, mock_scaler, mock_shap_explainer):
    with (
        patch("app.predictor.get_model", return_value=mock_model),
        patch("app.predictor.get_scaler", return_value=mock_scaler),
        patch("app.predictor.get_model_version", return_value="1.0.0"),
        patch("app.predictor._get_shap_explainer", return_value=mock_shap_explainer),
    ):
        from app.predictor import predict
        result = predict(SAMPLE_FEATURES, SAMPLE_LABELS)

    feature_labels_in_response = {cf.feature for cf in result.contributing_factors}
    # All labels must come from SAMPLE_LABELS values, not raw feature names
    assert feature_labels_in_response.issubset(set(SAMPLE_LABELS.values()))


def test_predict_direction_increases_for_positive_shap(mock_model, mock_scaler, mock_shap_explainer):
    with (
        patch("app.predictor.get_model", return_value=mock_model),
        patch("app.predictor.get_scaler", return_value=mock_scaler),
        patch("app.predictor.get_model_version", return_value="1.0.0"),
        patch("app.predictor._get_shap_explainer", return_value=mock_shap_explainer),
    ):
        from app.predictor import predict
        result = predict(SAMPLE_FEATURES, SAMPLE_LABELS)

    positive_shap_factors = [cf for cf in result.contributing_factors if cf.shap_value > 0]
    for factor in positive_shap_factors:
        assert factor.direction == "increases_risk"
