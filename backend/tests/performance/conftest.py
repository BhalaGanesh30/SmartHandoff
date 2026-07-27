"""Pytest configuration and fixtures for performance tests.

These fixtures provide staging environment dependencies for performance testing.
The staging environment must be pre-configured with:
- Vertex AI API enabled with quota for concurrent Gemini calls
- FHIR R4 server with seeded test encounters
- Cloud SQL database for document writes
- All required GCP credentials and API keys
"""
from __future__ import annotations

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agents.documentation.fhir_fetcher import FHIREncounterFetcher
from app.core.config import Settings
from app.core.fhir.client import FHIRClient
from app.db.repositories.document_repository import DocumentRepository


class StagingSettings:
    """Staging environment settings for performance tests.
    
    Environment variables required:
    - STAGING_GCP_PROJECT_ID: GCP project ID for Vertex AI
    - STAGING_GCP_REGION: GCP region (default: us-central1)
    - STAGING_FHIR_BASE_URL: FHIR R4 server base URL
    - STAGING_FHIR_CLIENT_ID: FHIR OAuth client ID
    - STAGING_FHIR_CLIENT_SECRET: FHIR OAuth client secret
    - STAGING_DATABASE_URL: PostgreSQL connection string for Cloud SQL
    """
    
    @property
    def GCP_PROJECT_ID(self) -> str:
        """GCP project ID for Vertex AI Gemini API."""
        value = os.environ.get("STAGING_GCP_PROJECT_ID", "")
        if not value:
            raise RuntimeError(
                "STAGING_GCP_PROJECT_ID environment variable is not set. "
                "Set it to your staging GCP project ID."
            )
        return value
    
    @property
    def GCP_REGION(self) -> str:
        """GCP region for Vertex AI endpoint."""
        return os.environ.get("STAGING_GCP_REGION", "us-central1")
    
    @property
    def FHIR_BASE_URL(self) -> str:
        """Staging FHIR R4 server base URL."""
        value = os.environ.get("STAGING_FHIR_BASE_URL", "")
        if not value:
            raise RuntimeError(
                "STAGING_FHIR_BASE_URL environment variable is not set. "
                "Set it to your staging FHIR server URL."
            )
        return value
    
    @property
    def FHIR_CLIENT_ID(self) -> str:
        """Staging FHIR OAuth client ID."""
        value = os.environ.get("STAGING_FHIR_CLIENT_ID", "")
        if not value:
            raise RuntimeError(
                "STAGING_FHIR_CLIENT_ID environment variable is not set."
            )
        return value
    
    @property
    def FHIR_CLIENT_SECRET(self) -> str:
        """Staging FHIR OAuth client secret."""
        value = os.environ.get("STAGING_FHIR_CLIENT_SECRET", "")
        if not value:
            raise RuntimeError(
                "STAGING_FHIR_CLIENT_SECRET environment variable is not set."
            )
        return value
    
    @property
    def DATABASE_URL(self) -> str:
        """Staging Cloud SQL PostgreSQL connection string."""
        value = os.environ.get("STAGING_DATABASE_URL", "")
        if not value:
            raise RuntimeError(
                "STAGING_DATABASE_URL environment variable is not set. "
                "Format: postgresql+asyncpg://user:pass@host/db"
            )
        return value


@pytest.fixture(scope="module")
def staging_settings():
    """Staging environment settings for performance tests."""
    return StagingSettings()


@pytest.fixture(scope="module")
def staging_fhir_client(staging_settings):
    """Real FHIR client connected to staging FHIR R4 server."""
    return FHIRClient(
        base_url=staging_settings.FHIR_BASE_URL,
        client_id=staging_settings.FHIR_CLIENT_ID,
        client_secret=staging_settings.FHIR_CLIENT_SECRET,
    )


@pytest.fixture(scope="module")
def staging_async_engine(staging_settings):
    """Async SQLAlchemy engine connected to staging Cloud SQL."""
    engine = create_async_engine(
        staging_settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    yield engine
    # Cleanup
    import asyncio
    asyncio.run(engine.dispose())


@pytest_asyncio.fixture
async def staging_db_session(staging_async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Async session for staging Cloud SQL database."""
    session_factory = async_sessionmaker(
        bind=staging_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture(scope="module")
def staging_doc_repository(staging_async_engine):
    """Document repository connected to staging Cloud SQL.
    
    For performance testing, we create a simplified repository wrapper
    that manages its own sessions and SignalR notifications.
    """
    from app.signalr import SignalRHub
    from unittest.mock import AsyncMock
    
    # Mock SignalR for performance tests (we don't need real-time notifications)
    mock_signalr = AsyncMock(spec=SignalRHub)
    mock_signalr.send_to_group = AsyncMock(return_value=None)
    
    session_factory = async_sessionmaker(
        bind=staging_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    class PerformanceDocumentRepository:
        """Wrapper around DocumentRepository for performance testing.
        
        This wrapper manages session lifecycle internally so the test doesn't need to.
        """
        
        def __init__(self, session_factory, signalr_hub):
            self._session_factory = session_factory
            self._signalr_hub = signalr_hub
        
        async def create_discharge_document(self, encounter_id: str, summary):
            """Create a discharge document using a fresh session."""
            async with self._session_factory() as session:
                repo = DocumentRepository(session, self._signalr_hub)
                result = await repo.create_discharge_document(encounter_id, summary)
                await session.commit()
                return result
    
    return PerformanceDocumentRepository(session_factory, mock_signalr)
