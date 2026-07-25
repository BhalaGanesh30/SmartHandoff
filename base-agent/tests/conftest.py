"""Shared pytest fixtures for base-agent unit tests."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.base.agent import AgentTaskStatus, BaseAgent, BaseAgentOutput
from app.base.cancellation import CancellationChecker
from app.models.adt_event import ADTEvent


# ---------------------------------------------------------------------------
# Concrete agent for testing the abstract BaseAgent
# ---------------------------------------------------------------------------


class ConcreteAgent(BaseAgent):
    """Minimal concrete subclass of BaseAgent for unit testing."""

    def __init__(self, *args, process_side_effect=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._process_side_effect = process_side_effect

    async def process(self, event: ADTEvent) -> BaseAgentOutput:
        if self._process_side_effect is not None:
            raise self._process_side_effect
        return BaseAgentOutput()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session():
    """Async SQLAlchemy session factory mock."""
    session_mock = AsyncMock()
    session_mock.__aenter__ = AsyncMock(return_value=session_mock)
    session_mock.__aexit__ = AsyncMock(return_value=False)
    session_mock.begin = MagicMock(return_value=session_mock)
    session_mock.execute = AsyncMock()

    factory = MagicMock(return_value=session_mock)
    return factory


@pytest.fixture
def mock_cancellation_checker():
    """CancellationChecker mock (not cancelled by default)."""
    checker = AsyncMock(spec=CancellationChecker)
    checker.is_cancelled = AsyncMock(return_value=False)
    return checker


@pytest.fixture
def mock_subscriber():
    """google.cloud.pubsub_v1.SubscriberClient mock."""
    subscriber = MagicMock()
    subscriber.acknowledge = MagicMock()
    subscriber.modify_ack_deadline = MagicMock()
    return subscriber


@pytest.fixture
def sample_adt_event() -> ADTEvent:
    """Minimal ADTEvent fixture."""
    return ADTEvent(
        encounter_id="enc-test-0001",
        event_type="ADT^A01",
        patient_id="pat-0001",
        unit="ICU-3",
        timestamp="2026-07-16T08:00:00Z",
    )


@pytest.fixture
def make_received_message(sample_adt_event):
    """Factory for mock Pub/Sub ReceivedMessage."""

    def _make(task_id: str = "task-uuid-001"):
        msg = MagicMock()
        msg.ack_id = "ack-id-test-001"
        msg.message.data = sample_adt_event.model_dump_json().encode()
        msg.message.attributes = {"task_id": task_id}
        return msg

    return _make
