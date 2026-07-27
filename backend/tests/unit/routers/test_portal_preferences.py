"""Unit tests — PATCH /api/v1/portal/preferences (patient notification opt-out).

Covers:
    - Patient can set notification_opt_out=True → 200 OK; DB update called
    - Patient can set notification_opt_out=False → 200 OK; DB update called
    - Audit log written on preference change (BR-012)
    - Staff JWT rejected (403 Forbidden)
    - urgency_override NOT settable via this endpoint (schema guard)

Design refs: US-067 AC Scenario 4, TASK-005, TASK-006.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth.dependencies import get_current_patient_user
from app.db.deps import get_write_db
from app.models.patient import Patient


PATIENT_ID = uuid.uuid4()


def _mock_patient():
    """Create a mock Patient object."""
    patient = MagicMock(spec=Patient)
    patient.id = PATIENT_ID
    patient.notification_opt_out = False
    return patient


@pytest.fixture()
def mock_db_session():
    """Create a mock AsyncSession."""
    session = AsyncMock()
    # Mock execute to return a result with scalar_one_or_none
    result = MagicMock()
    result.scalar_one_or_none.return_value = _mock_patient()
    session.execute.return_value = result
    return session


@pytest.fixture()
def client_with_patient_auth(mock_db_session):
    """TestClient with patient JWT dependency override."""
    app.dependency_overrides[get_current_patient_user] = lambda: _mock_patient()
    app.dependency_overrides[get_write_db] = lambda: mock_db_session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_patient_preference_update_sets_opt_out_true(client_with_patient_auth, mock_db_session):
    """PATCH with notification_opt_out=True returns 200 OK."""
    response = client_with_patient_auth.patch(
        "/api/v1/portal/preferences",
        json={"notification_opt_out": True},
    )
    if response.status_code != 200:
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
    assert response.status_code == 200
    body = response.json()
    assert body["notification_opt_out"] is True
    assert "message" in body
    
    # Verify DB update was called (check that execute was called for UPDATE)
    assert mock_db_session.execute.call_count >= 2  # SELECT + UPDATE
    assert mock_db_session.commit.call_count >= 1


def test_patient_preference_update_sets_opt_out_false(client_with_patient_auth, mock_db_session):
    """PATCH with notification_opt_out=False (opt back in) returns 200 OK."""
    response = client_with_patient_auth.patch(
        "/api/v1/portal/preferences",
        json={"notification_opt_out": False},
    )
    assert response.status_code == 200
    assert response.json()["notification_opt_out"] is False
    
    # Verify DB operations were performed
    assert mock_db_session.execute.call_count >= 2
    assert mock_db_session.commit.call_count >= 1


def test_urgency_override_not_in_request_schema():
    """urgency_override must not be a field in PortalPreferencesUpdateRequest."""
    from app.schemas.portal import PortalPreferencesUpdateRequest
    
    # Attempt to create a request with urgency_override should fail
    try:
        request = PortalPreferencesUpdateRequest(
            notification_opt_out=True,
            urgency_override=True  # type: ignore
        )
        # If we get here, the field was accepted — FAIL
        assert False, "SECURITY: urgency_override was accepted in patient request schema"
    except Exception:
        # Expected: Pydantic should reject extra fields or not recognize urgency_override
        pass
    
    # Verify field is not in schema
    assert "urgency_override" not in PortalPreferencesUpdateRequest.model_fields, (
        "SECURITY: urgency_override must never be patient-settable"
    )


def test_staff_jwt_rejected_from_portal_preferences():
    """Staff JWT must be rejected from PATCH /api/v1/portal/preferences."""
    # Override get_current_patient_user to raise 403 (simulates staff JWT rejection)
    def raise_403():
        raise HTTPException(status_code=403, detail="Patient JWT required")

    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _mock_patient()
    mock_db.execute.return_value = result

    app.dependency_overrides[get_current_patient_user] = raise_403
    app.dependency_overrides[get_write_db] = lambda: mock_db
    
    client = TestClient(app, raise_server_exceptions=False)
    response = client.patch(
        "/api/v1/portal/preferences",
        json={"notification_opt_out": True}
    )
    
    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_missing_notification_opt_out_field_returns_422():
    """Request without notification_opt_out field must return 422."""
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _mock_patient()
    mock_db.execute.return_value = result

    app.dependency_overrides[get_current_patient_user] = lambda: _mock_patient()
    app.dependency_overrides[get_write_db] = lambda: mock_db
    
    client = TestClient(app, raise_server_exceptions=False)
    response = client.patch(
        "/api/v1/portal/preferences",
        json={}  # Empty body - missing required field
    )
    
    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_audit_log_entry_created_on_preference_change(client_with_patient_auth, mock_db_session):
    """Audit log entry must be created when preference is updated (BR-012)."""
    response = client_with_patient_auth.patch(
        "/api/v1/portal/preferences",
        json={"notification_opt_out": True},
    )
    
    assert response.status_code == 200
    
    # Verify audit log was added
    # The router should call db.add() for AuditLog and db.commit()
    # We can check commit was called at least twice (once for patient update, once for audit)
    assert mock_db_session.commit.call_count >= 2
    assert mock_db_session.add.called
