"""Brand name enrichment module for patient medication summaries.

Provides cache-backed RxNav brand name lookups with 7-day TTL to avoid
redundant API calls. Each medication in the patient summary is enriched with
its brand name (e.g., `Furosemide (Lasix)`) for better patient comprehension.

Design refs:
    US-033 AC Scenario 2    — "Furosemide (Lasix) — a water pill to reduce fluid buildup"
    US-033 Technical Notes  — Redis cache TTL=7 days for brand names
    design.md §4.1          — Redis (Cloud Memorystore); RxNav API
"""
from __future__ import annotations

from app.agents.medication_reconciliation.brand_name.cache import BrandNameCache
from app.agents.medication_reconciliation.brand_name.enricher import (
    BrandNameEnricher,
    BrandNameResult,
)
from app.agents.medication_reconciliation.brand_name.rxnav_client import (
    RxNavBrandNameError,
    fetch_brand_name,
)

__all__ = [
    "BrandNameCache",
    "BrandNameEnricher",
    "BrandNameResult",
    "RxNavBrandNameError",
    "fetch_brand_name",
]
