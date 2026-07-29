"""Unit tests for GET /api/v1/encounters/{id}/risk endpoint."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Inline minimal app for test isolation
from fastapi import FastAPI
from app.routers.encounters_risk import router

app = FastAPI()
app.include_router(router, prefix="/api/v1")
client = TestClient(app)


def make_encounter(risk_score=0.72, risk_tier="HIGH", unit="ICU"):
    enc = MagicMock()
    enc.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    enc.risk_score = risk_score
    enc.risk_tier = risk_tier
    enc.unit = unit
    enc.attending_physician_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    enc.deleted_at = None
    return enc


def make_agent_task(risk_tier="HIGH", model_version="1.0.0"):
    task = MagicMock()
    task.output_summary = json.dumps({
        "risk_tier": risk_tier,
        "model_version": model_version,
        "contributing_factors": [
            {"feature": "Prior Hospital Admissions (12 Months)", "shap_value": 0.35,
             "feature_value": 2.0, "direction": "increases_risk"},
        ],
    })
    task.completed_at = None
    return task


PHYSICIAN_USER = {"sub": "22222222-2222-2222-2222-222222222222", "role": "physician", "units": ["ICU"]}
PHARMACIST_USER = {"sub": "33333333-3333-3333-3333-333333333333", "role": "pharmacist", "units": []}
ADMIN_USER = {"sub": "44444444-4444-4444-4444-444444444444", "role": "admin", "units": []}


@pytest.fixture
def mock_db_with_encounter():
    session = AsyncMock()
    enc = make_encounter()
    task = make_agent_task()

    def execute_side_effect(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = enc if "Encounter" in str(stmt) else task
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    return session


def test_get_risk_returns_200_with_all_fields_for_physician(mock_db_with_encounter):
    with (
        patch("app.routers.encounters_risk.get_current_user", return_value=PHYSICIAN_USER),
        patch("app.routers.encounters_risk.require_any_role", return_value=lambda: None),
        patch("app.routers.encounters_risk.get_read_session_factory") as mock_factory,
    ):
        # Setup mock session factory context manager
        mock_factory.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db_with_encounter)
        mock_factory.return_value.return_value.__aexit__ = AsyncMock(return_value=None)
        
        response = client.get("/api/v1/encounters/11111111-1111-1111-1111-111111111111/risk")

    assert response.status_code == 200
    data = response.json()
    assert data["risk_score"] == pytest.approx(0.72)
    assert data["risk_tier"] == "HIGH"
    assert "contributing_factors" in data
    assert "model_version" in data


def test_get_risk_400_for_invalid_uuid():
    with (
        patch("app.routers.encounters_risk.get_current_user", return_value=ADMIN_USER),
        patch("app.routers.encounters_risk.require_any_role", return_value=lambda: None),
    ):
        response = client.get("/api/v1/encounters/not-a-uuid/risk")

    assert response.status_code == 400


def test_get_risk_404_for_unknown_encounter():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    with (
        patch("app.routers.encounters_risk.get_current_user", return_value=ADMIN_USER),
        patch("app.routers.encounters_risk.require_any_role", return_value=lambda: None),
        patch("app.routers.encounters_risk.get_read_session_factory") as mock_factory,
    ):
        mock_factory.return_value.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_factory.return_value.return_value.__aexit__ = AsyncMock(return_value=None)
        
        response = client.get("/api/v1/encounters/99999999-9999-9999-9999-999999999999/risk")

    assert response.status_code == 404


def test_get_risk_unknown_tier_when_risk_score_is_none():
    session = AsyncMock()
    enc = make_encounter(risk_score=None, risk_tier="UNKNOWN")
    
    def execute_side_effect(stmt):
        result = MagicMock()
        if "Encounter" in str(stmt):
            result.scalar_one_or_none.return_value = enc
        else:
            result.scalar_one_or_none.return_value = None  # No AgentTask
        return result
    
    session.execute = AsyncMock(side_effect=execute_side_effect)

    with (
        patch("app.routers.encounters_risk.get_current_user", return_value=ADMIN_USER),
        patch("app.routers.encounters_risk.require_any_role", return_value=lambda: None),
        patch("app.routers.encounters_risk.get_read_session_factory") as mock_factory,
    ):
        mock_factory.return_value.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_factory.return_value.return_value.__aexit__ = AsyncMock(return_value=None)
        
        response = client.get("/api/v1/encounters/11111111-1111-1111-1111-111111111111/risk")

    assert response.status_code == 200
    assert response.json()["risk_tier"] == "UNKNOWN"
    assert response.json()["contributing_factors"] == []


def test_get_risk_403_for_pharmacist():
    """Pharmacists should be denied access to risk endpoint."""
    with (
        patch("app.routers.encounters_risk.get_current_user", return_value=PHARMACIST_USER),
    ):
        response = client.get("/api/v1/encounters/11111111-1111-1111-1111-111111111111/risk")

    assert response.status_code == 403
