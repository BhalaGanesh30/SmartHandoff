"""SMART on FHIR discovery client.

Fetches the .well-known/smart-configuration document to discover OAuth endpoints.

Design refs:
    US-016 Technical Notes — SMART on FHIR well-known discovery
    epics.md EP-002        — OAuth 2.0 client credentials flow
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.fhir.exceptions import FHIRAuthenticationError

logger = logging.getLogger(__name__)


async def discover_smart_config(base_url: str) -> dict[str, Any]:
    """Fetch the SMART on FHIR configuration from the EHR's well-known endpoint.

    Args:
        base_url: The FHIR server base URL (e.g., "https://ehr.example.com/fhir")

    Returns:
        Dictionary containing the SMART configuration, including:
            - token_endpoint: OAuth 2.0 token endpoint URL
            - authorization_endpoint: OAuth 2.0 authorization endpoint (unused in client_credentials)
            - capabilities: List of SMART capabilities (e.g., "client-confidential-asymmetric")

    Raises:
        FHIRAuthenticationError: If the discovery endpoint is unreachable or returns invalid JSON

    Example:
        config = await discover_smart_config("https://ehr.example.com/fhir")
        token_endpoint = config["token_endpoint"]
    """
    discovery_url = f"{base_url.rstrip('/')}/.well-known/smart-configuration"
    logger.info("Fetching SMART configuration from %s", discovery_url)

    try:
        async with httpx.AsyncClient(verify=True, timeout=10.0) as client:
            response = await client.get(discovery_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.critical(
            "SMART discovery failed",
            extra={
                "event": "fhir_discovery_failure",
                "url": discovery_url,
                "error": str(exc),
            },
        )
        raise FHIRAuthenticationError(
            f"Failed to fetch SMART configuration from {discovery_url}",
            status_code=getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None,
            response_body=str(exc),
        ) from exc

    try:
        config = response.json()
    except ValueError as exc:
        logger.critical(
            "SMART discovery returned invalid JSON",
            extra={
                "event": "fhir_discovery_invalid_json",
                "url": discovery_url,
            },
        )
        raise FHIRAuthenticationError(
            f"SMART configuration at {discovery_url} returned invalid JSON"
        ) from exc

    # Validate required fields
    if "token_endpoint" not in config:
        logger.critical(
            "SMART configuration missing token_endpoint",
            extra={
                "event": "fhir_discovery_missing_token_endpoint",
                "url": discovery_url,
                "keys": list(config.keys()),
            },
        )
        raise FHIRAuthenticationError(
            f"SMART configuration at {discovery_url} missing 'token_endpoint' field"
        )

    logger.info(
        "SMART configuration fetched successfully",
        extra={
            "event": "fhir_discovery_success",
            "token_endpoint": config["token_endpoint"],
            "capabilities": config.get("capabilities", []),
        },
    )
    return config


def get_token_endpoint(smart_config: dict[str, Any]) -> str:
    """Extract the token endpoint URL from a SMART configuration document.

    Args:
        smart_config: SMART configuration dictionary returned by discover_smart_config()

    Returns:
        OAuth 2.0 token endpoint URL

    Raises:
        KeyError: If token_endpoint is not present in the configuration
    """
    return smart_config["token_endpoint"]
