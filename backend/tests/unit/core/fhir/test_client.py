"""Unit tests for FHIRClient resource fetch methods.

Tests:
- Fetch methods return validated Pydantic models
- Rate limiter enforces 100 req/min capacity
- Circuit breaker opens after failures and closes after cooldown
- FHIR Bundle responses parsed correctly
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.core.fhir import FHIRClient
from app.core.fhir.circuit_breaker import CircuitBreakerError, _reset_for_testing

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "fhir_r4"

MOCK_TOKEN_RESPONSE = {
    "access_token": "mock_access_token",
    "token_type": "Bearer",
    "expires_in": 3600,
}

MOCK_SMART_CONFIG = {
    "token_endpoint": "https://ehr.example.com/auth/token",
}


def load_fixture(filename: str) -> dict:
    """Load FHIR R4 JSON fixture."""
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)


@pytest.fixture
def mock_env(monkeypatch):
    """Set environment variables for FHIR client."""
    monkeypatch.setenv("FHIR_BASE_URL", "https://ehr.example.com/fhir")
    monkeypatch.setenv("FHIR_CLIENT_ID", "test_client")
    monkeypatch.setenv("FHIR_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("FHIR_SCOPE", "system/*.read")
    monkeypatch.setenv("FHIR_MRN_SYSTEM", "http://hospital.org/mrn")


@pytest.fixture
async def reset_circuit_breaker():
    """Reset circuit breaker singleton before each test."""
    await _reset_for_testing()
    yield
    # Reset again after test to clean up
    await _reset_for_testing()


@pytest.mark.asyncio
async def test_get_encounter_by_id_success(mock_env):
    """Test get_encounter_by_id returns EncounterModel."""
    encounter_json = load_fixture("encounter_valid.json")

    with respx.mock:
        # Mock SMART discovery and auth
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock Encounter fetch
        respx.get("https://ehr.example.com/fhir/Encounter/encounter-001").mock(
            return_value=Response(200, json=encounter_json)
        )

        client = FHIRClient()
        try:
            encounter = await client.get_encounter_by_id("encounter-001")

            assert encounter.id == "encounter-001"
            assert encounter.patient_id == "patient-001"
            assert encounter.status == "in-progress"
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_get_medication_statements_returns_list(mock_env):
    """Test get_medication_statements parses Bundle and returns list."""
    bundle_json = load_fixture("bundle_medication_statements.json")

    with respx.mock:
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        respx.get("https://ehr.example.com/fhir/MedicationStatement").mock(
            return_value=Response(200, json=bundle_json)
        )

        client = FHIRClient()
        try:
            medications = await client.get_medication_statements("patient-001")

            assert len(medications) == 1
            assert medications[0].id == "med-statement-001"
            assert medications[0].medication_display == "Metformin 500mg"
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_get_medication_statements_empty_bundle(mock_env):
    """Test get_medication_statements returns empty list for no results."""
    bundle_json = load_fixture("bundle_empty.json")

    with respx.mock:
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        respx.get("https://ehr.example.com/fhir/MedicationStatement").mock(
            return_value=Response(200, json=bundle_json)
        )

        client = FHIRClient()
        try:
            medications = await client.get_medication_statements("patient-001")
            assert len(medications) == 0
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures(mock_env, reset_circuit_breaker):
    """Test circuit breaker opens after 10 consecutive failures."""
    with respx.mock:
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock 10 failures
        respx.get("https://ehr.example.com/fhir/Encounter/enc-fail").mock(
            return_value=Response(500, text="Internal Server Error")
        )

        client = FHIRClient()
        try:
            # Trigger 10 failures to open circuit
            for _ in range(10):
                with pytest.raises(Exception):  # httpx.HTTPStatusError or CircuitBreakerError
                    await client.get_encounter_by_id("enc-fail")

            # 11th request should be rejected by open circuit
            with pytest.raises(CircuitBreakerError):
                await client.get_encounter_by_id("enc-fail")

        finally:
            await client.close()


@pytest.mark.asyncio
async def test_rate_limiter_enforces_capacity(mock_env):
    """Test rate limiter blocks after 100 requests."""
    import time

    with respx.mock:
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        encounter_json = load_fixture("encounter_valid.json")
        respx.get("https://ehr.example.com/fhir/Encounter/encounter-001").mock(
            return_value=Response(200, json=encounter_json)
        )

        client = FHIRClient()
        try:
            start = time.time()

            # Make 101 requests (should hit rate limit and block)
            for _ in range(101):
                await client.get_encounter_by_id("encounter-001")

            elapsed = time.time() - start

            # Should take >0 seconds due to rate limiting (not instant)
            assert elapsed > 0.5, "Rate limiter should have blocked at least briefly"

        finally:
            await client.close()
