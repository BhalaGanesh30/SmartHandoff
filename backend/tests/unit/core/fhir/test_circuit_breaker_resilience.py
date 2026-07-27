"""Unit tests for CircuitBreaker resilience patterns.

Tests cover:
  - Circuit opens after 10 failures in 60s window
  - Circuit transitions to HALF_OPEN after 120s cooldown
  - Circuit closes after successful probe
  - Circuit reopens after failed probe
  - Failure window expiry resets count
  - Thread-safety of state transitions
  - Metrics updates on state changes

Design refs:
    US-018 AC Scenario 2 — Circuit opens after 10 failures
    US-018 AC Scenario 3 — Half-open probe after 120s
    US-018 TASK-001 — Module-level singleton
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from app.core.fhir.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
)
from app.core.fhir.metrics import CIRCUIT_STATE


@pytest.fixture
def circuit_breaker():
    """Create fresh circuit breaker instance for each test."""
    return CircuitBreaker(failure_threshold=10, timeout=120, window=60)


# ── State Transition Tests ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_circuit_opens_after_10_failures(circuit_breaker):
    """AC Scenario 2: Circuit opens after 10 consecutive failures in 60s."""

    async def failing_func():
        raise Exception("Simulated failure")

    # Trigger 10 consecutive failures
    for i in range(10):
        with pytest.raises(Exception, match="Simulated failure"):
            await circuit_breaker.call(failing_func)

    # Circuit should be OPEN
    assert circuit_breaker.state == CircuitBreakerState.OPEN
    assert circuit_breaker.failure_count == 10

    # Next call should raise CircuitBreakerError
    with pytest.raises(CircuitBreakerError, match="Circuit breaker OPEN"):
        await circuit_breaker.call(failing_func)


@pytest.mark.asyncio
async def test_circuit_half_open_after_120s_cooldown(circuit_breaker):
    """AC Scenario 3: Circuit transitions to HALF_OPEN after 120s cooldown."""
    # Manually open circuit
    circuit_breaker.state = CircuitBreakerState.OPEN
    circuit_breaker.opened_at = time.monotonic() - 121  # 121s ago (>120s)

    async def success_func():
        return "success"

    # Call should transition to HALF_OPEN and succeed
    result = await circuit_breaker.call(success_func)

    assert result == "success"
    assert circuit_breaker.state == CircuitBreakerState.CLOSED  # Probe succeeded → CLOSED


@pytest.mark.asyncio
async def test_circuit_closes_after_successful_probe(circuit_breaker):
    """Circuit closes after successful HALF_OPEN probe."""
    # Set state to HALF_OPEN
    circuit_breaker.state = CircuitBreakerState.HALF_OPEN
    circuit_breaker.failure_count = 10

    async def success_func():
        return "success"

    result = await circuit_breaker.call(success_func)

    assert result == "success"
    assert circuit_breaker.state == CircuitBreakerState.CLOSED
    assert circuit_breaker.failure_count == 0  # Reset on success


@pytest.mark.asyncio
async def test_circuit_reopens_after_failed_probe(circuit_breaker):
    """Circuit reopens after HALF_OPEN probe failure."""
    # Set state to HALF_OPEN
    circuit_breaker.state = CircuitBreakerState.HALF_OPEN
    circuit_breaker.opened_at = time.monotonic()

    async def failing_func():
        raise Exception("Probe failed")

    with pytest.raises(Exception, match="Probe failed"):
        await circuit_breaker.call(failing_func)

    assert circuit_breaker.state == CircuitBreakerState.OPEN  # Reopened


@pytest.mark.asyncio
async def test_failure_window_expiry_resets_count(circuit_breaker):
    """Failure count resets after 60s window expiry."""
    # Simulate failures 61s ago
    circuit_breaker.failure_count = 5
    circuit_breaker.last_failure_time = time.monotonic() - 61

    async def success_func():
        return "success"

    await circuit_breaker.call(success_func)

    # Failure count should be reset
    assert circuit_breaker.failure_count == 0
    assert circuit_breaker.last_failure_time is None


@pytest.mark.asyncio
async def test_circuit_open_rejects_requests_within_cooldown(circuit_breaker):
    """Requests rejected while circuit OPEN within 120s cooldown."""
    # Open circuit now
    circuit_breaker.state = CircuitBreakerState.OPEN
    circuit_breaker.opened_at = time.monotonic()

    async def any_func():
        return "should not execute"

    with pytest.raises(CircuitBreakerError, match="Circuit breaker OPEN"):
        await circuit_breaker.call(any_func)


# ── Metrics Tests ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_circuit_state_metric_updates(circuit_breaker):
    """Circuit state gauge updates on state transitions."""
    from app.core.fhir.metrics import set_circuit_state

    # Set to CLOSED first
    circuit_breaker.state = CircuitBreakerState.CLOSED
    set_circuit_state("CLOSED")
    assert CIRCUIT_STATE._value.get() == 0  # CLOSED

    # Open circuit
    circuit_breaker.state = CircuitBreakerState.OPEN
    set_circuit_state("OPEN")
    assert CIRCUIT_STATE._value.get() == 2  # OPEN

    # Half-open circuit
    circuit_breaker.state = CircuitBreakerState.HALF_OPEN
    set_circuit_state("HALF_OPEN")
    assert CIRCUIT_STATE._value.get() == 1  # HALF_OPEN

    # Close circuit
    circuit_breaker.state = CircuitBreakerState.CLOSED
    set_circuit_state("CLOSED")
    assert CIRCUIT_STATE._value.get() == 0  # CLOSED


# ── Thread-Safety Tests ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_concurrent_calls_thread_safe(circuit_breaker):
    """Concurrent calls to circuit breaker are thread-safe."""
    call_count = 0

    async def increment_func():
        nonlocal call_count
        await asyncio.sleep(0.01)  # Simulate async work
        call_count += 1
        return call_count

    # Execute 20 concurrent calls
    tasks = [circuit_breaker.call(increment_func) for _ in range(20)]
    results = await asyncio.gather(*tasks)

    assert call_count == 20
    assert len(results) == 20
    assert circuit_breaker.failure_count == 0  # All succeeded


# ── Edge Cases ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_exactly_10_failures_opens_circuit(circuit_breaker):
    """Circuit opens on exactly 10th failure, not 9th or 11th."""

    async def failing_func():
        raise Exception("Failure")

    # 9 failures
    for _ in range(9):
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_func)

    assert circuit_breaker.state == CircuitBreakerState.CLOSED  # Still closed

    # 10th failure
    with pytest.raises(Exception):
        await circuit_breaker.call(failing_func)

    assert circuit_breaker.state == CircuitBreakerState.OPEN  # Now open


@pytest.mark.asyncio
async def test_success_resets_failure_count_in_closed_state(circuit_breaker):
    """Success in CLOSED state resets failure count."""

    async def failing_func():
        raise Exception("Failure")

    async def success_func():
        return "success"

    # 5 failures
    for _ in range(5):
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_func)

    assert circuit_breaker.failure_count == 5

    # Success
    await circuit_breaker.call(success_func)

    assert circuit_breaker.failure_count == 0  # Reset


@pytest.mark.asyncio
async def test_circuit_breaker_initial_state():
    """Circuit breaker starts in CLOSED state."""
    breaker = CircuitBreaker()
    assert breaker.state == CircuitBreakerState.CLOSED
    assert breaker.failure_count == 0
    assert breaker.last_failure_time is None
