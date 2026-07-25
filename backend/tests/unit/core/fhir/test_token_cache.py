"""Unit tests for TokenCache with expiry buffer logic.

Tests:
- Cache miss (empty cache)
- Cache hit (valid token)
- Cache expiry (token expired within 60s buffer)
- Thread-safe concurrent access
- Cache clear
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.core.fhir.token_cache import TokenCache


@pytest.mark.asyncio
async def test_token_cache_miss_empty():
    """Test cache miss when cache is empty."""
    cache = TokenCache()
    token = await cache.get_token()
    assert token is None


@pytest.mark.asyncio
async def test_token_cache_hit():
    """Test cache hit with valid token."""
    cache = TokenCache(expiry_buffer_seconds=60)
    await cache.set_token("token_abc", expires_in=3600)

    token = await cache.get_token()
    assert token == "token_abc"


@pytest.mark.asyncio
async def test_token_cache_expiry_buffer():
    """Test that token within expiry buffer is considered expired."""
    cache = TokenCache(expiry_buffer_seconds=60)

    with freeze_time("2026-07-16 12:00:00"):
        # Set token with 50 seconds lifetime (less than 60s buffer)
        await cache.set_token("token_short", expires_in=50)

    with freeze_time("2026-07-16 12:00:01"):
        # Token should be considered expired (50s - 60s buffer = -10s effective lifetime)
        token = await cache.get_token()
        assert token is None


@pytest.mark.asyncio
async def test_token_cache_expiry_buffer_boundary():
    """Test token at exact expiry buffer boundary."""
    cache = TokenCache(expiry_buffer_seconds=60)

    with freeze_time("2026-07-16 12:00:00"):
        # Set token with 120 seconds lifetime (60s after buffer)
        await cache.set_token("token_boundary", expires_in=120)

        # Token should be valid immediately after setting
        token = await cache.get_token()
        assert token == "token_boundary"

    with freeze_time("2026-07-16 12:00:59"):
        # Token should still be valid (59 seconds elapsed, 1 second remaining after buffer)
        token = await cache.get_token()
        assert token == "token_boundary"

    with freeze_time("2026-07-16 12:01:00"):
        # Token should be expired (60 seconds elapsed, buffer exhausted)
        token = await cache.get_token()
        assert token is None


@pytest.mark.asyncio
async def test_token_cache_clear():
    """Test cache clear invalidates cached token."""
    cache = TokenCache()
    await cache.set_token("token_xyz", expires_in=3600)

    # Verify token is cached
    token = await cache.get_token()
    assert token == "token_xyz"

    # Clear cache
    await cache.clear()

    # Verify cache is empty
    token = await cache.get_token()
    assert token is None


@pytest.mark.asyncio
async def test_token_cache_is_expired():
    """Test is_expired() method."""
    cache = TokenCache()

    # Empty cache is expired
    assert await cache.is_expired()

    # Valid token is not expired
    await cache.set_token("token_valid", expires_in=3600)
    assert not await cache.is_expired()

    # Clear cache
    await cache.clear()
    assert await cache.is_expired()


@pytest.mark.asyncio
async def test_token_cache_concurrent_access():
    """Test thread-safe concurrent access to cache."""
    import asyncio

    cache = TokenCache()
    await cache.set_token("token_concurrent", expires_in=3600)

    # Simulate 10 concurrent get_token() calls
    tasks = [cache.get_token() for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # All calls should return the same cached token
    assert all(token == "token_concurrent" for token in results)


@pytest.mark.asyncio
async def test_token_cache_concurrent_set():
    """Test thread-safe concurrent set_token() calls (race condition)."""
    import asyncio

    cache = TokenCache()

    # Simulate 5 concurrent set_token() calls (race condition scenario)
    async def set_token_task(token_value: str) -> None:
        await cache.set_token(token_value, expires_in=3600)

    tasks = [set_token_task(f"token_{i}") for i in range(5)]
    await asyncio.gather(*tasks)

    # One of the tokens should "win" (exact value is non-deterministic due to race)
    token = await cache.get_token()
    assert token is not None
    assert token.startswith("token_")
