"""Unit tests for TokenBucketRateLimiter resilience patterns.

Tests cover:
  - Delay on 101st request within 60s
  - Token refill over time
  - Exponential backoff when bucket empty
  - Thread-safety of token consumption
  - Metrics incremented on rate limit

Design refs:
    US-018 AC Scenario 4 — Rate limiter enforces 100 req/min
    US-017 TASK-002 — Token bucket rate limiter
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.core.fhir.rate_limiter import TokenBucketRateLimiter
from app.core.fhir.metrics import RATE_LIMITED_TOTAL


# ── Basic Rate Limiting Tests ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_rate_limiter_allows_100_requests_immediately():
    """Rate limiter allows 100 requests without delay (full bucket)."""
    limiter = TokenBucketRateLimiter(capacity=100, refill_rate=1.67)

    start = time.monotonic()

    # Acquire 100 tokens
    for _ in range(100):
        await limiter.acquire()

    elapsed = time.monotonic() - start

    # Should complete in <0.1s (no delay)
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_rate_limiter_delays_101st_request():
    """AC Scenario 4: 101st request delayed until token refilled."""
    limiter = TokenBucketRateLimiter(capacity=100, refill_rate=1.67)

    # Consume all 100 tokens
    for _ in range(100):
        await limiter.acquire()

    # 101st request should delay
    start = time.monotonic()
    await limiter.acquire()
    elapsed = time.monotonic() - start

    # Should delay ~1s (exponential backoff first attempt)
    assert 0.9 < elapsed < 1.3


@pytest.mark.asyncio
async def test_token_refill_over_time():
    """Tokens refill at 1.67/second rate."""
    limiter = TokenBucketRateLimiter(capacity=100, refill_rate=1.67)

    # Consume all tokens
    for _ in range(100):
        await limiter.acquire()

    assert limiter.tokens < 1

    # Wait 1 second
    await asyncio.sleep(1.0)

    # Refill tokens (should have ~1.67 tokens now)
    await limiter._refill()

    assert 1.5 < limiter.tokens < 2.0


# ── Exponential Backoff Tests ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_exponential_backoff_on_empty_bucket():
    """Empty bucket triggers exponential backoff [1s, 2s, 4s]."""
    limiter = TokenBucketRateLimiter(capacity=10, refill_rate=1.0)  # 1 token per second

    # Consume all tokens
    for _ in range(10):
        await limiter.acquire()

    # Next acquire should backoff ~1s (first backoff attempt)
    start = time.monotonic()
    await limiter.acquire()
    elapsed = time.monotonic() - start

    # Should delay at least 0.9s (first backoff)
    assert elapsed >= 0.9


# ── Metrics Tests ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_rate_limited_metric_increments():
    """Rate limiter metric increments on backoff."""
    limiter = TokenBucketRateLimiter(capacity=5, refill_rate=1.0)

    initial_count = RATE_LIMITED_TOTAL._value.get()

    # Consume all tokens
    for _ in range(5):
        await limiter.acquire()

    # Next acquire triggers backoff
    await limiter.acquire()

    final_count = RATE_LIMITED_TOTAL._value.get()
    # Should increment by at least 1 (may be more due to multiple backoff attempts)
    assert final_count > initial_count


# ── Thread-Safety Tests ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_concurrent_acquire_thread_safe():
    """Concurrent acquire calls are thread-safe."""
    limiter = TokenBucketRateLimiter(capacity=50, refill_rate=10)

    acquired_count = 0

    async def acquire_token():
        nonlocal acquired_count
        await limiter.acquire()
        acquired_count += 1

    # Execute 50 concurrent acquires
    await asyncio.gather(*[acquire_token() for _ in range(50)])

    assert acquired_count == 50
    assert limiter.tokens < 1  # All tokens consumed
