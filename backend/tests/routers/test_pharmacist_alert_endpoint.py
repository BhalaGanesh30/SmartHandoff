"""Unit tests for POST /api/v1/encounters/{id}/pharmacist-alerts endpoint — US-031."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.schemas.pharmacist_alert import PharmacistAlertCreate


@pytest.fixture
async def mock_db_session() -> AsyncMock:
    """Mock database session for testing."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_pharmacist_jwt() -> str:
    """Mock JWT token for PHARMACIST role."""
    return "Bearer mock-pharmacist-token"


@pytest.mark.asyncio
async def test_high_severity_alert_logs_immediate_priority() -> None:
    """HIGH severity alert → logged message with priority=IMMEDIATE."""
    encounter_id = uuid.uuid4()
    
    with patch("app.api.v1.routers.alerts.get_write_db") as mock_db_dep, \
         patch("app.api.v1.routers.alerts.require_permission") as mock_rbac, \
         patch("app.api.v1.routers.alerts.logger") as mock_logger:
        
        # Setup mocks
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_db_dep.return_value = mock_session
        
        mock_rbac.return_value = lambda: MagicMock(user_id="test-pharmacist")
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/alerts/encounters/{encounter_id}/pharmacist-alerts",
                json={
                    "severity": "HIGH",
                    "drug_pair": ["Warfarin", "Aspirin"],
                    "interaction_description": "Major bleeding risk.",
                    "source": "RXNAV",
                    "interaction_check_status": "COMPLETE",
                },
                headers={"Authorization": "Bearer mock-pharmacist-jwt"},
            )
    
    assert response.status_code == 201
    
    # Verify logger was called with IMMEDIATE priority
    assert mock_logger.info.called
    log_call_args = str(mock_logger.info.call_args)
    assert "IMMEDIATE" in log_call_args
    assert "HIGH" in log_call_args
    assert "PHARMACIST_ALERT" in log_call_args


@pytest.mark.asyncio
async def test_medium_severity_alert_logs_standard_priority() -> None:
    """MEDIUM severity alert → logged message with priority=STANDARD."""
    encounter_id = uuid.uuid4()
    
    with patch("app.api.v1.routers.alerts.get_write_db") as mock_db_dep, \
         patch("app.api.v1.routers.alerts.require_permission") as mock_rbac, \
         patch("app.api.v1.routers.alerts.logger") as mock_logger:
        
        # Setup mocks
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_db_dep.return_value = mock_session
        
        mock_rbac.return_value = lambda: MagicMock(user_id="test-pharmacist")
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/alerts/encounters/{encounter_id}/pharmacist-alerts",
                json={
                    "severity": "MEDIUM",
                    "drug_pair": ["Lisinopril", "Potassium"],
                    "interaction_description": "Monitor potassium levels.",
                    "source": "RXNAV",
                    "interaction_check_status": "COMPLETE",
                },
                headers={"Authorization": "Bearer mock-pharmacist-jwt"},
            )
    
    assert response.status_code == 201
    
    # Verify logger was called with STANDARD priority
    assert mock_logger.info.called
    log_call_args = str(mock_logger.info.call_args)
    assert "STANDARD" in log_call_args
    assert "MEDIUM" in log_call_args


@pytest.mark.asyncio
async def test_incomplete_status_alert_uses_standard_priority() -> None:
    """INCOMPLETE status (MEDIUM severity) → logged message with priority=STANDARD."""
    encounter_id = uuid.uuid4()
    
    with patch("app.api.v1.routers.alerts.get_write_db") as mock_db_dep, \
         patch("app.api.v1.routers.alerts.require_permission") as mock_rbac, \
         patch("app.api.v1.routers.alerts.logger") as mock_logger:
        
        # Setup mocks
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_db_dep.return_value = mock_session
        
        mock_rbac.return_value = lambda: MagicMock(user_id="test-pharmacist")
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/alerts/encounters/{encounter_id}/pharmacist-alerts",
                json={
                    "severity": "MEDIUM",
                    "interaction_description": "Interaction check unavailable — manual review required",
                    "source": "SYSTEM",
                    "interaction_check_status": "INCOMPLETE",
                },
                headers={"Authorization": "Bearer mock-pharmacist-jwt"},
            )
    
    assert response.status_code == 201
    
    # Verify logger was called with STANDARD priority and INCOMPLETE status
    assert mock_logger.info.called
    log_call_args = str(mock_logger.info.call_args)
    assert "STANDARD" in log_call_args
    assert "INCOMPLETE" in log_call_args


@pytest.mark.asyncio
async def test_alert_flush_called_before_logging() -> None:
    """Verify db.flush() is called before notification logging (ensures PK assignment)."""
    encounter_id = uuid.uuid4()
    
    flush_called_before_log = False
    
    async def mock_flush():
        nonlocal flush_called_before_log
        flush_called_before_log = True
    
    def mock_log_info(*args, **kwargs):
        # Logger should be called after flush
        assert flush_called_before_log, "db.flush() should be called before logger.info()"
    
    with patch("app.api.v1.routers.alerts.get_write_db") as mock_db_dep, \
         patch("app.api.v1.routers.alerts.require_permission") as mock_rbac, \
         patch("app.api.v1.routers.alerts.logger") as mock_logger:
        
        # Setup mocks
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock(side_effect=mock_flush)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_db_dep.return_value = mock_session
        
        mock_rbac.return_value = lambda: MagicMock(user_id="test-pharmacist")
        mock_logger.info.side_effect = mock_log_info
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/alerts/encounters/{encounter_id}/pharmacist-alerts",
                json={
                    "severity": "HIGH",
                    "drug_pair": ["Warfarin", "Aspirin"],
                    "interaction_description": "Major bleeding risk.",
                    "source": "RXNAV",
                    "interaction_check_status": "COMPLETE",
                },
                headers={"Authorization": "Bearer mock-pharmacist-jwt"},
            )
    
    assert response.status_code == 201
    assert flush_called_before_log
