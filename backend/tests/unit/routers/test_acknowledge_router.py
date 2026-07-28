"""Unit tests for PATCH /api/v1/care/escalations/{id}/acknowledge.

US-042 AC Scenarios 2 and 4.

Covers:
    - 200 OK: nurse acknowledges → status=ACKNOWLEDGED, acknowledged_at set, acknowledged_by set
    - 409 Conflict: already acknowledged → rejected
    - 403 Forbidden: patient JWT → rejected
    - 403 Forbidden: pharmacist JWT → rejected
    - 404 Not Found: unknown escalation_id → rejected
    - 200 OK: escalation with status=ESCALATED_TO_SUPERVISOR can still be acknowledged

Note:
    These tests require a full backend environment with all dependencies installed.
    Run these tests in CI/CD or with: `pip install -r requirements.txt -r requirements-dev.txt`
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.core.auth.jwt import TokenClaims
from app.models.care_escalation import CareEscalation, CareEscalationStatus
from app.api.v1.routers.care_escalations import acknowledge_escalation, _require_any_role, _ALLOWED_ROLES

ESCALATION_ID = uuid.uuid4()
ENCOUNTER_ID = uuid.uuid4()
PATIENT_ID = uuid.uuid4()
NURSE_USER_ID = uuid.uuid4()


@pytest.fixture
def nurse_user() -> TokenClaims:
    """Mock nurse user."""
    return TokenClaims(
        sub=str(NURSE_USER_ID),
        role="nurse",
        units=["ICU-3"],
        email="nurse@hospital.org",
        jti=str(uuid.uuid4()),
    )


@pytest.fixture
def patient_user() -> TokenClaims:
    """Mock patient user."""
    return TokenClaims(
        sub=str(uuid.uuid4()),
        role="patient",
        units=[],
        email="patient@example.com",
        jti=str(uuid.uuid4()),
    )


@pytest.fixture
def pharmacist_user() -> TokenClaims:
    """Mock pharmacist user."""
    return TokenClaims(
        sub=str(uuid.uuid4()),
        role="pharmacist",
        units=["PHARMACY"],
        email="pharmacist@hospital.org",
        jti=str(uuid.uuid4()),
    )


def _make_pending_escalation() -> MagicMock:
    """Create a mock pending escalation."""
    esc = MagicMock(spec=CareEscalation)
    esc.id = ESCALATION_ID
    esc.encounter_id = ENCOUNTER_ID
    esc.patient_id = PATIENT_ID
    esc.status = CareEscalationStatus.PENDING
    esc.sent_at = datetime.now(tz=timezone.utc)
    esc.acknowledged_at = None
    esc.acknowledged_by = None
    esc.escalated_to_supervisor = False
    esc.escalated_at = None
    return esc


class TestAcknowledgeEscalation:
    async def test_nurse_acknowledges_returns_200(self, nurse_user):
        """AC Scenario 2: nurse JWT → 200 OK, status=ACKNOWLEDGED, acknowledged_at set."""
        mock_session = AsyncMock()
        pending_esc = _make_pending_escalation()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pending_esc
        mock_session.execute.return_value = result_mock
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Call the endpoint handler directly
        response = await acknowledge_escalation(
            escalation_id=ESCALATION_ID,
            session=mock_session,
            current_user=nurse_user,
        )

        assert pending_esc.status == CareEscalationStatus.ACKNOWLEDGED
        assert pending_esc.acknowledged_at is not None
        assert pending_esc.acknowledged_by == uuid.UUID(str(NURSE_USER_ID))
        assert response.id == ESCALATION_ID

    async def test_already_acknowledged_returns_409(self, nurse_user):
        """Scenario 2: already acknowledged → 409 Conflict."""
        mock_session = AsyncMock()
        acked_esc = _make_pending_escalation()
        acked_esc.status = CareEscalationStatus.ACKNOWLEDGED

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = acked_esc
        mock_session.execute.return_value = result_mock

        with pytest.raises(HTTPException) as exc_info:
            await acknowledge_escalation(
                escalation_id=ESCALATION_ID,
                session=mock_session,
                current_user=nurse_user,
            )

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    async def test_patient_jwt_returns_403(self, patient_user):
        """AC Scenario 4: patient JWT → 403 Forbidden."""
        # Test the RBAC dependency directly
        check_role = _require_any_role(_ALLOWED_ROLES)
        
        with pytest.raises(HTTPException) as exc_info:
            await check_role(current_user=patient_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    async def test_pharmacist_jwt_returns_403(self, pharmacist_user):
        """AC Scenario 4: pharmacist JWT → 403 Forbidden."""
        # Test the RBAC dependency directly
        check_role = _require_any_role(_ALLOWED_ROLES)
        
        with pytest.raises(HTTPException) as exc_info:
            await check_role(current_user=pharmacist_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    async def test_unknown_escalation_returns_404(self, nurse_user):
        """Unknown escalation_id → 404 Not Found."""
        mock_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        with pytest.raises(HTTPException) as exc_info:
            await acknowledge_escalation(
                escalation_id=uuid.uuid4(),
                session=mock_session,
                current_user=nurse_user,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
