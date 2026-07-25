"""Unit tests for FHIR retry logic with selective error handling.

Tests cover:
  - Success after 1 transient failure (503)
  - Success after 2 transient failures
  - Exhausted retries after 3 failures
  - No retry on 4xx errors (400, 404)
  - Network timeout triggers retry
  - Connection error triggers retry
  - Retry metrics incremented correctly

Design refs:
    US-018 AC Scenario 1 — Retry succeeds after 503
    US-018 TASK-003 — Selective error handling
"""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.core.fhir.client import FHIRClient
from app.core.fhir.exceptions import (
    FHIRClientError,
    FHIRNetworkError,
    FHIRServerError,
)
from app.core.fhir.metrics import RETRY_TOTAL

MOCK_TOKEN_RESPONSE = {
    "access_token": "mock_access_token",
    "token_type": "Bearer",
    "expires_in": 3600,
}

MOCK_SMART_CONFIG = {
    "token_endpoint": "https://ehr.example.com/auth/token",
}


@pytest.fixture
def mock_env(monkeypatch):
    """Set environment variables for FHIR client."""
    monkeypatch.setenv("FHIR_BASE_URL", "https://ehr.example.com/fhir")
    monkeypatch.setenv("FHIR_CLIENT_ID", "test_client")
    monkeypatch.setenv("FHIR_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("FHIR_SCOPE", "system/*.read")
    monkeypatch.setenv("FHIR_MRN_SYSTEM", "http://hospital.org/mrn")


# ── Retry Success Tests ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retry_succeeds_after_one_503_failure(mock_env):
    """AC Scenario 1: Retry succeeds after one transient failure (HTTP 503)."""
    with respx.mock:
        # Mock SMART discovery and auth
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock Patient fetch: first 503, then 200
        patient_url = respx.get("https://ehr.example.com/fhir/Patient/123")
        patient_url.mock(side_effect=[
            Response(503, text="Service Unavailable"),
            Response(200, json={"resourceType": "Patient", "id": "123"}),
        ])

        client = FHIRClient()
        result = await client._fetch_with_retry(
            "https://ehr.example.com/fhir/Patient/123"
        )

        assert result["id"] == "123"
        assert patient_url.call_count == 2


@pytest.mark.asyncio
async def test_retry_succeeds_after_two_failures(mock_env):
    """Retry succeeds after 2 transient failures."""
    with respx.mock:
        # Mock SMART discovery and auth
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock Encounter fetch: 500, 503, then 200
        encounter_url = respx.get("https://ehr.example.com/fhir/Encounter/456")
        encounter_url.mock(side_effect=[
            Response(500, text="Internal Server Error"),
            Response(503, text="Service Unavailable"),
            Response(200, json={"resourceType": "Encounter", "id": "456"}),
        ])

        client = FHIRClient()
        result = await client._fetch_with_retry(
            "https://ehr.example.com/fhir/Encounter/456"
        )

        assert result["id"] == "456"
        assert encounter_url.call_count == 3


# ── No Retry on 4xx Tests ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_no_retry_on_404_error(mock_env):
    """Technical Note: No retry on 4xx errors (404)."""
    with respx.mock:
        # Mock SMART discovery and auth
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock Patient fetch: 404
        patient_url = respx.get("https://ehr.example.com/fhir/Patient/999")
        patient_url.mock(return_value=Response(404, text="Resource not found"))

        client = FHIRClient()
        with pytest.raises(FHIRClientError) as exc_info:
            await client._fetch_with_retry(
                "https://ehr.example.com/fhir/Patient/999"
            )

        assert exc_info.value.status_code == 404
        assert patient_url.call_count == 1  # No retry


@pytest.mark.asyncio
async def test_no_retry_on_400_bad_request(mock_env):
    """No retry on 400 Bad Request."""
    with respx.mock:
        # Mock SMART discovery and auth
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock Patient search: 400
        patient_url = respx.get("https://ehr.example.com/fhir/Patient")
        patient_url.mock(return_value=Response(400, text="Invalid query parameter"))

        client = FHIRClient()
        with pytest.raises(FHIRClientError) as exc_info:
            await client._fetch_with_retry(
                "https://ehr.example.com/fhir/Patient", params={"invalid": "param"}
            )

        assert exc_info.value.status_code == 400
        assert patient_url.call_count == 1


# ── Exhausted Retries Tests ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_exhausted_retries_after_3_failures(mock_env):
    """Retry exhaustion after 3 consecutive 500 errors."""
    with respx.mock:
        # Mock SMART discovery and auth
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock Patient fetch: all 500
        patient_url = respx.get("https://ehr.example.com/fhir/Patient/123")
        patient_url.mock(return_value=Response(500, text="Server error"))

        client = FHIRClient()
        with pytest.raises(FHIRServerError) as exc_info:
            await client._fetch_with_retry(
                "https://ehr.example.com/fhir/Patient/123"
            )

        assert exc_info.value.status_code == 500
        assert exc_info.value.attempts == 3
        assert patient_url.call_count == 3


# ── Network Error Tests ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retry_on_network_timeout(mock_env):
    """Network timeout triggers retry."""
    import httpx

    with respx.mock:
        # Mock SMART discovery and auth
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock Patient fetch: timeout then success
        patient_url = respx.get("https://ehr.example.com/fhir/Patient/123")
        patient_url.mock(side_effect=[
            httpx.TimeoutException("Request timed out"),
            Response(200, json={"resourceType": "Patient", "id": "123"}),
        ])

        client = FHIRClient()
        result = await client._fetch_with_retry(
            "https://ehr.example.com/fhir/Patient/123"
        )

        assert result["id"] == "123"
        assert patient_url.call_count == 2


@pytest.mark.asyncio
async def test_retry_on_connection_error(mock_env):
    """Connection error triggers retry."""
    import httpx

    with respx.mock:
        # Mock SMART discovery and auth
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock Patient fetch: connection error then success
        patient_url = respx.get("https://ehr.example.com/fhir/Patient/456")
        patient_url.mock(side_effect=[
            httpx.ConnectError("Connection refused"),
            Response(200, json={"resourceType": "Patient", "id": "456"}),
        ])

        client = FHIRClient()
        result = await client._fetch_with_retry(
            "https://ehr.example.com/fhir/Patient/456"
        )

        assert result["id"] == "456"
        assert patient_url.call_count == 2


# ── Metrics Tests ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retry_metrics_increment_on_success(mock_env):
    """Retry success increments correct metric."""
    initial_success = RETRY_TOTAL.labels(outcome="success")._value.get()

    with respx.mock:
        # Mock SMART discovery and auth
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock Patient fetch: 503 then 200
        patient_url = respx.get("https://ehr.example.com/fhir/Patient/123")
        patient_url.mock(side_effect=[
            Response(503, text="Service Unavailable"),
            Response(200, json={"resourceType": "Patient", "id": "123"}),
        ])

        client = FHIRClient()
        await client._fetch_with_retry("https://ehr.example.com/fhir/Patient/123")

        final_success = RETRY_TOTAL.labels(outcome="success")._value.get()
        assert final_success == initial_success + 1
