"""Shared pytest fixtures for coordinator-agent tests.

Provides:
  - ``mock_adt_event``      — minimal valid ADTEvent factory
  - ``mock_db_session``     — AsyncMock session factory (unit tests)
  - ``async_db_session``    — real asyncpg session factory (performance tests)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


# ---------------------------------------------------------------------------
# ADTEvent factory
# ---------------------------------------------------------------------------


def _make_adt_event(event_type: str = "ADT^A01") -> MagicMock:
    """Return a minimal MagicMock that satisfies ADTEvent interface."""
    event = MagicMock()
    event.encounter_id = uuid.uuid4()
    event.event_type.value = event_type
    event.event_timestamp = datetime.now(UTC)
    return event


@pytest.fixture
def mock_adt_event():
    return _make_adt_event("ADT^A01")


@pytest.fixture
def mock_transfer_event():
    return _make_adt_event("ADT^A02")


# ---------------------------------------------------------------------------
# Mock DB session (unit tests — no real DB)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session():
    """Returns an async_sessionmaker-like callable yielding a mock session."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("fake-id",)] * 5  # 5 rows inserted
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return session_factory


# ---------------------------------------------------------------------------
# Real async DB session (performance tests — requires TEST_DATABASE_URL env)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def async_db_engine():
    import os
    db_url = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
    engine = create_async_engine(db_url, pool_size=20, max_overflow=30)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_db_session(async_db_engine):
    factory = async_sessionmaker(async_db_engine, class_=AsyncSession, expire_on_commit=False)
    return factory
