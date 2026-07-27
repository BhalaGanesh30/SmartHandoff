"""Unit tests for medication reconciliation API endpoint.

US-030 TASK-006: Tests GET /api/v1/encounters/{id}/medications/reconciliation
for all response scenarios (200, 202, 403, 404).
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models.encounter import Encounter
from app.models.medication import (
    Medication,
    MedicationListSource,
    ReconciliationCategory,
    ReconciliationFlag,
)

# Test client for FastAPI app
client = TestClient(app)

# Mock JWTs
PHARMACIST_JWT = "test-pharmacist-jwt"
PATIENT_JWT = "test-patient-jwt"

# Test encounter ID
TEST_ENCOUNTER_ID = str(uuid4())


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_encounter():
    """Mock Encounter ORM instance."""
    encounter = Encounter()
    encounter.id = uuid4()
    encounter.patient_id = uuid4()
    encounter.status = "ADMITTED"
    return encounter


@pytest.fixture
def mock_medications():
    """Mock list of reconciled medications."""
    now = datetime.now(timezone.utc)
    return [
        Medication(
            id=uuid4(),
            name="Metformin 500mg",
            rxnorm_cui="860975",
            reconciliation_category=ReconciliationCategory.CONTINUED,
            flags=[],
            dose_value=500.0,
            dose_unit="mg",
            route="oral",
            frequency="twice daily",
            sources=[MedicationListSource.PRE_ADMIT, MedicationListSource.DISCHARGE],
            reconciliation_completed_at=now,
        ),
        Medication(
            id=uuid4(),
            name="Apixaban 5mg",
            rxnorm_cui="1364430",
            reconciliation_category=ReconciliationCategory.NEW,
            flags=[],
            dose_value=5.0,
            dose_unit="mg",
            route="oral",
            frequency="twice daily",
            sources=[MedicationListSource.DISCHARGE],
            reconciliation_completed_at=now,
        ),
    ]


@pytest.fixture
def mock_pharmacist_claims():
    """Mock JWT claims for pharmacist role."""
    from app.core.auth.jwt import TokenClaims
    return TokenClaims(
        sub=str(uuid4()),
        email="pharmacist@hospital.example",
        role="PHARMACIST",
        exp=9999999999,
    )


@pytest.fixture
def mock_patient_claims():
    """Mock JWT claims for patient role."""
    from app.core.auth.jwt import TokenClaims
    return TokenClaims(
        sub=str(uuid4()),
        email="patient@example.com",
        role="PATIENT",
        exp=9999999999,
    )


# ── Test Cases ─────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_endpoint_returns_200_with_results(mock_pharmacist_claims, mock_encounter, mock_medications):
    """Test that endpoint returns 200 with properly structured reconciliation results."""
    with patch(
        "app.core.auth.jwt.get_current_user",
        return_value=mock_pharmacist_claims,
    ), patch(
        "app.core.auth.rbac.load_rbac_matrix",
        return_value={"PHARMACIST": {"medication": ["read"]}},
    ), patch(
        "app.db.audit.write_rbac_audit_entry",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.routers.medications.select",
    ) as mock_select, patch(
        "app.repositories.medication_repository.get_reconciliation_results",
        new_callable=AsyncMock,
        return_value=mock_medications,
    ), patch(
        "app.repositories.medication_repository.get_reconciliation_completed_at",
        new_callable=AsyncMock,
        return_value=datetime.now(timezone.utc),
    ), patch(
        "app.services.audit_service.write_audit_log",
        new_callable=AsyncMock,
    ):
        # Mock encounter query
        mock_stmt = AsyncMock()
        mock_select.return_value = mock_stmt
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_encounter
        
        response = client.get(
            f"/api/v1/encounters/{TEST_ENCOUNTER_ID}/medications/reconciliation",
            headers={"Authorization": f"Bearer {PHARMACIST_JWT}"},
        )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert "encounter_id" in data
    assert "total_medications" in data
    assert "reconciliation_completed_at" in data
    assert "medications" in data
    
    assert data["total_medications"] == 2
    assert len(data["medications"]) == 2
    
    # Validate first medication structure
    med = data["medications"][0]
    assert "id" in med
    assert "name" in med
    assert "reconciliation_category" in med
    assert "pre_admit" in med
    assert "inpatient" in med
    assert "discharge" in med
    assert "flags" in med


@pytest.mark.unit
def test_endpoint_returns_404_for_unknown_encounter(mock_pharmacist_claims):
    """Test that endpoint returns 404 when encounter does not exist."""
    with patch(
        "app.core.auth.jwt.get_current_user",
        return_value=mock_pharmacist_claims,
    ), patch(
        "app.core.auth.rbac.load_rbac_matrix",
        return_value={"PHARMACIST": {"medication": ["read"]}},
    ), patch(
        "app.db.audit.write_rbac_audit_entry",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.routers.medications.select",
    ) as mock_select:
        # Mock encounter query returning None
        mock_stmt = AsyncMock()
        mock_select.return_value = mock_stmt
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        
        response = client.get(
            f"/api/v1/encounters/{uuid4()}/medications/reconciliation",
            headers={"Authorization": f"Bearer {PHARMACIST_JWT}"},
        )
    
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Encounter not found"


@pytest.mark.unit
def test_endpoint_returns_202_for_pending_reconciliation(
    mock_pharmacist_claims, mock_encounter
):
    """Test that endpoint returns 202 when reconciliation has not completed."""
    with patch(
        "app.core.auth.jwt.get_current_user",
        return_value=mock_pharmacist_claims,
    ), patch(
        "app.core.auth.rbac.load_rbac_matrix",
        return_value={"PHARMACIST": {"medication": ["read"]}},
    ), patch(
        "app.db.audit.write_rbac_audit_entry",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.routers.medications.select",
    ) as mock_select, patch(
        "app.repositories.medication_repository.get_reconciliation_results",
        new_callable=AsyncMock,
        return_value=[],  # No medications yet
    ), patch(
        "app.repositories.medication_repository.get_reconciliation_completed_at",
        new_callable=AsyncMock,
        return_value=None,  # Not completed
    ):
        # Mock encounter query
        mock_stmt = AsyncMock()
        mock_select.return_value = mock_stmt
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_encounter
        
        response = client.get(
            f"/api/v1/encounters/{TEST_ENCOUNTER_ID}/medications/reconciliation",
            headers={"Authorization": f"Bearer {PHARMACIST_JWT}"},
        )
    
    assert response.status_code == 202, f"Expected 202, got {response.status_code}"
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Reconciliation in progress"


@pytest.mark.unit
def test_endpoint_returns_403_for_patient_role(mock_patient_claims):
    """Test that endpoint returns 403 for PATIENT role (insufficient permissions)."""
    with patch(
        "app.core.auth.jwt.get_current_user",
        return_value=mock_patient_claims,
    ), patch(
        "app.core.auth.rbac.load_rbac_matrix",
        return_value={"PATIENT": {}},  # No permissions
    ), patch(
        "app.db.audit.write_rbac_audit_entry",
        new_callable=AsyncMock,
    ):
        response = client.get(
            f"/api/v1/encounters/{TEST_ENCOUNTER_ID}/medications/reconciliation",
            headers={"Authorization": f"Bearer {PATIENT_JWT}"},
        )
    
    # PATIENT role is hardcoded to deny in RBAC
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Forbidden"


@pytest.mark.unit
def test_endpoint_requires_authentication():
    """Test that endpoint returns 401 when no JWT is provided."""
    response = client.get(
        f"/api/v1/encounters/{TEST_ENCOUNTER_ID}/medications/reconciliation",
    )
    
    # Should return 401 or 422 depending on auth middleware
    assert response.status_code in (401, 422, 403), (
        f"Expected 401/422/403 for missing auth, got {response.status_code}"
    )


@pytest.mark.unit
def test_endpoint_audit_log_written_on_success(
    mock_pharmacist_claims, mock_encounter, mock_medications
):
    """Test that HIPAA audit log is written on successful request."""
    with patch(
        "app.core.auth.jwt.get_current_user",
        return_value=mock_pharmacist_claims,
    ), patch(
        "app.core.auth.rbac.load_rbac_matrix",
        return_value={"PHARMACIST": {"medication": ["read"]}},
    ), patch(
        "app.db.audit.write_rbac_audit_entry",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.routers.medications.select",
    ) as mock_select, patch(
        "app.repositories.medication_repository.get_reconciliation_results",
        new_callable=AsyncMock,
        return_value=mock_medications,
    ), patch(
        "app.repositories.medication_repository.get_reconciliation_completed_at",
        new_callable=AsyncMock,
        return_value=datetime.now(timezone.utc),
    ), patch(
        "app.services.audit_service.write_audit_log",
        new_callable=AsyncMock,
    ) as mock_audit:
        # Mock encounter query
        mock_stmt = AsyncMock()
        mock_select.return_value = mock_stmt
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_encounter
        
        response = client.get(
            f"/api/v1/encounters/{TEST_ENCOUNTER_ID}/medications/reconciliation",
            headers={"Authorization": f"Bearer {PHARMACIST_JWT}"},
        )
    
    assert response.status_code == 200
    
    # Verify audit log was called
    mock_audit.assert_called_once()
    call_kwargs = mock_audit.call_args.kwargs
    assert call_kwargs["action"] == "READ_MEDICATION_RECONCILIATION"
    assert call_kwargs["resource_type"] == "Medication"


@pytest.mark.unit
def test_endpoint_response_schema_validation(
    mock_pharmacist_claims, mock_encounter, mock_medications
):
    """Test that response conforms to MedicationReconciliationResponse schema."""
    with patch(
        "app.core.auth.jwt.get_current_user",
        return_value=mock_pharmacist_claims,
    ), patch(
        "app.core.auth.rbac.load_rbac_matrix",
        return_value={"PHARMACIST": {"medication": ["read"]}},
    ), patch(
        "app.db.audit.write_rbac_audit_entry",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.routers.medications.select",
    ) as mock_select, patch(
        "app.repositories.medication_repository.get_reconciliation_results",
        new_callable=AsyncMock,
        return_value=mock_medications,
    ), patch(
        "app.repositories.medication_repository.get_reconciliation_completed_at",
        new_callable=AsyncMock,
        return_value=datetime.now(timezone.utc),
    ), patch(
        "app.services.audit_service.write_audit_log",
        new_callable=AsyncMock,
    ):
        # Mock encounter query
        mock_stmt = AsyncMock()
        mock_select.return_value = mock_stmt
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_encounter
        
        response = client.get(
            f"/api/v1/encounters/{TEST_ENCOUNTER_ID}/medications/reconciliation",
            headers={"Authorization": f"Bearer {PHARMACIST_JWT}"},
        )
    
    assert response.status_code == 200
    data = response.json()
    
    # Validate top-level schema
    from app.schemas.medication import MedicationReconciliationResponse
    validated = MedicationReconciliationResponse(**data)
    
    assert validated.total_medications >= 0
    assert len(validated.medications) == validated.total_medications
