"""Thread-safe in-memory token cache for SMART on FHIR access tokens.

Design refs:
    US-016 AC Scenario 2 — cached token reused without re-authentication
    US-016 AC Scenario 3 — token refreshed before 60-second expiry buffer
    US-016 DoD           — asyncio.Lock for thread-safety
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


@dataclass
class TokenCacheEntry:
    """A cached FHIR access token with expiry timestamp.

    Attributes:
        access_token: The OAuth 2.0 access token string
        expires_at: UTC timestamp when the token expires (with 60s buffer already applied)
    """

    access_token: str
    expires_at: datetime  # UTC, with 60s buffer already applied


class TokenCache:
    """Thread-safe in-memory cache for SMART on FHIR access tokens.

    This cache stores a single access token with its expiry timestamp.
    The expiry includes a 60-second safety buffer to prevent token expiry mid-request.

    Thread safety:
        All operations are protected by an asyncio.Lock to prevent race conditions
        when multiple concurrent agent tasks attempt to refresh the token.

    Example:
        cache = TokenCache()
        await cache.set_token("token_abc", expires_in=3600)
        token = await cache.get_token()  # Returns "token_abc" if not expired
        await cache.clear()  # Invalidate cached token
    """

    def __init__(self, expiry_buffer_seconds: int = 60) -> None:
        """Initialize an empty token cache.

        Args:
            expiry_buffer_seconds: Number of seconds before actual expiry to consider
                                   the token expired (default: 60s per US-016 AC)
        """
        self._cache: TokenCacheEntry | None = None
        self._lock = asyncio.Lock()
        self._expiry_buffer = timedelta(seconds=expiry_buffer_seconds)
        logger.info(
            "TokenCache initialized with %ds expiry buffer",
            expiry_buffer_seconds,
        )

    async def get_token(self) -> str | None:
        """Retrieve the cached access token if it exists and is not expired.

        Returns:
            The cached access token, or None if no token is cached or it has expired

        Thread-safety:
            This method is thread-safe (protected by asyncio.Lock)
        """
        async with self._lock:
            if self._cache is None:
                logger.debug("Token cache miss: no token cached")
                return None

            now = datetime.now(timezone.utc)
            if now >= self._cache.expires_at:
                remaining = (self._cache.expires_at - now).total_seconds()
                logger.info(
                    "Token cache miss: token expired",
                    extra={
                        "event": "token_cache_expired",
                        "remaining_seconds": remaining,
                    },
                )
                self._cache = None
                return None

            remaining = (self._cache.expires_at - now).total_seconds()
            logger.debug(
                "Token cache hit: %ds remaining until expiry",
                remaining,
            )
            return self._cache.access_token

    async def set_token(self, access_token: str, expires_in: int) -> None:
        """Store a new access token in the cache with expiry buffer applied.

        Args:
            access_token: The OAuth 2.0 access token string
            expires_in: Token lifetime in seconds (as returned by the auth server)

        The actual cache expiry will be set to (now + expires_in - buffer) to ensure
        the token is refreshed before it expires.

        Thread-safety:
            This method is thread-safe (protected by asyncio.Lock)
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            # Apply the 60-second buffer by subtracting it from the actual expiry
            expires_at = now + timedelta(seconds=expires_in) - self._expiry_buffer
            self._cache = TokenCacheEntry(
                access_token=access_token,
                expires_at=expires_at,
            )
            logger.info(
                "Token cached with %ds lifetime (buffer-adjusted)",
                expires_in - self._expiry_buffer.total_seconds(),
                extra={
                    "event": "token_cached",
                    "original_expires_in": expires_in,
                    "buffer_seconds": self._expiry_buffer.total_seconds(),
                    "effective_expires_in": expires_in - self._expiry_buffer.total_seconds(),
                },
            )

    async def clear(self) -> None:
        """Clear the cached token (invalidate the cache).

        This is called when authentication fails or when the cached token is rejected
        by the FHIR server (e.g., revoked token).

        Thread-safety:
            This method is thread-safe (protected by asyncio.Lock)
        """
        async with self._lock:
            if self._cache is not None:
                logger.info("Token cache cleared")
                self._cache = None

    async def is_expired(self) -> bool:
        """Check if the cached token is expired (within the buffer window).

        Returns:
            True if no token is cached or the token is expired, False otherwise

        Thread-safety:
            This method is thread-safe (protected by asyncio.Lock)
        """
        token = await self.get_token()
        return token is None
