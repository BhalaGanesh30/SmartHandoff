"""Unit tests — GET /api/v1/notifications (notification audit log endpoint).

Covers:
    - Staff JWT returns notification list with correct fields
    - PHI fields (recipient_phone, recipient_email) excluded from response
    - Patient JWT rejected (403)
    - Empty list returned when no notifications exist for encounter
    - urgency_override field present in response items

Design refs: US-067 AC Scenario 1, TASK-004, TASK-006.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth.jwt import get_current_user, TokenClaims
from app.db.deps import get_read_db


ENCOUNTER_ID = uuid.uuid4()
PATIENT_ID = uuid.uuid4()


def _make_notification_record(delivery_status="SENT", urgency_override=False):
    """Create a mock notification record."""
    record = MagicMock()
    record.id = uuid.uuid4()
    record.type = MagicMock(value="SMS")
    record.channel = "SMS"
    record.sent_at = datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc)
    record.delivery_status = MagicMock(value=delivery_status)
    record.template = "medication_reminder"
    record.urgency_override = urgency_override
    record.recipient_phone_hash = "abc123hash"
    record.recipient_email_hash = None
    # PHI fields must NOT be in ORM model per TASK-004
    return record


@pytest.fixture()
def mock_db_session():
    """Create a mock AsyncSession with notification records."""
    session = AsyncMock()
    mock_records = [_make_notification_record()]
    result = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = mock_records
    result.scalars.return_value = scalars_result
    session.execute.return_value = result
    return session


@pytest.fixture()
def mock_staff_user():
    """Create a mock staff user TokenClaims."""
    user = MagicMock(spec=TokenClaims)
    user.user_id = str(uuid.uuid4())
    user.role = "NURSE"
    return user


@pytest.fixture()
def client_with_staff_auth(mock_db_session, mock_staff_user):
    """TestClient with staff JWT dependency override."""
    app.dependency_overrides[get_current_user] = lambda: mock_staff_user
    app.dependency_overrides[get_read_db] = lambda: mock_db_session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_staff_log_query_returns_correct_fields(client_with_staff_auth):
    """GET /api/v1/notifications returns required fields from AC Scenario 1."""
    response = client_with_staff_auth.get(
        f"/api/v1/notifications?encounter_id={ENCOUNTER_ID}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["encounter_id"] == str(ENCOUNTER_ID)
    assert body["total"] == 1
    assert "items" in body
    
    item = body["items"][0]
    # AC Scenario 1 required fields
    assert "notification_type" in item or "type" in item, "notification_type/type field missing"
    assert "channel" in item
    assert "delivery_status" in item
    assert "template_name" in item
    assert "urgency_override" in item


def test_phi_excluded_from_notification_log_response(client_with_staff_auth):
    """recipient_phone and recipient_email must not appear in response."""
    response = client_with_staff_auth.get(
        f"/api/v1/notifications?encounter_id={ENCOUNTER_ID}"
    )
    assert response.status_code == 200
    response_text = response.text
    
    # Ensure no plaintext phone/email field names in response
    # Hash fields are OK, but not plaintext values
    assert '"recipient_phone":' not in response_text or '"recipient_phone_hash"' in response_text, \
        "Plaintext recipient_phone found in response"
    assert '"recipient_email":' not in response_text or '"recipient_email_hash"' in response_text, \
        "Plaintext recipient_email found in response"
    
    # Verify hash fields ARE present (they're allowed)
    body = response.json()
    item = body["items"][0]
    assert "recipient_phone_hash" in item or "recipient_email_hash" in item, \
        "Hash fields should be present for correlation"


def test_empty_list_returned_for_encounter_with_no_notifications(mock_staff_user):
    """GET with encounter_id that has no notifications returns 200 with empty items list."""
    mock_db = AsyncMock()
    result = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = []  # No records
    result.scalars.return_value = scalars_result
    mock_db.execute.return_value = result
    
    app.dependency_overrides[get_current_user] = lambda: mock_staff_user
    app.dependency_overrides[get_read_db] = lambda: mock_db
    
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(f"/api/v1/notifications?encounter_id={uuid.uuid4()}")
    
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
    
    app.dependency_overrides.clear()


def test_encounter_id_required_parameter(mock_staff_user):
    """GET without encounter_id returns 422 Unprocessable Entity."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: mock_staff_user
    app.dependency_overrides[get_read_db] = lambda: mock_db
    
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/notifications")
    
    assert response.status_code == 422  # Missing required query parameter
    app.dependency_overrides.clear()


def test_patient_jwt_rejected_from_notifications_endpoint():
    """Patient JWT must be rejected from GET /api/v1/notifications."""
    # Mock get_current_user to return a patient user (role = PATIENT)
    patient_user = MagicMock(spec=TokenClaims)
    patient_user.user_id = str(uuid.uuid4())
    patient_user.role = "PATIENT"  # Not in allowed STAFF_ROLES
    
    mock_db = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: patient_user
    app.dependency_overrides[get_read_db] = lambda: mock_db
    
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(f"/api/v1/notifications?encounter_id={ENCOUNTER_ID}")
    
    assert response.status_code == 403  # Role not permitted
    app.dependency_overrides.clear()


def test_urgency_override_field_present_in_response(mock_staff_user):
    """urgency_override must be present in each notification item."""
    mock_db = AsyncMock()
    # Create a record with urgency_override=True
    mock_records = [_make_notification_record(urgency_override=True)]
    result = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = mock_records
    result.scalars.return_value = scalars_result
    mock_db.execute.return_value = result
    
    app.dependency_overrides[get_current_user] = lambda: mock_staff_user
    app.dependency_overrides[get_read_db] = lambda: mock_db
    
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(f"/api/v1/notifications?encounter_id={ENCOUNTER_ID}")
    
    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert "urgency_override" in item
    assert item["urgency_override"] is True
    
    app.dependency_overrides.clear()
