"""Shared fixtures for router unit tests.

Sets up required environment variables for FastAPI app startup in test mode.
"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(monkeypatch_session):
    """Set all required environment variables for test app startup."""
    # PHI encryption (32-byte base64url-encoded key)
    monkeypatch_session.setenv("PHI_ENCRYPTION_KEY", "lo95mKWitxnFh2zmETOaoV8hPKYex9V76CQzUngTqXI=")
    
    # OTP salt for phone number hashing
    monkeypatch_session.setenv("OTP_PHONE_SALT", "test-salt-for-unit-tests")
    
    # Database URLs
    monkeypatch_session.setenv("PRIMARY_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch_session.setenv("REPLICA_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    
    # Azure SignalR
    monkeypatch_session.setenv("AZURE_SIGNALR_CONNECTION_STRING", "Endpoint=https://test.service.signalr.net;AccessKey=test;Version=1.0;")
    
    # Redis
    monkeypatch_session.setenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Twilio
    monkeypatch_session.setenv("TWILIO_ACCOUNT_SID", "ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    monkeypatch_session.setenv("TWILIO_AUTH_TOKEN", "test_auth_token")
    monkeypatch_session.setenv("TWILIO_VERIFY_SID", "VAXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    
    # Portal token validation
    monkeypatch_session.setenv("PORTAL_JWT_SECRET", "test-portal-jwt-secret-key-for-unit-tests")
    
    yield


@pytest.fixture(scope="session")
def monkeypatch_session():
    """Session-scoped monkeypatch for environment variables."""
    from _pytest.monkeypatch import MonkeyPatch
    m = MonkeyPatch()
    yield m
    m.undo()
