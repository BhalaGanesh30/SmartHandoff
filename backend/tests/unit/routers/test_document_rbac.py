"""
RBAC unit tests for the document approve and reject endpoints.

Uses FastAPI TestClient with mocked DB session and JWT claims.
Validates Scenario 4: nurse JWT → 403 on approve; all roles can reject.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models.document import Document
from app.schemas.document_schemas import DocumentStatus
from app.core.auth.jwt import get_current_user, TokenClaims
from app.db.deps import get_write_db

DOCUMENT_ID = str(uuid4())


@pytest.fixture
def mock_physician_user() -> TokenClaims:
    """Create a mock physician user TokenClaims."""
    return TokenClaims(
        sub=str(uuid4()),
        role="PHYSICIAN",  # Uppercase to match RBAC matrix
        units=["3A", "ICU"],
        email="physician@hospital.com",
        jti=str(uuid4()),
    )


@pytest.fixture
def mock_nurse_user() -> TokenClaims:
    """Create a mock nurse user TokenClaims."""
    return TokenClaims(
        sub=str(uuid4()),
        role="NURSE",  # Uppercase to match RBAC matrix
        units=["3A"],
        email="nurse@hospital.com",
        jti=str(uuid4()),
    )


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_document() -> MagicMock:
    """Create a mock Document ORM object."""
    doc = MagicMock(spec=Document)
    doc.id = uuid4()
    doc.status = DocumentStatus.PENDING_REVIEW
    doc.metadata = {}
    doc.content = {"medications": "Aspirin 100mg"}
    return doc


class TestApproveEndpointRBAC:
    """Scenario 4: approve is restricted to physician role."""

    def test_physician_can_approve(
        self,
        mock_physician_user: TokenClaims,
        mock_db_session: AsyncMock,
    ) -> None:
        """Physician role can successfully call approve endpoint."""
        app.dependency_overrides[get_current_user] = lambda: mock_physician_user
        app.dependency_overrides[get_write_db] = lambda: mock_db_session
        
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.patch(
                f"/api/v1/documents/{DOCUMENT_ID}/approve",
                json={},
            )
        
        app.dependency_overrides.clear()
        
        # Physician can access the endpoint
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved"] is True

    def test_nurse_receives_403_on_approve(
        self,
        mock_nurse_user: TokenClaims,
    ) -> None:
        """Nurse role receives 403 Forbidden when attempting to approve."""
        app.dependency_overrides[get_current_user] = lambda: mock_nurse_user
        
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.patch(
                f"/api/v1/documents/{DOCUMENT_ID}/approve",
                json={},
            )
        
        app.dependency_overrides.clear()
        
        assert resp.status_code == 403
        detail = resp.json().get("detail", "").lower()
        assert "not authorised" in detail or "forbidden" in detail or "permission denied" in detail
