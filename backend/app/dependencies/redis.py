"""Redis client dependency for async operations (OTP, rate limiting, etc.)."""
from __future__ import annotations

import os
from functools import lru_cache

import redis.asyncio as aioredis


@lru_cache(maxsize=1)
def _get_redis_url() -> str:
    """Return REDIS_URL from environment.

    Raises:
        RuntimeError: If REDIS_URL is not set.
    """
    url = os.environ.get("REDIS_URL", "")
    if not url:
        raise RuntimeError(
            "REDIS_URL environment variable is not set. "
            "Mount the 'smarthandoff-redis-url-{env}' Secret Manager secret."
        )
    return url


_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency that provides an async Redis client.

    Returns:
        aioredis.Redis: Singleton async Redis client instance.

    The client is created once and reused across requests. Connection
    parameters are read from REDIS_URL environment variable.
    """
    global _redis_client

    if _redis_client is None:
        url = _get_redis_url()
        _redis_client = aioredis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=1,        # 1-second command timeout
            retry_on_timeout=False,  # fail fast
        )

    return _redis_client
