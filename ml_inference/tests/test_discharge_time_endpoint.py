"""Unit tests for POST /ml-inference/predict/discharge-time endpoint.

Coverage:
    Scenario 1: returns 200 with predicted_discharge_time and confidence_interval
    Scenario 4: confidence_level correctly mapped from confidence_interval_hours
    Auth: unauthenticated → 401; invalid JWT → 401
    503 when model not loaded

Design refs:
    US-036 TASK-006 — Unit test requirements
    TR-007 — <500ms response time requirement
    TR-020 — ≥80% branch coverage target
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

VALID_PAYLOAD = {
    "encounter_id": "550e8400-e29b-41d4-a716-446655440001",
    "admit_time": "2026-07-17T08:00:00Z",
    "patient_dob": "1960-03-15T00:00:00Z",
    "admit_diagnosis_group": "CARDIAC",
    "unit": "3A",
    "pending_procedures_count": 1,
}


def _mock_pipeline(predicted_hours: float = 6.0):
    """Return a MagicMock pipeline whose predict() returns [predicted_hours]."""
    pipeline = MagicMock()
    pipeline.predict.return_value = np.array([predicted_hours])
    return pipeline


# ──────────────────────────────────────────────
# Happy path
# ──────────────────────────────────────────────

@patch("app.routers.discharge_time.load_model", return_value=_mock_pipeline(6.0))
@patch("app.routers.discharge_time.get_model_version", return_value="v20260717")
@patch("app.auth.verify_service_account_jwt", return_value=None)
def test_predict_returns_200_with_valid_payload(mock_auth, mock_version, mock_model):
    """AC Scenario 1: Happy path returns 200 with prediction."""
    with TestClient(app) as client:
        resp = client.post(
            "/ml-inference/predict/discharge-time",
            json=VALID_PAYLOAD,
            headers={"Authorization": "Bearer mock-token"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "predicted_discharge_time" in data
    assert "confidence_interval_hours" in data
    assert data["confidence_level"] in ("high", "medium", "low")
    assert data["encounter_id"] == VALID_PAYLOAD["encounter_id"]
    assert data["model_version"] == "v20260717"


@patch("app.routers.discharge_time.load_model", return_value=_mock_pipeline(6.0))
@patch("app.routers.discharge_time.get_model_version", return_value="v1")
@patch("app.auth.verify_service_account_jwt", return_value=None)
def test_predict_response_time_under_500ms(mock_auth, mock_version, mock_model):
    """TR-007: Inference latency must be < 500 ms after model is pre-loaded."""
    with TestClient(app) as client:
        start = time.perf_counter()
        resp = client.post(
            "/ml-inference/predict/discharge-time",
            json=VALID_PAYLOAD,
            headers={"Authorization": "Bearer mock-token"},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
    assert resp.status_code == 200
    assert elapsed_ms < 500, f"Response took {elapsed_ms:.1f} ms — exceeds 500 ms threshold"


# ──────────────────────────────────────────────
# Confidence level mapping (AC Scenario 4)
# ──────────────────────────────────────────────

@pytest.mark.parametrize("hours,expected_level", [
    (2.0, "high"),    # 15% of 2 h = 0.3 h < 1 h → high
    (8.0, "medium"),  # 15% of 8 h = 1.2 h  → medium (1-2 h)
    (16.0, "low"),    # 15% of 16 h = 2.4 h → low (>2 h)
])
@patch("app.auth.verify_service_account_jwt", return_value=None)
def test_confidence_level_mapping(mock_auth, hours, expected_level):
    """AC Scenario 4: Confidence level correctly mapped from interval."""
    with patch("app.routers.discharge_time.load_model", return_value=_mock_pipeline(hours)), \
         patch("app.routers.discharge_time.get_model_version", return_value="v1"):
        with TestClient(app) as client:
            resp = client.post(
                "/ml-inference/predict/discharge-time",
                json=VALID_PAYLOAD,
                headers={"Authorization": "Bearer mock-token"},
            )
    assert resp.status_code == 200
    assert resp.json()["confidence_level"] == expected_level


@patch("app.routers.discharge_time.load_model", return_value=_mock_pipeline(6.0))
@patch("app.routers.discharge_time.get_model_version", return_value="v1")
@patch("app.auth.verify_service_account_jwt", return_value=None)
def test_confidence_level_high_when_interval_below_1h(mock_auth, mock_version, mock_model):
    """Confidence = high when interval < 1.0 hours."""
    with TestClient(app) as client:
        resp = client.post(
            "/ml-inference/predict/discharge-time",
            json=VALID_PAYLOAD,
            headers={"Authorization": "Bearer mock-token"},
        )
    data = resp.json()
    # 15% of 6h = 0.9h → high
    assert data["confidence_level"] == "high"
    assert data["confidence_interval_hours"] < 1.0


@patch("app.routers.discharge_time.load_model", return_value=_mock_pipeline(10.0))
@patch("app.routers.discharge_time.get_model_version", return_value="v1")
@patch("app.auth.verify_service_account_jwt", return_value=None)
def test_confidence_level_medium_when_interval_1_to_2h(mock_auth, mock_version, mock_model):
    """Confidence = medium when 1.0 ≤ interval ≤ 2.0 hours."""
    with TestClient(app) as client:
        resp = client.post(
            "/ml-inference/predict/discharge-time",
            json=VALID_PAYLOAD,
            headers={"Authorization": "Bearer mock-token"},
        )
    data = resp.json()
    # 15% of 10h = 1.5h → medium
    assert data["confidence_level"] == "medium"
    assert 1.0 <= data["confidence_interval_hours"] <= 2.0


@patch("app.routers.discharge_time.load_model", return_value=_mock_pipeline(20.0))
@patch("app.routers.discharge_time.get_model_version", return_value="v1")
@patch("app.auth.verify_service_account_jwt", return_value=None)
def test_confidence_level_low_when_interval_above_2h(mock_auth, mock_version, mock_model):
    """Confidence = low when interval > 2.0 hours."""
    with TestClient(app) as client:
        resp = client.post(
            "/ml-inference/predict/discharge-time",
            json=VALID_PAYLOAD,
            headers={"Authorization": "Bearer mock-token"},
        )
    data = resp.json()
    # 15% of 20h = 3.0h → low
    assert data["confidence_level"] == "low"
    assert data["confidence_interval_hours"] > 2.0


# ──────────────────────────────────────────────
# Auth rejection
# ──────────────────────────────────────────────

def test_predict_rejects_unauthenticated_request():
    """Unauthenticated request returns 401/403."""
    with TestClient(app) as client:
        resp = client.post("/ml-inference/predict/discharge-time", json=VALID_PAYLOAD)
    assert resp.status_code in (401, 403)


@patch("app.auth.verify_service_account_jwt", side_effect=Exception("Invalid JWT"))
def test_predict_rejects_invalid_jwt(mock_auth):
    """Invalid JWT returns 401."""
    with TestClient(app) as client:
        resp = client.post(
            "/ml-inference/predict/discharge-time",
            json=VALID_PAYLOAD,
            headers={"Authorization": "Bearer invalid-token"},
        )
    assert resp.status_code in (401, 403)


# ──────────────────────────────────────────────
# Model unavailable
# ──────────────────────────────────────────────

@patch("app.routers.discharge_time.load_model", side_effect=RuntimeError("GCS unavailable"))
@patch("app.auth.verify_service_account_jwt", return_value=None)
def test_predict_returns_503_when_model_unavailable(mock_auth, mock_model):
    """Model load failure returns 503."""
    with TestClient(app) as client:
        resp = client.post(
            "/ml-inference/predict/discharge-time",
            json=VALID_PAYLOAD,
            headers={"Authorization": "Bearer mock-token"},
        )
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


# ──────────────────────────────────────────────
# Input validation
# ──────────────────────────────────────────────

@patch("app.routers.discharge_time.load_model", return_value=_mock_pipeline(6.0))
@patch("app.routers.discharge_time.get_model_version", return_value="v1")
@patch("app.auth.verify_service_account_jwt", return_value=None)
def test_predict_validates_required_fields(mock_auth, mock_version, mock_model):
    """Missing required fields returns 422."""
    invalid_payload = {"encounter_id": "550e8400-e29b-41d4-a716-446655440001"}
    with TestClient(app) as client:
        resp = client.post(
            "/ml-inference/predict/discharge-time",
            json=invalid_payload,
            headers={"Authorization": "Bearer mock-token"},
        )
    assert resp.status_code == 422
