"""Unit tests for FHIRClient.get_patient_by_mrn() patient resolution logic.

Tests validate three-tier resolution strategy (AIR-014):
1. MRN search → resolution_method=MRN, partial_match=False
2. Name+DOB fallback → resolution_method=NAME_DOB, partial_match=True
3. Unresolvable → returns None with warning log

Design refs:
    TASK-003 — Patient resolution with MRN fallback
    AIR-014  — Three-tier patient resolution strategy
"""
import os
import pytest
import respx
from httpx import Response

from app.core.config import get_settings
from app.core.fhir import FHIRClient, PatientResolutionMethod


@pytest.fixture(autouse=True)
def mock_fhir_env(monkeypatch):
    """Mock FHIR environment variables for all tests."""
    monkeypatch.setenv("FHIR_BASE_URL", "http://fhir-server.test/fhir")
    monkeypatch.setenv("FHIR_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("FHIR_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("FHIR_SCOPE", "system/*.read")
    monkeypatch.setenv("FHIR_MRN_SYSTEM", "http://hospital.org/mrn")
    
    # Clear settings cache to pick up new env vars
    get_settings.cache_clear()
    
    yield
    
    # Clear cache after test
    get_settings.cache_clear()


@pytest.fixture
def fhir_client():
    """Create FHIRClient instance for testing."""
    client = FHIRClient()
    yield client
    # Cleanup not needed for unit tests (no real connections)


@pytest.fixture
def mock_fhir_bundle_mrn_hit():
    """Mock FHIR Bundle response for successful MRN search."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "patient-123",
                    "identifier": [
                        {
                            "type": {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                        "code": "MR",
                                    }
                                ]
                            },
                            "system": "http://hospital.org/mrn",
                            "value": "MRN-001",
                        }
                    ],
                    "name": [
                        {
                            "family": "Smith",
                            "given": ["John"],
                        }
                    ],
                    "gender": "male",
                    "birthDate": "1980-01-01",
                }
            }
        ],
    }


@pytest.fixture
def mock_fhir_bundle_empty():
    """Mock FHIR Bundle response for no matches."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 0,
        "entry": [],
    }


@pytest.fixture
def mock_fhir_bundle_name_dob_hit():
    """Mock FHIR Bundle response for successful name+DOB search."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "patient-456",
                    "name": [
                        {
                            "family": "Smith",
                            "given": ["Jane"],
                        }
                    ],
                    "gender": "female",
                    "birthDate": "1985-05-15",
                }
            }
        ],
    }


@pytest.fixture
def mock_fhir_bundle_multiple_matches():
    """Mock FHIR Bundle response with multiple name+DOB matches."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 2,
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "patient-789",
                    "name": [
                        {
                            "family": "Johnson",
                            "given": ["Alice"],
                        }
                    ],
                    "gender": "female",
                    "birthDate": "1990-03-20",
                }
            },
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "patient-790",
                    "name": [
                        {
                            "family": "Johnson",
                            "given": ["Alice"],
                        }
                    ],
                    "gender": "female",
                    "birthDate": "1990-03-20",
                }
            },
        ],
    }


@pytest.mark.asyncio
@respx.mock
async def test_mrn_hit_returns_patient_with_mrn_resolution(
    fhir_client, mock_fhir_bundle_mrn_hit
):
    """Test Scenario 1: MRN search returns patient with resolution_method=MRN and partial_match=False.

    Validates:
    - Patient found by MRN identifier search
    - resolution_method set to MRN
    - partial_match set to False
    - Patient fields populated correctly
    """
    # Mock SMART discovery
    respx.get("http://fhir-server.test/fhir/.well-known/smart-configuration").mock(
        return_value=Response(
            200,
            json={"token_endpoint": "http://fhir-server.test/oauth/token"},
        )
    )

    # Mock token endpoint
    respx.post("http://fhir-server.test/oauth/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "test-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
    )

    # Mock MRN search - returns patient
    respx.get("http://fhir-server.test/fhir/Patient").mock(
        return_value=Response(200, json=mock_fhir_bundle_mrn_hit)
    )

    # Execute
    patient = await fhir_client.get_patient_by_mrn("MRN-001")

    # Verify
    assert patient is not None
    assert patient.id == "patient-123"
    assert patient.mrn == "MRN-001"
    assert patient.family_name == "Smith"
    assert patient.given_name == "John"
    assert patient.resolution_method == PatientResolutionMethod.MRN
    assert patient.partial_match is False


@pytest.mark.asyncio
@respx.mock
async def test_mrn_miss_fallback_returns_patient_with_name_dob_resolution(
    fhir_client, mock_fhir_bundle_empty, mock_fhir_bundle_name_dob_hit
):
    """Test Scenario 2: MRN miss with name+DOB fallback returns patient with resolution_method=NAME_DOB and partial_match=True.

    Validates:
    - MRN search returns no results
    - Fallback to name+DOB search
    - Patient found by name+DOB
    - resolution_method set to NAME_DOB
    - partial_match set to True
    """
    # Mock SMART discovery
    respx.get("http://fhir-server.test/fhir/.well-known/smart-configuration").mock(
        return_value=Response(
            200,
            json={"token_endpoint": "http://fhir-server.test/oauth/token"},
        )
    )

    # Mock token endpoint
    respx.post("http://fhir-server.test/oauth/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "test-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
    )

    # Mock MRN search - returns empty
    respx.get(
        "http://fhir-server.test/fhir/Patient",
        params={"identifier": "http://hospital.org/mrn|MRN-UNKNOWN"},
    ).mock(return_value=Response(200, json=mock_fhir_bundle_empty))

    # Mock name+DOB fallback - returns patient
    respx.get(
        "http://fhir-server.test/fhir/Patient",
        params={"family": "Smith", "birthdate": "1985-05-15"},
    ).mock(return_value=Response(200, json=mock_fhir_bundle_name_dob_hit))

    # Execute
    patient = await fhir_client.get_patient_by_mrn(
        mrn="MRN-UNKNOWN", fallback_name="Smith", fallback_dob="1985-05-15"
    )

    # Verify
    assert patient is not None
    assert patient.id == "patient-456"
    assert patient.family_name == "Smith"
    assert patient.given_name == "Jane"
    assert patient.resolution_method == PatientResolutionMethod.NAME_DOB
    assert patient.partial_match is True


