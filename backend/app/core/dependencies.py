"""FastAPI dependency injection providers.

Provides singleton instances of external service clients (Redis, etc.)
for use in FastAPI route handlers via Depends().

Usage::
    from fastapi import Depends
    from app.core.dependencies import get_redis

    @app.get("/")
    async def handler(redis: Redis = Depends(get_redis)):
        await redis.get("key")
"""
from __future__ import annotations

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

# Module-level singleton for Redis client
_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """FastAPI dependency — returns the shared async Redis client.

    The Redis connection is created once and reused across all requests.
    Uses REDIS_URL from settings.

    Returns:
        Redis: Shared async Redis client instance.

    Raises:
        RuntimeError: If REDIS_URL is not configured.

    Example::
        @router.get("/interactions")
        async def get_interactions(redis: Redis = Depends(get_redis)):
            cached = await redis.get("key")
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection pool on application shutdown.

    Call this in FastAPI's on_shutdown event handler.

    Example::
        @app.on_event("shutdown")
        async def shutdown():
            await close_redis()
    """
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
