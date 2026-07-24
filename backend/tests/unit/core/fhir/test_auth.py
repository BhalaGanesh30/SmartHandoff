"""Unit tests for FHIRAuthClient OAuth 2.0 authentication.

Tests:
- Successful authentication (AC Scenario 1)
- Cache hit without network call (AC Scenario 2)
- Cache miss triggers refresh (AC Scenario 3)
- 401 raises FHIRAuthenticationError (AC Scenario 4)
- Network errors
- Invalid token response
"""
from __future__ import annotations

import pytest
import respx
from freezegun import freeze_time
from httpx import Response

from app.core.fhir.auth import FHIRAuthClient
from app.core.fhir.exceptions import FHIRAuthenticationError

# Mock SMART configuration
MOCK_SMART_CONFIG = {
    "token_endpoint": "https://ehr.example.com/auth/token",
}

# Mock token response
MOCK_TOKEN_RESPONSE = {
    "access_token": "mock_access_token_xyz",
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": "system/*.read",
}


@pytest.fixture
def mock_env(monkeypatch):
    """Set environment variables for FHIR auth."""
    monkeypatch.setenv("FHIR_BASE_URL", "https://ehr.example.com/fhir")
    monkeypatch.setenv("FHIR_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("FHIR_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("FHIR_SCOPE", "system/*.read")


@pytest.mark.asyncio
async def test_authenticate_success(mock_env):
    """Test successful OAuth 2.0 client_credentials authentication (AC Scenario 1)."""
    discovery_url = "https://ehr.example.com/fhir/.well-known/smart-configuration"
    token_url = "https://ehr.example.com/auth/token"

    with respx.mock:
        # Mock SMART discovery
        respx.get(discovery_url).mock(return_value=Response(200, json=MOCK_SMART_CONFIG))

        # Mock token endpoint
        respx.post(token_url).mock(return_value=Response(200, json=MOCK_TOKEN_RESPONSE))

        client = FHIRAuthClient()
        try:
            token_response = await client.authenticate()

            assert token_response["access_token"] == "mock_access_token_xyz"
            assert token_response["expires_in"] == 3600
            assert token_response["token_type"] == "Bearer"
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_get_access_token_cache_hit(mock_env):
    """Test get_access_token returns cached token without network call (AC Scenario 2)."""
    discovery_url = "https://ehr.example.com/fhir/.well-known/smart-configuration"
    token_url = "https://ehr.example.com/auth/token"

    with respx.mock:
        # Mock SMART discovery (called once)
        respx.get(discovery_url).mock(return_value=Response(200, json=MOCK_SMART_CONFIG))

        # Mock token endpoint (called once)
        token_mock = respx.post(token_url).mock(return_value=Response(200, json=MOCK_TOKEN_RESPONSE))

        client = FHIRAuthClient()
        try:
            # First call: cache miss, should authenticate
            token1 = await client.get_access_token()
            assert token1 == "mock_access_token_xyz"
            assert token_mock.call_count == 1

            # Second call: cache hit, should NOT authenticate
            token2 = await client.get_access_token()
            assert token2 == "mock_access_token_xyz"
            assert token_mock.call_count == 1  # No additional call
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_get_access_token_cache_miss_refresh(mock_env):
    """Test get_access_token auto-refreshes on cache miss (AC Scenario 3)."""
    discovery_url = "https://ehr.example.com/fhir/.well-known/smart-configuration"
    token_url = "https://ehr.example.com/auth/token"

    with respx.mock:
        # Mock SMART discovery
        respx.get(discovery_url).mock(return_value=Response(200, json=MOCK_SMART_CONFIG))

        # Mock token endpoint (will be called twice)
        token_mock = respx.post(token_url).mock(return_value=Response(200, json=MOCK_TOKEN_RESPONSE))

        client = FHIRAuthClient()
        try:
            # First authentication
            token1 = await client.get_access_token()
            assert token1 == "mock_access_token_xyz"
            assert token_mock.call_count == 1

            # Invalidate cache (simulate expiry)
            await client.invalidate_token()

            # Second call: cache miss, should re-authenticate
            token2 = await client.get_access_token()
            assert token2 == "mock_access_token_xyz"
            assert token_mock.call_count == 2  # Second authentication
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_get_access_token_expiry_buffer_refresh(mock_env):
    """Test token refresh when within 60-second expiry buffer (AC Scenario 3)."""
    discovery_url = "https://ehr.example.com/fhir/.well-known/smart-configuration"
    token_url = "https://ehr.example.com/auth/token"

    # Token with 55 seconds remaining (within 60s buffer)
    short_token_response = {
        "access_token": "short_token",
        "token_type": "Bearer",
        "expires_in": 55,  # Will be expired immediately due to 60s buffer
    }

    with respx.mock:
        # Mock SMART discovery
        respx.get(discovery_url).mock(return_value=Response(200, json=MOCK_SMART_CONFIG))

        # Mock token endpoint (returns short-lived token)
        token_mock = respx.post(token_url).mock(return_value=Response(200, json=short_token_response))

        client = FHIRAuthClient()
        try:
            with freeze_time("2026-07-16 12:00:00"):
                # First call: authenticate, but token expires immediately (55s - 60s buffer)
                token1 = await client.get_access_token()
                assert token1 == "short_token"
                assert token_mock.call_count == 1

            # Second call: token is expired, should re-authenticate
            with freeze_time("2026-07-16 12:00:01"):
                token2 = await client.get_access_token()
                assert token2 == "short_token"
                assert token_mock.call_count == 2  # Second authentication
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_authenticate_failure_401(mock_env):
    """Test 401 Unauthorized raises FHIRAuthenticationError (AC Scenario 4)."""
    discovery_url = "https://ehr.example.com/fhir/.well-known/smart-configuration"
    token_url = "https://ehr.example.com/auth/token"

    with respx.mock:
        # Mock SMART discovery
        respx.get(discovery_url).mock(return_value=Response(200, json=MOCK_SMART_CONFIG))

        # Mock token endpoint returning 401
        respx.post(token_url).mock(
            return_value=Response(401, json={"error": "invalid_client"})
        )

        client = FHIRAuthClient()
        try:
            with pytest.raises(FHIRAuthenticationError) as exc_info:
                await client.authenticate()

            assert exc_info.value.status_code == 401
            assert "401" in str(exc_info.value)
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_authenticate_network_error(mock_env):
    """Test network error raises FHIRAuthenticationError."""
    import httpx
    discovery_url = "https://ehr.example.com/fhir/.well-known/smart-configuration"
    token_url = "https://ehr.example.com/auth/token"

    with respx.mock:
        # Mock SMART discovery
        respx.get(discovery_url).mock(return_value=Response(200, json=MOCK_SMART_CONFIG))

        # Mock token endpoint with network error
        respx.post(token_url).mock(side_effect=httpx.ConnectError("Connection timeout"))

        client = FHIRAuthClient()
        try:
            with pytest.raises(FHIRAuthenticationError) as exc_info:
                await client.authenticate()

            assert "network error" in str(exc_info.value).lower()
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_authenticate_invalid_json(mock_env):
    """Test invalid JSON response raises FHIRAuthenticationError."""
    discovery_url = "https://ehr.example.com/fhir/.well-known/smart-configuration"
    token_url = "https://ehr.example.com/auth/token"

    with respx.mock:
        # Mock SMART discovery
        respx.get(discovery_url).mock(return_value=Response(200, json=MOCK_SMART_CONFIG))

        # Mock token endpoint returning invalid JSON
        respx.post(token_url).mock(return_value=Response(200, text="Not JSON"))

        client = FHIRAuthClient()
        try:
            with pytest.raises(FHIRAuthenticationError) as exc_info:
                await client.authenticate()

            assert "invalid JSON" in str(exc_info.value)
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_authenticate_missing_access_token(mock_env):
    """Test missing access_token in response raises FHIRAuthenticationError."""
    discovery_url = "https://ehr.example.com/fhir/.well-known/smart-configuration"
    token_url = "https://ehr.example.com/auth/token"

    invalid_token_response = {
        # Missing access_token
        "token_type": "Bearer",
        "expires_in": 3600,
    }

    with respx.mock:
        # Mock SMART discovery
        respx.get(discovery_url).mock(return_value=Response(200, json=MOCK_SMART_CONFIG))

        # Mock token endpoint returning incomplete response
        respx.post(token_url).mock(return_value=Response(200, json=invalid_token_response))

        client = FHIRAuthClient()
        try:
            with pytest.raises(FHIRAuthenticationError) as exc_info:
                await client.authenticate()

            assert "missing 'access_token'" in str(exc_info.value)
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_invalidate_token(mock_env):
    """Test invalidate_token clears cache."""
    discovery_url = "https://ehr.example.com/fhir/.well-known/smart-configuration"
    token_url = "https://ehr.example.com/auth/token"

    with respx.mock:
        # Mock SMART discovery
        respx.get(discovery_url).mock(return_value=Response(200, json=MOCK_SMART_CONFIG))

        # Mock token endpoint
        respx.post(token_url).mock(return_value=Response(200, json=MOCK_TOKEN_RESPONSE))

        client = FHIRAuthClient()
        try:
            # Authenticate and cache token
            await client.get_access_token()

            # Invalidate cache
            await client.invalidate_token()

            # Cache should be empty (is_expired returns True)
            assert await client._cache.is_expired()
        finally:
            await client.close()
