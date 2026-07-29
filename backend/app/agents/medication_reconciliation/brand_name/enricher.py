"""Brand name enrichment facade — cache-aside pattern for RxNav lookups.

For each drug in the medication list, this enricher:
  1. Checks the Redis cache (TTL=7 days).
  2. On miss, calls RxNav getDisplayTerms.
  3. Stores result in cache.
  4. Returns ``{"brand_name": str | None}`` per drug.

Design refs:
    US-033 Technical Notes — brand name cache, Redis TTL=7 days
    US-033 AC Scenario 2   — "Furosemide (Lasix) — a water pill to reduce fluid buildup"
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.agents.medication_reconciliation.brand_name.cache import BrandNameCache
from app.agents.medication_reconciliation.brand_name.rxnav_client import (
    RxNavBrandNameError,
    fetch_brand_name,
)

logger = logging.getLogger(__name__)


@dataclass
class BrandNameResult:
    """Brand name enrichment result for a single drug.

    Attributes:
        rxcui: RxNorm CUI of the drug.
        generic_name: Generic drug name (input).
        brand_name: Brand name if found (e.g. ``"Lasix"``), else ``None``.
    """

    rxcui: str
    generic_name: str
    brand_name: str | None


class BrandNameEnricher:
    """Cache-aside brand name enrichment using RxNav.

    Args:
        cache: ``BrandNameCache`` instance backed by Redis.
    """

    def __init__(self, cache: BrandNameCache) -> None:
        self._cache = cache

    async def enrich(self, rxcui: str, generic_name: str) -> BrandNameResult:
        """Return brand name for a drug, using cache or RxNav.

        Args:
            rxcui: RxNorm CUI string.
            generic_name: Generic drug name (used as fallback display label).

        Returns:
            ``BrandNameResult`` with ``brand_name`` populated if available.
        """
        cached = await self._cache.get(rxcui)
        if cached is not None:
            return BrandNameResult(
                rxcui=rxcui,
                generic_name=generic_name,
                brand_name=cached.get("brand_name"),
            )

        brand_name: str | None = None
        try:
            brand_name = await fetch_brand_name(rxcui)
        except RxNavBrandNameError as exc:
            logger.warning("Brand name lookup failed for rxcui=%s: %s", rxcui, exc)

        await self._cache.set(rxcui, {"brand_name": brand_name})
        return BrandNameResult(rxcui=rxcui, generic_name=generic_name, brand_name=brand_name)