@pytest.mark.asyncio
@respx.mock
async def test_mrn_miss_no_fallback_returns_none(
    fhir_client, mock_fhir_bundle_empty, caplog
):
    """Test Scenario 3: MRN miss without fallback params returns None.

    Validates:
    - MRN search returns no results
    - No fallback parameters provided
    - Returns None
    - Warning logged about unresolvable patient
    """
    # Mock SMART discovery
    respx.get("http://fhir-server.test/fhir/.well-known/smart-configuration").mock(
        return_value=Response(
            200,
            json={"token_endpoint": "http://fhir-server.test/oauth/token"},
        )
    )

    # Mock token endpoint
    respx.post("http://fhir-server.test/oauth/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "test-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
    )

    # Mock MRN search - returns empty
    respx.get("http://fhir-server.test/fhir/Patient").mock(
        return_value=Response(200, json=mock_fhir_bundle_empty)
    )

    # Execute
    patient = await fhir_client.get_patient_by_mrn("MRN-NONEXISTENT")

    # Verify
    assert patient is None

    # Verify warning logged
    assert "patient_resolution_unresolvable" in caplog.text or "Patient unresolvable" in caplog.text


@pytest.mark.asyncio
@respx.mock
async def test_unresolvable_patient_both_searches_fail(
    fhir_client, mock_fhir_bundle_empty, caplog
):
    """Test Scenario 3b: Both MRN and name+DOB searches fail, returns None.

    Validates:
    - MRN search returns no results
    - Name+DOB fallback returns no results
    - Returns None
    - Warning logged about unresolvable patient
    """
    # Mock SMART discovery
    respx.get("http://fhir-server.test/fhir/.well-known/smart-configuration").mock(
        return_value=Response(
            200,
            json={"token_endpoint": "http://fhir-server.test/oauth/token"},
        )
    )

    # Mock token endpoint
    respx.post("http://fhir-server.test/oauth/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "test-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
    )

    # Mock MRN search - returns empty
    respx.get(
        "http://fhir-server.test/fhir/Patient",
        params={"identifier": "http://hospital.org/mrn|MRN-NONEXISTENT"},
    ).mock(return_value=Response(200, json=mock_fhir_bundle_empty))

    # Mock name+DOB fallback - also returns empty
    respx.get(
        "http://fhir-server.test/fhir/Patient",
        params={"family": "ZZZ", "birthdate": "1900-01-01"},
    ).mock(return_value=Response(200, json=mock_fhir_bundle_empty))

    # Execute
    patient = await fhir_client.get_patient_by_mrn(
        mrn="MRN-NONEXISTENT", fallback_name="ZZZ", fallback_dob="1900-01-01"
    )

    # Verify
    assert patient is None

    # Verify warning logged
    assert "patient_resolution_unresolvable" in caplog.text or "Patient unresolvable" in caplog.text


@pytest.mark.asyncio
@respx.mock
async def test_multiple_name_dob_matches_uses_first_result(
    fhir_client, mock_fhir_bundle_empty, mock_fhir_bundle_multiple_matches, caplog
):
    """Test edge case: Multiple name+DOB matches, uses first result with warning.

    Validates:
    - MRN search returns no results
    - Name+DOB fallback returns multiple matches
    - Uses first match
    - Warning logged about multiple matches
    - resolution_method set to NAME_DOB
    - partial_match set to True
    """
    # Mock SMART discovery
    respx.get("http://fhir-server.test/fhir/.well-known/smart-configuration").mock(
        return_value=Response(
            200,
            json={"token_endpoint": "http://fhir-server.test/oauth/token"},
        )
    )

    # Mock token endpoint
    respx.post("http://fhir-server.test/oauth/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "test-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
    )

    # Mock MRN search - returns empty
    respx.get(
        "http://fhir-server.test/fhir/Patient",
        params={"identifier": "http://hospital.org/mrn|MRN-UNKNOWN"},
    ).mock(return_value=Response(200, json=mock_fhir_bundle_empty))

    # Mock name+DOB fallback - returns multiple matches
    respx.get(
        "http://fhir-server.test/fhir/Patient",
        params={"family": "Johnson", "birthdate": "1990-03-20"},
    ).mock(return_value=Response(200, json=mock_fhir_bundle_multiple_matches))

    # Execute
    patient = await fhir_client.get_patient_by_mrn(
        mrn="MRN-UNKNOWN", fallback_name="Johnson", fallback_dob="1990-03-20"
    )

    # Verify
    assert patient is not None
    assert patient.id == "patient-789"  # First match
    assert patient.family_name == "Johnson"
    assert patient.given_name == "Alice"
    assert patient.resolution_method == PatientResolutionMethod.NAME_DOB
    assert patient.partial_match is True

    # Verify multiple matches warning logged
    assert "patient_resolution_multiple_matches" in caplog.text or "multiple matches" in caplog.text
