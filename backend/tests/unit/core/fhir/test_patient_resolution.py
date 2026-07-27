"""Unit tests for patient resolution with MRN fallback.

Tests:
- MRN hit returns PatientModel with resolution_method=MRN
- MRN miss with name+DOB fallback returns partial_match=True
- Both methods fail returns None with warning log
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.core.fhir import FHIRClient, PatientResolutionMethod

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
    """Set environment variables."""
    monkeypatch.setenv("FHIR_BASE_URL", "https://ehr.example.com/fhir")
    monkeypatch.setenv("FHIR_CLIENT_ID", "test_client")
    monkeypatch.setenv("FHIR_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("FHIR_SCOPE", "system/*.read")
    monkeypatch.setenv("FHIR_MRN_SYSTEM", "http://hospital.org/mrn")


@pytest.mark.asyncio
@respx.mock
async def test_patient_resolution_mrn_hit(mock_env):
    """Test MRN hit returns PatientModel with resolution_method=MRN (AC Scenario 1)."""
    patient_json = load_fixture("patient_valid.json")
    bundle_json = {"resourceType": "Bundle", "type": "searchset", "total": 1, "entry": [{"resource": patient_json}]}

    # Mock SMART discovery
    respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
        return_value=Response(200, json=MOCK_SMART_CONFIG)
    )
    
    # Mock token endpoint
    respx.post("https://ehr.example.com/auth/token").mock(
        return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
    )

    # Mock MRN search success
    respx.get("https://ehr.example.com/fhir/Patient").mock(
        return_value=Response(200, json=bundle_json)
    )

    client = FHIRClient()
    try:
        patient = await client.get_patient_by_mrn("MRN-001")

        assert patient is not None
        assert patient.id == "patient-001"
        assert patient.mrn == "MRN-001"
        assert patient.resolution_method == PatientResolutionMethod.MRN
        assert patient.partial_match is False
    finally:
        await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_patient_resolution_name_dob_fallback(mock_env):
    """Test MRN miss with name+DOB fallback returns partial_match=True (AC Scenario 2)."""
    patient_json = load_fixture("patient_valid.json")
    bundle_empty = {"resourceType": "Bundle", "type": "searchset", "total": 0, "entry": []}
    bundle_fallback = {"resourceType": "Bundle", "type": "searchset", "total": 1, "entry": [{"resource": patient_json}]}

    # Mock SMART discovery
    respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
        return_value=Response(200, json=MOCK_SMART_CONFIG)
    )
    
    # Mock token endpoint
    respx.post("https://ehr.example.com/auth/token").mock(
        return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
    )

    # Mock MRN search miss - use route() for specific query params
    mrn_route = respx.get("https://ehr.example.com/fhir/Patient", params={"identifier": "http://hospital.org/mrn|MRN-UNKNOWN"})
    mrn_route.mock(return_value=Response(200, json=bundle_empty))

    # Mock name+DOB fallback success
    fallback_route = respx.get("https://ehr.example.com/fhir/Patient", params={"family": "Smith", "birthdate": "1980-01-01"})
    fallback_route.mock(return_value=Response(200, json=bundle_fallback))

    client = FHIRClient()
    try:
        patient = await client.get_patient_by_mrn(
            mrn="MRN-UNKNOWN",
            fallback_name="Smith",
            fallback_dob="1980-01-01",
        )

        assert patient is not None
        assert patient.resolution_method == PatientResolutionMethod.NAME_DOB
        assert patient.partial_match is True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_patient_resolution_unresolvable(mock_env):
    """Test both MRN and name+DOB fail returns None with warning."""
    bundle_empty = {"resourceType": "Bundle", "entry": []}

    with respx.mock:
        respx.get("https://ehr.example.com/fhir/.well-known/smart-configuration").mock(
            return_value=Response(200, json=MOCK_SMART_CONFIG)
        )
        respx.post("https://ehr.example.com/auth/token").mock(
            return_value=Response(200, json=MOCK_TOKEN_RESPONSE)
        )

        # Mock both searches fail
        respx.get("https://ehr.example.com/fhir/Patient").mock(
            return_value=Response(200, json=bundle_empty)
        )

        client = FHIRClient()
        try:
            patient = await client.get_patient_by_mrn(
                mrn="MRN-NONEXISTENT",
                fallback_name="ZZZ",
                fallback_dob="1900-01-01",
            )

            assert patient is None
        finally:
            await client.close()
