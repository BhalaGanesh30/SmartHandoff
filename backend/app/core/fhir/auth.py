"""SMART on FHIR OAuth 2.0 authentication client with token caching.

Design refs:
    US-016 AC Scenario 1 — client_credentials OAuth flow
    US-016 AC Scenario 2 — cached token reused without re-auth
    US-016 AC Scenario 3 — token refreshed before 60s expiry
    US-016 AC Scenario 4 — 401 raises FHIRAuthenticationError with logging
    design.md §4.1       — httpx.AsyncClient for async HTTP
    TR-021               — zero hardcoded credentials (Secret Manager)
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.fhir.discovery import discover_smart_config, get_token_endpoint
from app.core.fhir.exceptions import FHIRAuthenticationError
from app.core.fhir.token_cache import TokenCache

logger = logging.getLogger(__name__)


class FHIRAuthClient:
    """SMART on FHIR OAuth 2.0 authentication client with automatic token refresh.

    This client handles:
    - SMART on FHIR discovery (.well-known/smart-configuration)
    - OAuth 2.0 client_credentials grant flow
    - In-memory token caching with 60-second expiry buffer
    - Thread-safe automatic token refresh

    Usage:
        client = FHIRAuthClient()
        token = await client.get_access_token()
        # Use token in Authorization: Bearer header for FHIR API calls

    Credentials:
        FHIR_BASE_URL, FHIR_CLIENT_ID, FHIR_CLIENT_SECRET are loaded from
        environment variables (mounted from GCP Secret Manager by Cloud Run).

    Thread-safety:
        Multiple concurrent calls to get_access_token() are safe; the TokenCache
        uses asyncio.Lock to prevent simultaneous token refresh.
    """

    def __init__(self) -> None:
        """Initialize the FHIR authentication client.

        Credentials are loaded from environment variables via get_settings().
        The token cache is initialized with a 60-second expiry buffer.
        """
        self._settings = get_settings()
        self._cache = TokenCache(expiry_buffer_seconds=60)
        self._http_client = httpx.AsyncClient(
            verify=True,  # Enforce TLS certificate validation
            timeout=httpx.Timeout(10.0),  # 10-second timeout for auth requests
            follow_redirects=True,
        )
        self._token_endpoint: str | None = None
        logger.info(
            "FHIRAuthClient initialized",
            extra={
                "event": "fhir_auth_client_init",
                "base_url": self._settings.FHIR_BASE_URL,
                "scope": self._settings.FHIR_SCOPE,
            },
        )

    async def _ensure_token_endpoint(self) -> str:
        """Lazy-load the OAuth token endpoint via SMART discovery.

        Returns:
            The OAuth 2.0 token endpoint URL

        Raises:
            FHIRAuthenticationError: If discovery fails

        Caches the token endpoint after the first successful discovery to avoid
        repeated network calls.
        """
        if self._token_endpoint is None:
            smart_config = await discover_smart_config(self._settings.FHIR_BASE_URL)
            self._token_endpoint = get_token_endpoint(smart_config)
            logger.info(
                "Token endpoint discovered",
                extra={
                    "event": "token_endpoint_discovered",
                    "token_endpoint": self._token_endpoint,
                },
            )
        return self._token_endpoint

    async def authenticate(self) -> dict[str, Any]:
        """Perform OAuth 2.0 client_credentials grant to obtain an access token.

        Returns:
            Token response dictionary containing:
                - access_token: The OAuth access token string
                - expires_in: Token lifetime in seconds
                - token_type: Token type (typically "Bearer")
                - scope: Granted scope (may differ from requested scope)

        Raises:
            FHIRAuthenticationError: If authentication fails (e.g., 401, 403, network error)

        This method is called internally by get_access_token() when the cache is empty
        or the cached token has expired. Applications should call get_access_token()
        instead of authenticate() directly.
        """
        token_endpoint = await self._ensure_token_endpoint()

        # Prepare OAuth 2.0 client_credentials grant request
        # Spec: https://datatracker.ietf.org/doc/html/rfc6749#section-4.4.2
        request_data = {
            "grant_type": "client_credentials",
            "client_id": self._settings.FHIR_CLIENT_ID,
            "client_secret": self._settings.FHIR_CLIENT_SECRET,
            "scope": self._settings.FHIR_SCOPE,
        }

        logger.info(
            "Authenticating with FHIR token endpoint",
            extra={
                "event": "fhir_auth_attempt",
                "token_endpoint": token_endpoint,
                "scope": self._settings.FHIR_SCOPE,
                # No client_id or client_secret logged (SEC-011)
            },
        )

        try:
            response = await self._http_client.post(
                token_endpoint,
                data=request_data,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Authentication failed (4xx or 5xx)
            status_code = exc.response.status_code
            response_body = exc.response.text[:500]  # Limit body to 500 chars
            logger.critical(
                "FHIR authentication failed",
                extra={
                    "event": "fhir_auth_failure",
                    "status_code": status_code,
                    "token_endpoint": token_endpoint,
                    # No response_body logged (may contain sensitive details)
                },
            )
            raise FHIRAuthenticationError(
                f"FHIR authentication failed with HTTP {status_code}",
                status_code=status_code,
                response_body=response_body,
            ) from exc
        except httpx.HTTPError as exc:
            # Network error (timeout, connection refused, etc.)
            logger.critical(
                "FHIR authentication network error",
                extra={
                    "event": "fhir_auth_network_error",
                    "error": str(exc),
                    "token_endpoint": token_endpoint,
                },
            )
            raise FHIRAuthenticationError(
                f"FHIR authentication network error: {exc}"
            ) from exc

        # Parse token response
        try:
            token_response = response.json()
        except ValueError as exc:
            logger.critical(
                "FHIR token endpoint returned invalid JSON",
                extra={
                    "event": "fhir_auth_invalid_json",
                    "token_endpoint": token_endpoint,
                },
            )
            raise FHIRAuthenticationError(
                "FHIR token endpoint returned invalid JSON"
            ) from exc

        # Validate required fields
        if "access_token" not in token_response:
            logger.critical(
                "FHIR token response missing access_token",
                extra={
                    "event": "fhir_auth_missing_token",
                    "keys": list(token_response.keys()),
                },
            )
            raise FHIRAuthenticationError(
                "FHIR token response missing 'access_token' field"
            )

        if "expires_in" not in token_response:
            logger.warning(
                "FHIR token response missing expires_in, defaulting to 3600s",
                extra={"event": "fhir_auth_missing_expires_in"},
            )
            token_response["expires_in"] = 3600  # Default to 1 hour

        logger.info(
            "FHIR authentication successful",
            extra={
                "event": "fhir_auth_success",
                "expires_in": token_response["expires_in"],
                "scope": token_response.get("scope", "N/A"),
            },
        )
        return token_response

    async def get_access_token(self) -> str:
        """Get a valid FHIR access token, using cache or refreshing if expired.

        Returns:
            A valid OAuth 2.0 access token string

        Raises:
            FHIRAuthenticationError: If authentication fails

        This is the primary method for obtaining FHIR access tokens. It automatically:
        1. Returns the cached token if valid (no network call)
        2. Refreshes the token if expired (within 60s buffer)
        3. Handles token caching and thread-safe refresh

        Thread-safety:
            Multiple concurrent calls are safe; the TokenCache uses asyncio.Lock
            to prevent simultaneous refresh requests.

        Example:
            token = await client.get_access_token()
            headers = {"Authorization": f"Bearer {token}"}
        """
        # Check cache first (no network call if token is valid)
        cached_token = await self._cache.get_token()
        if cached_token is not None:
            logger.debug("Using cached FHIR access token")
            return cached_token

        # Cache miss or expired — authenticate and cache new token
        logger.info("FHIR token cache miss, authenticating...")
        token_response = await self.authenticate()
        access_token = token_response["access_token"]
        expires_in = token_response["expires_in"]

        # Cache the new token (with 60s buffer applied)
        await self._cache.set_token(access_token, expires_in)
        return access_token

    async def invalidate_token(self) -> None:
        """Invalidate the cached token (force re-authentication on next request).

        This is called when:
        - The FHIR server rejects a cached token (e.g., revoked token)
        - The EHR administrator rotates credentials
        - Testing/debugging scenarios require a fresh token

        After calling this method, the next call to get_access_token() will
        perform a full OAuth authentication flow.
        """
        await self._cache.clear()
        logger.info("FHIR token cache invalidated")

    async def close(self) -> None:
        """Close the underlying HTTP client.

        This should be called when the FHIRAuthClient is no longer needed,
        typically during application shutdown.
        """
        await self._http_client.aclose()
        logger.info("FHIRAuthClient HTTP client closed")
