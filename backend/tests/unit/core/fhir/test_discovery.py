"""Unit tests for SMART on FHIR discovery client.

Tests:
- Successful SMART configuration fetch
- Token endpoint extraction
- Network error handling
- Invalid JSON handling
- Missing token_endpoint handling
"""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.core.fhir.discovery import discover_smart_config, get_token_endpoint
from app.core.fhir.exceptions import FHIRAuthenticationError

# Sample SMART configuration (based on SMART on FHIR v2.0 spec)
SAMPLE_SMART_CONFIG = {
    "authorization_endpoint": "https://ehr.example.com/auth/authorize",
    "token_endpoint": "https://ehr.example.com/auth/token",
    "token_endpoint_auth_methods_supported": [
        "client_secret_basic",
        "client_secret_post",
    ],
    "grant_types_supported": ["authorization_code", "client_credentials"],
    "scopes_supported": ["system/*.read", "patient/*.read"],
    "capabilities": [
        "client-confidential-symmetric",
        "permission-offline",
        "context-standalone-patient",
    ],
}


@pytest.mark.asyncio
async def test_discover_smart_config_success():
    """Test successful SMART configuration discovery."""
    base_url = "https://ehr.example.com/fhir"
    discovery_url = f"{base_url}/.well-known/smart-configuration"

    with respx.mock:
        respx.get(discovery_url).mock(return_value=Response(200, json=SAMPLE_SMART_CONFIG))

        config = await discover_smart_config(base_url)

        assert config == SAMPLE_SMART_CONFIG
        assert config["token_endpoint"] == "https://ehr.example.com/auth/token"


@pytest.mark.asyncio
async def test_discover_smart_config_trailing_slash():
    """Test discovery with base URL containing trailing slash."""
    base_url = "https://ehr.example.com/fhir/"  # Note trailing slash
    discovery_url = "https://ehr.example.com/fhir/.well-known/smart-configuration"

    with respx.mock:
        respx.get(discovery_url).mock(return_value=Response(200, json=SAMPLE_SMART_CONFIG))

        config = await discover_smart_config(base_url)

        assert config["token_endpoint"] == "https://ehr.example.com/auth/token"


@pytest.mark.asyncio
async def test_discover_smart_config_network_error():
    """Test discovery failure due to network error."""
    import httpx
    base_url = "https://unreachable.example.com/fhir"
    discovery_url = f"{base_url}/.well-known/smart-configuration"

    with respx.mock:
        respx.get(discovery_url).mock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(FHIRAuthenticationError) as exc_info:
            await discover_smart_config(base_url)

        assert "Failed to fetch SMART configuration" in str(exc_info.value)


@pytest.mark.asyncio
async def test_discover_smart_config_http_error():
    """Test discovery failure due to HTTP error (e.g., 404)."""
    base_url = "https://ehr.example.com/fhir"
    discovery_url = f"{base_url}/.well-known/smart-configuration"

    with respx.mock:
        respx.get(discovery_url).mock(return_value=Response(404, text="Not Found"))

        with pytest.raises(FHIRAuthenticationError) as exc_info:
            await discover_smart_config(base_url)

        assert "Failed to fetch SMART configuration" in str(exc_info.value)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_discover_smart_config_invalid_json():
    """Test discovery failure due to invalid JSON response."""
    base_url = "https://ehr.example.com/fhir"
    discovery_url = f"{base_url}/.well-known/smart-configuration"

    with respx.mock:
        respx.get(discovery_url).mock(return_value=Response(200, text="Not JSON"))

        with pytest.raises(FHIRAuthenticationError) as exc_info:
            await discover_smart_config(base_url)

        assert "invalid JSON" in str(exc_info.value)


@pytest.mark.asyncio
async def test_discover_smart_config_missing_token_endpoint():
    """Test discovery failure when token_endpoint is missing."""
    base_url = "https://ehr.example.com/fhir"
    discovery_url = f"{base_url}/.well-known/smart-configuration"

    incomplete_config = {
        "authorization_endpoint": "https://ehr.example.com/auth/authorize",
        # Missing token_endpoint
    }

    with respx.mock:
        respx.get(discovery_url).mock(return_value=Response(200, json=incomplete_config))

        with pytest.raises(FHIRAuthenticationError) as exc_info:
            await discover_smart_config(base_url)

        assert "missing 'token_endpoint'" in str(exc_info.value)


def test_get_token_endpoint():
    """Test token endpoint extraction from SMART config."""
    token_endpoint = get_token_endpoint(SAMPLE_SMART_CONFIG)
    assert token_endpoint == "https://ehr.example.com/auth/token"


def test_get_token_endpoint_missing():
    """Test KeyError when token_endpoint is missing."""
    invalid_config = {"authorization_endpoint": "https://example.com/auth"}
    with pytest.raises(KeyError):
        get_token_endpoint(invalid_config)

