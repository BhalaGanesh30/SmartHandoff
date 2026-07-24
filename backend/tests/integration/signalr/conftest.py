"""Fixtures for SignalR integration tests.

Provides:
  - async_db_session: in-memory SQLite async session for integration tests.
  - recorded_broadcaster: a SignalRBroadcaster subclass that records calls + timestamps.
  - transition_service: TaskStatusTransitionService wired to recorded_broadcaster.
  
Design:
  Uses in-memory SQLite (like other integration tests) for fast, isolated testing
  without requiring external PostgreSQL setup.
"""
from __future__ import annotations

import asyncio
import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.services.task_status_service import TaskStatusTransitionService
from app.signalr.broadcaster import SignalRBroadcaster
from app.signalr.schemas import TaskUpdatedPayload

# 32-byte synthetic test key (base64url-encoded) — never used in production
_TEST_PHI_KEY = base64.urlsafe_b64encode(b"smarthandoff-test-key-0000000000").decode()
os.environ.setdefault("PHI_ENCRYPTION_KEY", _TEST_PHI_KEY)


# ---------------------------------------------------------------------------
# Recorded broadcaster — captures broadcast calls and timestamps
# ---------------------------------------------------------------------------

@dataclass
class BroadcastRecord:
    """Record of a single broadcast call with timestamp."""
    payload: TaskUpdatedPayload
    called_at: datetime


class RecordingBroadcaster(SignalRBroadcaster):
    """SignalRBroadcaster subclass that records calls instead of HTTP requests.

    Used in integration tests to measure latency without a live Azure SignalR Service.
    """

    def __init__(self) -> None:
        # Skip parent __init__ to avoid parsing a real connection string.
        self._records: list[BroadcastRecord] = []

    async def broadcast_task_updated(self, payload: TaskUpdatedPayload) -> None:  # type: ignore[override]
        """Record the broadcast call with timestamp instead of sending HTTP."""
        self._records.append(
            BroadcastRecord(payload=payload, called_at=datetime.now(timezone.utc))
        )

    @property
    def records(self) -> list[BroadcastRecord]:
        """Return all recorded broadcast calls."""
        return self._records

    async def aclose(self) -> None:
        """No-op for test broadcaster."""
        pass


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    """Function-scoped in-memory SQLite async engine with schema applied."""
    # Use simple in-memory database without shared cache
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test async DB session with transaction rollback for isolation."""
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def recorded_broadcaster() -> RecordingBroadcaster:
    """Fixture providing a recording broadcaster for tests."""
    return RecordingBroadcaster()


@pytest.fixture
def transition_service(recorded_broadcaster: RecordingBroadcaster) -> TaskStatusTransitionService:
    """Fixture providing TaskStatusTransitionService with recording broadcaster."""
    return TaskStatusTransitionService(recorded_broadcaster)
