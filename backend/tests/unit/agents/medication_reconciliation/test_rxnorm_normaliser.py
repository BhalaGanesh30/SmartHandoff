"""Unit tests for RxNormNormaliser.

US-030 TASK-006: Validates RxNorm API integration with caching behavior.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.medication_reconciliation.rxnorm import RxNormNormaliser


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_prevents_duplicate_http_call():
    """Test that cache prevents duplicate HTTP calls for same drug name."""
    normaliser = RxNormNormaliser()
    
    with patch.object(
        normaliser, "_fetch_cui", new_callable=AsyncMock, return_value="12345"
    ) as mock_fetch:
        # First call
        result1 = await normaliser.normalise("Metformin")
        # Second call with same name (different case)
        result2 = await normaliser.normalise("metformin")
        
        assert result1 == "12345"
        assert result2 == "12345"
        # HTTP client should only be called once due to cache
        assert mock_fetch.call_count == 1, (
            f"Expected 1 HTTP call, got {mock_fetch.call_count}. "
            "Cache did not prevent duplicate HTTP call."
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unknown_drug_returns_none():
    """Test that unknown drugs return None."""
    normaliser = RxNormNormaliser()
    
    with patch.object(
        normaliser, "_fetch_cui", new_callable=AsyncMock, return_value=None
    ):
        result = await normaliser.normalise("Fictionomycin 200mg")
        assert result is None, "Unknown drug should return None"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_timeout_returns_none():
    """Test that HTTP timeout returns None gracefully."""
    import httpx
    
    normaliser = RxNormNormaliser()
    
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value = mock_client
        
        result = await normaliser._fetch_cui("Atorvastatin")
        assert result is None, "Timeout should return None"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_network_error_returns_none():
    """Test that network errors return None gracefully."""
    import httpx
    
    normaliser = RxNormNormaliser()
    
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = httpx.NetworkError("Connection failed")
        mock_client_cls.return_value = mock_client
        
        result = await normaliser._fetch_cui("Warfarin")
        assert result is None, "Network error should return None"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_key_case_insensitive():
    """Test that cache keys are case-insensitive."""
    normaliser = RxNormNormaliser()
    
    with patch.object(
        normaliser, "_fetch_cui", new_callable=AsyncMock, return_value="860975"
    ) as mock_fetch:
        await normaliser.normalise("METFORMIN")
        await normaliser.normalise("metformin")
        await normaliser.normalise("Metformin")
        
        # All three should hit the same cache entry
        assert mock_fetch.call_count == 1, (
            f"Expected 1 HTTP call for case variations, got {mock_fetch.call_count}"
        )
