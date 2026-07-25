"""CancellationChecker — Redis-backed cancellation flag query.

Checks whether a cancellation flag has been set for a given encounter by
querying the Redis key ``cancellation:{encounter_id}``.

The flag is written by the EP-001 cancellation event handlers
(ADT^A11 / ADT^A12 / ADT^A13) via Cloud Memorystore (US-015, US-001).

Key format:
    ``cancellation:{encounter_id}``
    TTL: 3600 seconds (set at write time by EP-001 handler)

Fail-safe behaviour:
    Redis connection errors return ``False`` (not-cancelled) to avoid
    falsely stopping valid clinical agent processing on transient Redis
    downtime. The error is logged as WARNING for observability.

Design refs:
    US-024  — cancellation check before DB persist (AC Scenario 3)
    US-015  — EP-001 A11/A12/A13 sets the Redis flag
    US-001  — Cloud Memorystore (Redis) provisioned for cancellation flags
"""
from __future__ import annotations

import logging

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_CANCELLATION_KEY_PREFIX = "cancellation"


class CancellationChecker:
    """Queries Redis for encounter cancellation flags.

    Args:
        redis_client: An async ``redis.asyncio.Redis`` client instance.
            Injected at construction for testability.

    Example::

        import redis.asyncio as aioredis

        redis_client = aioredis.from_url("redis://localhost:6379")
        checker = CancellationChecker(redis_client=redis_client)
        is_cancelled = await checker.is_cancelled("enc-uuid-1234")
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def is_cancelled(self, encounter_id: str) -> bool:
        """Return ``True`` if a cancellation flag exists for ``encounter_id``.

        Queries the Redis key ``cancellation:{encounter_id}``. Returns
        ``False`` on Redis connection errors (fail-safe — see module docstring).

        Args:
            encounter_id: UUID string of the encounter to check.

        Returns:
            ``True`` if ``cancellation:{encounter_id}`` key exists in Redis;
            ``False`` if absent or on connection error.
        """
        key = f"{_CANCELLATION_KEY_PREFIX}:{encounter_id}"
        try:
            result = await self._redis.exists(key)
            is_cancelled: bool = bool(result)
            if is_cancelled:
                logger.info(
                    "cancellation_flag_detected",
                    extra={"encounter_id": encounter_id, "redis_key": key},
                )
            return is_cancelled

        except aioredis.RedisError as exc:
            # Fail-safe: treat Redis unavailability as not-cancelled
            logger.warning(
                "cancellation_check_redis_error",
                extra={
                    "encounter_id": encounter_id,
                    "error": str(exc),
                    "action": "treating_as_not_cancelled",
                },
            )
            return False
