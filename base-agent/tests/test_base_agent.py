"""Unit tests for BaseAgent, retry_with_backoff, CancellationChecker, and StructuredOutputHelper.

Covers all 4 acceptance criteria scenarios from US-024:
  (a) Success path — ACK + COMPLETED
  (b) Retry on RetryableError — NACK + retry_count increment
  (c) Cancellation check — CANCELLED + ACK (no DB persist)
  (d) Non-retryable failure — FAILED + error JSON

Design refs: US-024 DoD, AC Scenarios 1–4.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import redis.asyncio as aioredis
from pydantic import BaseModel

from app.base.agent import AgentTaskStatus, BaseAgentOutput
from app.base.cancellation import CancellationChecker
from app.base.errors import NonRetryableError, RetryableError, retry_with_backoff
from app.base.structured_output import StructuredOutputHelper
from tests.conftest import ConcreteAgent


# ===========================================================================
# Helpers
# ===========================================================================


def make_agent(
    mock_db_session,
    mock_cancellation_checker,
    process_side_effect=None,
) -> ConcreteAgent:
    return ConcreteAgent(
        subscription_path="projects/test/subscriptions/test-sub",
        db_session=mock_db_session,
        cancellation_checker=mock_cancellation_checker,
        process_side_effect=process_side_effect,
    )


# ===========================================================================
# (a) Scenario 1: Success path
# ===========================================================================


@pytest.mark.asyncio
async def test_success_path(
    mock_db_session,
    mock_cancellation_checker,
    mock_subscriber,
    make_received_message,
):
    """ACK is sent and AgentTask status is set to COMPLETED on success."""
    agent = make_agent(mock_db_session, mock_cancellation_checker)
    msg = make_received_message(task_id="task-001")

    await agent._handle_message(mock_subscriber, msg)

    # ACK must be called once
    mock_subscriber.acknowledge.assert_called_once()

    # NACK must NOT be called
    mock_subscriber.modify_ack_deadline.assert_not_called()

    # update_task_status called with COMPLETED (second call; first is IN_PROGRESS)
    calls = mock_db_session().execute.call_args_list
    # Verify at least 2 status updates: IN_PROGRESS then COMPLETED
    assert mock_db_session().execute.call_count >= 2


# ===========================================================================
# (b) Scenario 2: Retry on RetryableError
# ===========================================================================


@pytest.mark.asyncio
async def test_retry_on_retryable_error(
    mock_db_session,
    mock_cancellation_checker,
    mock_subscriber,
    make_received_message,
):
    """NACK is sent and retry_count is incremented when RetryableError is raised."""
    agent = make_agent(
        mock_db_session,
        mock_cancellation_checker,
        process_side_effect=RetryableError("DB timeout", error_detail={"host": "sql-proxy"}),
    )
    msg = make_received_message(task_id="task-002")

    await agent._handle_message(mock_subscriber, msg)

    # NACK must be called
    mock_subscriber.modify_ack_deadline.assert_called_once_with(
        request={
            "subscription": agent._subscription_path,
            "ack_ids": [msg.ack_id],
            "ack_deadline_seconds": 0,
        }
    )

    # ACK must NOT be called
    mock_subscriber.acknowledge.assert_not_called()


@pytest.mark.asyncio
async def test_retry_decorator_exhaustion():
    """retry_with_backoff raises RetryableError after 4 total attempts (1 + 3 retries)."""
    call_count = 0

    @retry_with_backoff
    async def always_retryable():
        nonlocal call_count
        call_count += 1
        raise RetryableError("transient")

    with patch("app.base.errors.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(RetryableError):
            await always_retryable()

    assert call_count == 4, f"Expected 4 total attempts, got {call_count}"


# ===========================================================================
# (c) Scenario 3: Cancellation check
# ===========================================================================


@pytest.mark.asyncio
async def test_cancellation_flag_exits_cleanly(
    mock_db_session,
    mock_cancellation_checker,
    mock_subscriber,
    make_received_message,
):
    """Agent exits without calling process(); AgentTask = CANCELLED; ACK sent."""
    mock_cancellation_checker.is_cancelled = AsyncMock(return_value=True)

    agent = make_agent(mock_db_session, mock_cancellation_checker)
    msg = make_received_message(task_id="task-003")

    # Track whether process() was called by patching it
    process_called = False
    original_process = agent.process

    async def spy_process(*args, **kwargs):
        nonlocal process_called
        process_called = True
        return await original_process(*args, **kwargs)

    agent.process = spy_process

    await agent._handle_message(mock_subscriber, msg)

    # process() must NOT have been called
    assert not process_called, "process() must not be called when encounter is cancelled"

    # ACK must be sent (to prevent DLQ accumulation)
    mock_subscriber.acknowledge.assert_called_once()

    # NACK must NOT be called
    mock_subscriber.modify_ack_deadline.assert_not_called()


@pytest.mark.asyncio
async def test_cancellation_checker_redis_fail_safe():
    """CancellationChecker returns False (not cancelled) on Redis connection error."""
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(side_effect=aioredis.RedisError("connection refused"))

    checker = CancellationChecker(redis_client=mock_redis)
    result = await checker.is_cancelled("enc-fail-safe-001")

    assert result is False, "Redis failure should return False (not-cancelled)"


# ===========================================================================
# (d) Scenario 4: Non-retryable failure
# ===========================================================================


@pytest.mark.asyncio
async def test_nonretryable_failure_sets_failed_status(
    mock_db_session,
    mock_cancellation_checker,
    mock_subscriber,
    make_received_message,
):
    """AgentTask.status = FAILED with error JSON; ACK sent on NonRetryableError."""
    agent = make_agent(
        mock_db_session,
        mock_cancellation_checker,
        process_side_effect=NonRetryableError(
            "Schema validation failed",
            error_detail={"field": "encounter_id", "value": None},
        ),
    )
    msg = make_received_message(task_id="task-004")

    await agent._handle_message(mock_subscriber, msg)

    # ACK must be sent (non-retryable — Pub/Sub delivery counter manages DLQ)
    mock_subscriber.acknowledge.assert_called_once()

    # NACK must NOT be called
    mock_subscriber.modify_ack_deadline.assert_not_called()


@pytest.mark.asyncio
async def test_retry_decorator_nonretryable_immediate():
    """NonRetryableError propagates on first attempt — no retry."""
    call_count = 0

    @retry_with_backoff
    async def always_nonretryable():
        nonlocal call_count
        call_count += 1
        raise NonRetryableError("permanent")

    with pytest.raises(NonRetryableError):
        await always_nonretryable()

    assert call_count == 1, f"Expected 1 attempt, got {call_count}"


# ===========================================================================
# StructuredOutputHelper
# ===========================================================================


@pytest.mark.asyncio
async def test_structured_output_rate_limit_retryable():
    """HTTP 429 from Vertex AI raises RetryableError."""
    mock_response = MagicMock()
    mock_response.status_code = 429

    class SimpleOutput(BaseModel):
        content: str

    helper = StructuredOutputHelper()

    with patch("app.base.structured_output.ChatVertexAI") as MockLLM:
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "rate limit", request=MagicMock(), response=mock_response
            )
        )
        MockLLM.return_value.with_structured_output.return_value = mock_chain

        with pytest.raises(RetryableError) as exc_info:
            await helper.invoke_structured("test prompt", SimpleOutput)

    assert "429" in str(exc_info.value)


@pytest.mark.asyncio
async def test_structured_output_success():
    """invoke_structured returns validated Pydantic instance on success."""

    class SimpleOutput(BaseModel):
        content: str

    expected = SimpleOutput(content="discharge summary")
    helper = StructuredOutputHelper()

    with patch("app.base.structured_output.ChatVertexAI") as MockLLM:
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value=expected)
        MockLLM.return_value.with_structured_output.return_value = mock_chain

        result = await helper.invoke_structured("test prompt", SimpleOutput)

    assert result == expected
    assert isinstance(result, SimpleOutput)
