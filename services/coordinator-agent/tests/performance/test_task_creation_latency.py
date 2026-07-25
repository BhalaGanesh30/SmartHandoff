"""Performance test: task creation p95 < 2 s under 50 concurrent ADT events.

Requires:
  - TEST_DATABASE_URL env var pointing to a PostgreSQL test database
  - ``agent_task`` table created via Alembic migrations

Run with:
    pytest tests/performance/ -v -s --timeout=120
"""
from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from app.coordinator.agent import TransitionCoordinatorAgent


def _make_admit_event() -> MagicMock:
    event = MagicMock()
    event.encounter_id = uuid.uuid4()
    event.event_type.value = "ADT^A01"
    event.event_timestamp = datetime.now(UTC)
    return event


@pytest.mark.asyncio
@pytest.mark.performance
async def test_task_creation_p95_under_2_seconds(async_db_session):
    """50 concurrent ADT^A01 events; p95 task creation latency must be <2 s."""
    coordinator = TransitionCoordinatorAgent(db_session=async_db_session)
    events = [_make_admit_event() for _ in range(50)]

    async def timed_process(event: MagicMock) -> float:
        start = time.monotonic()
        await coordinator.process_event(event)
        return time.monotonic() - start

    # Fire all 50 events concurrently
    latencies: list[float] = await asyncio.gather(
        *[timed_process(e) for e in events]
    )

    latencies_sorted = sorted(latencies)
    p95_index = int(len(latencies_sorted) * 0.95) - 1
    p95_latency = latencies_sorted[p95_index]
    p50_latency = statistics.median(latencies_sorted)

    print(f"\nTask creation latency (50 concurrent ADT events):")
    print(f"  p50: {p50_latency:.3f}s")
    print(f"  p95: {p95_latency:.3f}s")
    print(f"  max: {max(latencies_sorted):.3f}s")

    assert p95_latency < 2.0, (
        f"p95 task creation latency {p95_latency:.3f}s exceeds 2.0s SLA (FR-004)"
    )
