"""Unit tests for POST /api/v1/auth/patient/otp."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies.redis import get_redis
from app.dependencies.twilio import get_twilio_client

VALID_TOKEN = "valid-portal-token"
PHONE = "+12345678901"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_claims():
    claims = MagicMock()
    claims.phone_number = PHONE
    claims.patient_id = "patient-uuid-001"
    claims.portal_session_id = "session-uuid-001"
    return claims


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.incr.return_value = 1
    redis.ttl.return_value = 3600
    return redis


@pytest.fixture
def mock_twilio():
    client = MagicMock()
    verification = MagicMock()
    verification.sid = "VEXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    verification.status = "pending"
    client.verify.v2.services.return_value.verifications.create.return_value = verification
    return client


@pytest.fixture(autouse=True)
def reset_overrides():
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOTPRequest:
    def test_valid_request_returns_202(self, mock_claims, mock_redis, mock_twilio):
        app.dependency_overrides[get_redis] = lambda: mock_redis
        app.dependency_overrides[get_twilio_client] = lambda: mock_twilio

        with patch("app.api.v1.routers.auth_patient_otp.validate_portal_token", return_value=mock_claims):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/patient/otp",
                    json={"portal_token": VALID_TOKEN},
                )
        assert resp.status_code == 202
        assert resp.json() == {"status": "otp_sent"}

    def test_rate_limit_exceeded_returns_429(self, mock_claims, mock_redis, mock_twilio):
        """6th request within the window must return 429 with Retry-After header."""
        mock_redis.incr.return_value = 6  # Exceeds RATE_LIMIT_MAX=5
        mock_redis.ttl.return_value = 3200
        
        app.dependency_overrides[get_redis] = lambda: mock_redis
        app.dependency_overrides[get_twilio_client] = lambda: mock_twilio

        with patch("app.api.v1.routers.auth_patient_otp.validate_portal_token", return_value=mock_claims):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/patient/otp",
                    json={"portal_token": VALID_TOKEN},
                )

        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        # Twilio must NOT be called when rate limit exceeded
        mock_twilio.verify.v2.services.return_value.verifications.create.assert_not_called()

    def test_rate_limit_ttl_set_on_first_request(self, mock_claims, mock_redis, mock_twilio):
        """TTL must be set when counter is first incremented."""
        mock_redis.incr.return_value = 1  # First request
        
        app.dependency_overrides[get_redis] = lambda: mock_redis
        app.dependency_overrides[get_twilio_client] = lambda: mock_twilio

        with patch("app.api.v1.routers.auth_patient_otp.validate_portal_token", return_value=mock_claims):
            with TestClient(app) as client:
                client.post("/api/v1/auth/patient/otp", json={"portal_token": VALID_TOKEN})

        mock_redis.expire.assert_called_once()
        call_args = mock_redis.expire.call_args
        assert call_args[0][1] == 3600  # RATE_LIMIT_TTL_SECONDS
