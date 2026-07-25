"""Unit tests for POST /api/v1/auth/patient/verify."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies.redis import get_redis
from app.dependencies.twilio import get_twilio_client

VALID_TOKEN = "valid-portal-token"
PHONE = "+12345678901"
VERIFICATION_SID = "VEXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set OTP_PHONE_SALT for otp_helpers to use get_settings()."""
    from app.core.config import get_settings
    monkeypatch.setenv("OTP_PHONE_SALT", "test-salt-for-unit-tests")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_claims():
    claims = MagicMock()
    claims.phone_number = PHONE
    claims.patient_id = "patient-uuid-001"
    claims.portal_session_id = "session-uuid-001"
    return claims


@pytest.fixture
def mock_redis_with_sid():
    """Redis has an active OTP session (SID present, no failures yet)."""
    redis = AsyncMock()
    redis.get.side_effect = lambda key: (
        VERIFICATION_SID.encode() if "otp:" in key and "failures" not in key and "rate" not in key
        else None
    )
    redis.incr.return_value = 1
    redis.expire = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def mock_twilio_approved():
    client = MagicMock()
    check = MagicMock()
    check.status = "approved"
    client.verify.v2.services.return_value.verification_checks.create.return_value = check
    return client


@pytest.fixture
def mock_twilio_rejected():
    client = MagicMock()
    check = MagicMock()
    check.status = "pending"  # Twilio returns "pending" for wrong code
    client.verify.v2.services.return_value.verification_checks.create.return_value = check
    return client


@pytest.fixture(autouse=True)
def reset_overrides():
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


class TestOTPVerify:
    def test_successful_verification_returns_jwt(
        self, mock_claims, mock_redis_with_sid, mock_twilio_approved
    ):
        app.dependency_overrides[get_redis] = lambda: mock_redis_with_sid
        app.dependency_overrides[get_twilio_client] = lambda: mock_twilio_approved

        with patch("app.api.v1.routers.auth_patient_verify.validate_portal_token", return_value=mock_claims):
            with patch("app.api.v1.routers.auth_patient_verify.create_access_token", return_value="jwt-token"):
                with TestClient(app) as client:
                    resp = client.post(
                        "/api/v1/auth/patient/verify",
                        json={"portal_token": VALID_TOKEN, "otp_code": "000000"},
                    )

        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == "jwt-token"
        assert body["token_type"] == "bearer"
        # Redis cleanup: otp: and otp_failures: keys deleted
        mock_redis_with_sid.delete.assert_called_once()

    def test_otp_expired_when_redis_key_absent(
        self, mock_claims, mock_twilio_approved
    ):
        """Missing Redis key (TTL elapsed) must return 401 otp_expired."""
        redis = AsyncMock()
        redis.get.return_value = None  # Key expired
        
        app.dependency_overrides[get_redis] = lambda: redis
        app.dependency_overrides[get_twilio_client] = lambda: mock_twilio_approved

        with patch("app.api.v1.routers.auth_patient_verify.validate_portal_token", return_value=mock_claims):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/patient/verify",
                    json={"portal_token": VALID_TOKEN, "otp_code": "000000"},
                )

        assert resp.status_code == 401
        assert resp.json()["detail"]["error"] == "otp_expired"

    def test_wrong_otp_increments_failures_and_returns_attempts_remaining(
        self, mock_claims, mock_redis_with_sid, mock_twilio_rejected
    ):
        mock_redis_with_sid.get.side_effect = [
            VERIFICATION_SID.encode(),  # otp: key present
            b"0",                        # failures: 0
        ]
        mock_redis_with_sid.incr.return_value = 1  # After increment: 1 failure
        
        app.dependency_overrides[get_redis] = lambda: mock_redis_with_sid
        app.dependency_overrides[get_twilio_client] = lambda: mock_twilio_rejected

        with patch("app.api.v1.routers.auth_patient_verify.validate_portal_token", return_value=mock_claims):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/patient/verify",
                    json={"portal_token": VALID_TOKEN, "otp_code": "999999"},
                )

        assert resp.status_code == 401
        body = resp.json()["detail"]
        assert body["error"] == "invalid_otp"
        assert body["attempts_remaining"] == 2  # MAX_FAILED_ATTEMPTS(3) - 1

    def test_third_failure_invalidates_otp(
        self, mock_claims, mock_redis_with_sid, mock_twilio_rejected
    ):
        """After 3 failures the OTP keys must be deleted and 0 attempts remain."""
        mock_redis_with_sid.get.side_effect = [
            VERIFICATION_SID.encode(),  # otp: key
            b"2",                        # failures already at 2
        ]
        mock_redis_with_sid.incr.return_value = 3  # 3rd failure
        
        app.dependency_overrides[get_redis] = lambda: mock_redis_with_sid
        app.dependency_overrides[get_twilio_client] = lambda: mock_twilio_rejected

        with patch("app.api.v1.routers.auth_patient_verify.validate_portal_token", return_value=mock_claims):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/patient/verify",
                    json={"portal_token": VALID_TOKEN, "otp_code": "999999"},
                )

        assert resp.status_code == 401
        body = resp.json()["detail"]
        assert body["error"] == "invalid_otp"
        assert body["attempts_remaining"] == 0
        # Both keys must be deleted
        mock_redis_with_sid.delete.assert_called_once()
