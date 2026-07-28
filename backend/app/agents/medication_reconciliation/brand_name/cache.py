"""Redis cache wrapper for RxNav drug brand name lookups.

Uses a per-CUI key with a 7-day TTL because brand names are stable and do not
change frequently. Avoids redundant RxNav API calls across patient summaries.

Design refs:
    US-033 Technical Notes  — Redis TTL=7 days for brand name cache
    US-033 AC Scenario 2    — brand name enrichment for every medication
    design.md §4.1          — Redis (Cloud Memorystore) caching tier
"""
from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_KEY_PREFIX = "drug-brand"
_CACHE_TTL_SECONDS = 604_800  # 7 days


def _build_key(rxcui: str) -> str:
    """Build a Redis key for a drug brand name lookup.

    Args:
        rxcui: RxNorm CUI string.

    Returns:
        Cache key string, e.g. ``drug-brand:12345``.
    """
    return f"{_KEY_PREFIX}:{rxcui}"


class BrandNameCache:
    """Async cache wrapper for drug brand name results.

    Args:
        redis: An initialised ``redis.asyncio.Redis`` client.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, rxcui: str) -> dict[str, Any] | None:
        """Return cached brand name payload for a CUI, or ``None`` on miss.

        Args:
            rxcui: RxNorm CUI string.

        Returns:
            Deserialized payload ``{"brand_name": str}``,
            or ``None`` on cache miss.
        """
        key = _build_key(rxcui)
        raw = await self._redis.get(key)
        if raw is None:
            logger.debug("Brand name cache miss: key=%s", key)
            return None
        logger.debug("Brand name cache hit: key=%s", key)
        return json.loads(raw)

    async def set(self, rxcui: str, data: dict[str, Any]) -> None:
        """Store brand name payload for a CUI with a 7-day TTL.

        Args:
            rxcui: RxNorm CUI string.
            data: Serialisable payload ``{"brand_name": str | None}``.
        """
        key = _build_key(rxcui)
        await self._redis.set(key, json.dumps(data), ex=_CACHE_TTL_SECONDS)
        logger.debug("Cached brand name: key=%s ttl=%ds", key, _CACHE_TTL_SECONDS)
