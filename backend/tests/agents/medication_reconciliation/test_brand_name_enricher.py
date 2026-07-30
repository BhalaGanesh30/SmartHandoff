"""Unit tests for BrandNameEnricher — US-033 AC Scenario 2.

Test matrix:
    - Cache miss → RxNav fetched; result stored in cache
    - Cache hit → RxNav NOT called
    - RxNav returns None (generic drug) → brand_name=None returned gracefully
    - RxNav raises RxNavBrandNameError → brand_name=None, no exception propagated
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.medication_reconciliation.brand_name.enricher import BrandNameEnricher


@pytest.fixture
def mock_cache():
    return AsyncMock()


@pytest.mark.asyncio
async def test_cache_miss_calls_rxnav_and_stores_result(mock_cache):
    """Cache miss triggers RxNav API call and stores result."""
    mock_cache.get.return_value = None  # cache miss
    with patch(
        "app.agents.medication_reconciliation.brand_name.enricher.fetch_brand_name",
        return_value="Lasix",
    ) as mock_fetch:
        enricher = BrandNameEnricher(cache=mock_cache)
        result = await enricher.enrich(rxcui="50166", generic_name="Furosemide")

    assert result.brand_name == "Lasix"
    mock_fetch.assert_awaited_once_with("50166")
    mock_cache.set.assert_awaited_once_with("50166", {"brand_name": "Lasix"})


@pytest.mark.asyncio
async def test_cache_hit_suppresses_rxnav_call(mock_cache):
    """Cache hit returns cached value without calling RxNav API."""
    mock_cache.get.return_value = {"brand_name": "Lasix"}  # cache hit
    with patch(
        "app.agents.medication_reconciliation.brand_name.enricher.fetch_brand_name"
    ) as mock_fetch:
        enricher = BrandNameEnricher(cache=mock_cache)
        result = await enricher.enrich(rxcui="50166", generic_name="Furosemide")

    assert result.brand_name == "Lasix"
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_generic_drug_no_brand_returns_none(mock_cache):
    """Generic drug with no brand name returns None gracefully."""
    mock_cache.get.return_value = None
    with patch(
        "app.agents.medication_reconciliation.brand_name.enricher.fetch_brand_name",
        return_value=None,  # generic — no brand name in RxNav
    ):
        enricher = BrandNameEnricher(cache=mock_cache)
        result = await enricher.enrich(rxcui="6809", generic_name="Metformin")

    assert result.brand_name is None


@pytest.mark.asyncio
async def test_rxnav_error_returns_none_gracefully(mock_cache):
    """RxNav API error returns None without propagating exception."""
    from app.agents.medication_reconciliation.brand_name.rxnav_client import (
        RxNavBrandNameError,
    )

    mock_cache.get.return_value = None
    with patch(
        "app.agents.medication_reconciliation.brand_name.enricher.fetch_brand_name",
        side_effect=RxNavBrandNameError("RxNav 503"),
    ):
        enricher = BrandNameEnricher(cache=mock_cache)
        result = await enricher.enrich(rxcui="50166", generic_name="Furosemide")

    assert result.brand_name is None  # graceful degradation — no exception propagated
