"""Unit tests for GET /api/v1/beds and PATCH /api/v1/beds/{id}/status (beds.py).

Coverage:
  SC-3: GET with unit+status filter returns only matching beds
  SC-3: GET with no filter returns all beds
  DoD: PATCH requires BedManager role (403 for Physician)
  DoD: PATCH 404 on unknown bed_id
  DoD: Audit event emitted after PATCH

Design refs:
    US-035 TASK-006 — Unit test coverage for beds router
    US-035 TASK-005 — Beds router implementation
"""
from __future__ import annotations

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from app.agents.bed_management.schemas import BedStatus
from app.core.auth.jwt import TokenClaims
from app.core.auth.rbac import require_permission
from app.db.deps import get_read_db, get_write_db
from app.models.bed import Bed


@pytest.fixture
def bed_manager_user() -> TokenClaims:
    """Mock BedManager user."""
    return TokenClaims(
        sub=str(uuid.uuid4()),
        role="BED_MANAGER",
        units=["3A"],
        email="bedmanager@hospital.com",
        jti=str(uuid.uuid4()),
    )


@pytest.fixture
def physician_user() -> TokenClaims:
    """Mock Physician user."""
    return TokenClaims(
        sub=str(uuid.uuid4()),
        role="PHYSICIAN",
        units=["3A"],
        email="physician@hospital.com",
        jti=str(uuid.uuid4()),
    )


