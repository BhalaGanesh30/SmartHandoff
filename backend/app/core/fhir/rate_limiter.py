"""Token bucket rate limiter for FHIR API calls.

Design refs:
    AIR-013 — 100 FHIR req/min per agent instance
    US-017 Technical Notes — Rate limiter as decorator
"""
from __future__ import annotations

import asyncio
import logging
import time
from functools import wraps
from typing import Callable

from app.core.fhir.metrics import increment_rate_limited

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Token bucket rate limiter for async functions.

    Attributes:
        capacity: Maximum number of tokens (requests) in bucket
        refill_rate: Tokens added per second
        tokens: Current number of available tokens
        last_refill: Timestamp of last token refill
    """

    def __init__(self, capacity: int = 100, refill_rate: float = 1.67) -> None:
        """Initialize token bucket.

        Args:
            capacity: Maximum bucket capacity (default: 100 requests)
            refill_rate: Tokens per second (default: 1.67 = 100/min)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from bucket (blocking if insufficient).

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Blocks until enough tokens are available, then consumes them.
        Uses exponential backoff if bucket empty.
        """
        async with self._lock:
            attempt = 0
            backoff_delays = [1, 2, 4]  # Exponential backoff

            while self.tokens < tokens:
                await self._refill()

                if self.tokens >= tokens:
                    break

                # Bucket empty — exponential backoff
                delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                increment_rate_limited()
                logger.warning(
                    "Rate limit reached, backing off",
                    extra={
                        "event": "rate_limit_backoff",
                        "attempt": attempt + 1,
                        "delay_seconds": delay,
                        "current_tokens": self.tokens,
                    },
                )
                await asyncio.sleep(delay)
                attempt += 1

            # Consume tokens
            self.tokens -= tokens


def rate_limited(limiter: TokenBucketRateLimiter) -> Callable:
    """Decorator to apply rate limiting to async functions.

    Args:
        limiter: TokenBucketRateLimiter instance

    Usage:
        limiter = TokenBucketRateLimiter(capacity=100, refill_rate=1.67)

        @rate_limited(limiter)
        async def fetch_fhir_resource(url: str):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await limiter.acquire()
            return await func(*args, **kwargs)

        return wrapper

    return decorator
