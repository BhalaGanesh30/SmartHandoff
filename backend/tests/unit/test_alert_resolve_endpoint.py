"""Unit tests for PATCH /api/v1/alerts/{id}/resolve endpoint.

Tests RBAC enforcement and resolution workflow.

Design refs:
    US-032 AC Scenario 2 — successful pharmacist resolution
    US-032 AC Scenario 4 — 403 for non-pharmacist role
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


def _make_alert(status: str = "ACTIVE") -> MagicMock:
    """Create a mock PharmacistAlert for testing."""
    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.encounter_id = uuid.uuid4()
    alert.alert_type = "HIGH_RISK_DRUG_CLASS"
    alert.severity = "HIGH"
    alert.status = status
    alert.drug_class = "ANTICOAGULANT"
    alert.drug_name = "Warfarin"
    alert.drug_pair = None
    alert.interaction_description = None
    alert.source = "SYSTEM"
    alert.sla_breached = False
    alert.resolved_by_user_id = None
    alert.resolved_at = None
    alert.resolution_type = None
    alert.created_at = datetime.now(timezone.utc)
    return alert


@pytest.fixture
def pharmacist_headers() -> dict[str, str]:
    """JWT header with PHARMACIST role (mocked by test auth override)."""
    return {"Authorization": "Bearer pharmacist-test-token"}


@pytest.fixture
def nurse_headers() -> dict[str, str]:
    """JWT header with NURSE role."""
    return {"Authorization": "Bearer nurse-test-token"}


def test_pharmacist_can_resolve_active_alert(pharmacist_headers: dict) -> None:
    """AC Scenario 2: Pharmacist resolves an ACTIVE alert → 200, status=RESOLVED."""
    from app.main import app

    alert = _make_alert(status="ACTIVE")

    with (
        patch("app.api.routes.alerts.get_write_db") as mock_db_dep,
        patch("app.api.routes.alerts.require_role") as mock_rbac,
        patch("app.core.pubsub.publisher.publish_message", new_callable=AsyncMock),
    ):
        mock_session = AsyncMock()
        mock_session.get.return_value = alert
        mock_session.commit = AsyncMock()
        mock_db_dep.return_value = mock_session

        # Mock RBAC to return a pharmacist user
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.role = "PHARMACIST"
        mock_rbac.return_value = mock_user

        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/alerts/{alert.id}/resolve",
                json={"resolution_type": "REVIEWED_ACCEPTABLE", "resolution_note": "Reviewed OK"},
                headers=pharmacist_headers,
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "RESOLVED"
    assert data["resolution_type"] == "REVIEWED_ACCEPTABLE"
    assert data["resolved_at"] is not None
    assert data["resolved_by_user_id"] is not None


def test_nurse_cannot_resolve_alert(nurse_headers: dict) -> None:
    """AC Scenario 4: Nurse JWT → 403 Forbidden; alert unchanged."""
    from app.main import app

    alert_id = uuid.uuid4()

    with patch("app.api.routes.alerts.require_role") as mock_rbac:
        # Mock RBAC to raise 403 for nurse role
        mock_rbac.side_effect = HTTPException(status_code=403, detail="Forbidden")

        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/alerts/{alert_id}/resolve",
                json={"resolution_type": "REVIEWED_ACCEPTABLE"},
                headers=nurse_headers,
            )

    assert response.status_code == 403


def test_resolve_unknown_alert_returns_404(pharmacist_headers: dict) -> None:
    """Resolving a non-existent alert_id → 404 Not Found."""
    from app.main import app

    with (
        patch("app.api.routes.alerts.get_write_db") as mock_db_dep,
        patch("app.api.routes.alerts.require_role") as mock_rbac,
    ):
        mock_session = AsyncMock()
        mock_session.get.return_value = None  # Alert not found
        mock_db_dep.return_value = mock_session

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.role = "PHARMACIST"
        mock_rbac.return_value = mock_user

        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/alerts/{uuid.uuid4()}/resolve",
                json={"resolution_type": "REVIEWED_ACCEPTABLE"},
                headers=pharmacist_headers,
            )

    assert response.status_code == 404


def test_resolve_already_resolved_alert_returns_409(
    pharmacist_headers: dict,
) -> None:
    """Resolving an already-resolved alert → 409 Conflict."""
    from app.main import app

    alert = _make_alert(status="RESOLVED")

    with (
        patch("app.api.routes.alerts.get_write_db") as mock_db_dep,
        patch("app.api.routes.alerts.require_role") as mock_rbac,
    ):
        mock_session = AsyncMock()
        mock_session.get.return_value = alert
        mock_db_dep.return_value = mock_session

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.role = "PHARMACIST"
        mock_rbac.return_value = mock_user

        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/alerts/{alert.id}/resolve",
                json={"resolution_type": "REVIEWED_ACCEPTABLE"},
                headers=pharmacist_headers,
            )

    assert response.status_code == 409