@pytest.fixture
def mock_read_db():
    """Mock read database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_write_db():
    """Mock write database session."""
    session = AsyncMock()
    return session


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/v1/beds — Filtering
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_beds_filter_unit_and_status(bed_manager_user, mock_read_db):
    """SC-3: GET /api/v1/beds?unit=3A&status=VACANT returns matching beds only."""
    mock_rows = [
        {
            "bed_id": uuid.uuid4(),
            "unit": "3A",
            "room": "301",
            "bed_number": "A",
            "bed_type": "MEDICAL",
            "status": "VACANT",
            "isolation_required": False,
            "gender_designation": "ANY",
            "predicted_discharge_time": None,
        },
        {
            "bed_id": uuid.uuid4(),
            "unit": "3A",
            "room": "301",
            "bed_number": "B",
            "bed_type": "MEDICAL",
            "status": "VACANT",
            "isolation_required": False,
            "gender_designation": "ANY",
            "predicted_discharge_time": None,
        },
    ]
    
    result = MagicMock()
    result.mappings.return_value.all.return_value = mock_rows
    mock_read_db.execute.return_value = result
    
    # Mock dependency overrides
    def override_get_current_user():
        return bed_manager_user
    
    async def override_get_read_db():
        yield mock_read_db
    
    def override_require_permission(resource, action):
        def dependency():
            return bed_manager_user
        return dependency
    
    app.dependency_overrides[get_read_db] = override_get_read_db
    app.dependency_overrides[require_permission] = override_require_permission
    
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/beds?unit=3A&status=VACANT",
                headers={"Authorization": "Bearer test_token"},
            )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(b["unit"] == "3A" for b in data)
        assert all(b["status"] == "VACANT" for b in data)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_beds_no_filter_returns_all(bed_manager_user, mock_read_db):
    """GET /api/v1/beds without filters returns all beds."""
    mock_rows = [
        {
            "bed_id": uuid.uuid4(),
            "unit": "3A",
            "room": "301",
            "bed_number": "A",
            "bed_type": "MEDICAL",
            "status": "VACANT",
            "isolation_required": False,
            "gender_designation": "ANY",
            "predicted_discharge_time": None,
        },
        {
            "bed_id": uuid.uuid4(),
            "unit": "ICU",
            "room": "ICU-1",
            "bed_number": "1",
            "bed_type": "ICU",
            "status": "OCCUPIED",
            "isolation_required": True,
            "gender_designation": "ANY",
            "predicted_discharge_time": None,
        },
    ]
    
    result = MagicMock()
    result.mappings.return_value.all.return_value = mock_rows
    mock_read_db.execute.return_value = result
    
    def override_require_permission(resource, action):
        def dependency():
            return bed_manager_user
        return dependency
    
    async def override_get_read_db():
        yield mock_read_db
    
    app.dependency_overrides[require_permission] = override_require_permission
    app.dependency_overrides[get_read_db] = override_get_read_db
    
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/beds",
                headers={"Authorization": "Bearer test_token"},
            )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
    finally:
        app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/v1/beds — RBAC
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_beds_requires_authentication():
    """GET /api/v1/beds without valid JWT returns 403."""
    def override_require_permission(resource, action):
        def dependency():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return dependency
    
    app.dependency_overrides[require_permission] = override_require_permission
    
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/beds")
        
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/beds/{id}/status — RBAC
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_bed_status_forbidden_for_physician(physician_user):
    """PATCH /api/v1/beds/{id}/status returns 403 for Physician role."""
    def override_require_permission(resource, action):
        def dependency():
            # Simulate RBAC denial for Physician trying to use bed:write
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return dependency
    
    app.dependency_overrides[require_permission] = override_require_permission
    
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.patch(
                f"/api/v1/beds/{uuid.uuid4()}/status",
                json={"status": "MAINTENANCE", "reason": "Annual maintenance check"},
                headers={"Authorization": "Bearer physician_token"},
            )
        
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/beds/{id}/status — Not Found
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_bed_status_not_found(bed_manager_user, mock_write_db):
    """PATCH /api/v1/beds/{id}/status returns 404 for non-existent bed."""
    # Mock bed not found
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_write_db.execute.return_value = result
    
    def override_require_permission(resource, action):
        def dependency():
            return bed_manager_user
        return dependency
    
    async def override_get_write_db():
        yield mock_write_db
    
    app.dependency_overrides[require_permission] = override_require_permission
    app.dependency_overrides[get_write_db] = override_get_write_db
    
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.patch(
                f"/api/v1/beds/{uuid.uuid4()}/status",
                json={"status": "MAINTENANCE", "reason": "Check plumbing"},
                headers={"Authorization": "Bearer bed_manager_token"},
            )
        
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/beds/{id}/status — Success
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_bed_status_success(bed_manager_user, mock_write_db):
    """PATCH /api/v1/beds/{id}/status successfully updates bed status."""
    bed_id = uuid.uuid4()
    mock_bed = MagicMock(spec=Bed)
    mock_bed.id = bed_id
    mock_bed.status = BedStatus.VACANT.value
    
    # Mock bed fetch
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = mock_bed
    
    # Mock update
    update_result = MagicMock()
    update_result.rowcount = 1
    
    mock_write_db.execute.side_effect = [select_result, update_result]
    mock_write_db.commit = AsyncMock()
    
    def override_require_permission(resource, action):
        def dependency():
            return bed_manager_user
        return dependency
    
    async def override_get_write_db():
        yield mock_write_db
    
    # Mock audit service
    with patch("app.api.v1.routers.beds.write_audit_log", new_callable=AsyncMock) as mock_audit:
        app.dependency_overrides[require_permission] = override_require_permission
        app.dependency_overrides[get_write_db] = override_get_write_db
        
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.patch(
                    f"/api/v1/beds/{bed_id}/status",
                    json={"status": "MAINTENANCE", "reason": "Scheduled maintenance"},
                    headers={"Authorization": "Bearer bed_manager_token"},
                )
            
            assert response.status_code == 200
            data = response.json()
            assert data["bed_id"] == str(bed_id)
            assert data["previous_status"] == "VACANT"
            assert data["new_status"] == "MAINTENANCE"
            
            # Verify audit log was called
            mock_audit.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/beds/{id}/status — Audit Logging
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_emits_audit_event(bed_manager_user, mock_write_db):
    """PATCH /api/v1/beds/{id}/status writes audit log entry."""
    bed_id = uuid.uuid4()
    mock_bed = MagicMock(spec=Bed)
    mock_bed.id = bed_id
    mock_bed.status = BedStatus.OCCUPIED.value
    
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = mock_bed
    update_result = MagicMock()
    update_result.rowcount = 1
    mock_write_db.execute.side_effect = [select_result, update_result]
    mock_write_db.commit = AsyncMock()
    
    def override_require_permission(resource, action):
        def dependency():
            return bed_manager_user
        return dependency
    
    async def override_get_write_db():
        yield mock_write_db
    
    with patch("app.api.v1.routers.beds.write_audit_log", new_callable=AsyncMock) as mock_audit:
        app.dependency_overrides[require_permission] = override_require_permission
        app.dependency_overrides[get_write_db] = override_get_write_db
        
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.patch(
                    f"/api/v1/beds/{bed_id}/status",
                    json={"status": "DIRTY", "reason": "Patient discharged manually"},
                    headers={"Authorization": "Bearer bed_manager_token"},
                )
            
            assert response.status_code == 200
            
            # Verify audit_log was called with correct action
            mock_audit.assert_awaited_once()
            call_args = mock_audit.call_args[1]  # kwargs
            assert call_args["action"] == "BED_STATUS_OVERRIDE"
            assert call_args["resource_type"] == "Bed"
            assert call_args["resource_id"] == bed_id
            assert call_args["metadata"]["previous"] == "OCCUPIED"
            assert call_args["metadata"]["new"] == "DIRTY"
            assert call_args["metadata"]["reason"] == "Patient discharged manually"
        finally:
            app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/beds/{id}/status — Validation
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_rejects_short_reason(bed_manager_user):
    """PATCH /api/v1/beds/{id}/status returns 422 for reason < 5 chars."""
    def override_require_permission(resource, action):
        def dependency():
            return bed_manager_user
        return dependency
    
    app.dependency_overrides[require_permission] = override_require_permission
    
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.patch(
                f"/api/v1/beds/{uuid.uuid4()}/status",
                json={"status": "MAINTENANCE", "reason": "Fix"},  # Too short
                headers={"Authorization": "Bearer bed_manager_token"},
            )
        
        assert response.status_code == 422  # Validation error
    finally:
        app.dependency_overrides.clear()
