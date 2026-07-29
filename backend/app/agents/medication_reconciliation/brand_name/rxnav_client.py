"""Async client for the RxNav brand name lookup endpoints.

Calls the RxNav related concepts endpoint to find brand name (BN) synonyms:
    GET https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/related.json?tty=BN

For generic-only drugs, the endpoint returns no BN concepts — this is expected
and handled gracefully by returning None.

Design refs:
    US-033 Definition of Done — Drug brand name lookup: RxNav getDisplayTerms API
    US-033 AC Scenario 2      — Furosemide (Lasix) — a water pill to reduce fluid buildup
    design.md §4.1            — httpx async client stack
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_RXNAV_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
_REQUEST_TIMEOUT_SECONDS = 8.0


class RxNavBrandNameError(Exception):
    """Raised when the RxNav brand name lookup fails or returns no result."""


async def fetch_brand_name(rxcui: str) -> str | None:
    """Fetch the preferred brand name synonym for a given RxNorm CUI.

    Calls ``GET /rxcui/{rxcui}/related.json?tty=BN`` and returns the first
    brand-name concept found, or ``None`` if no brand is available (generics).

    Args:
        rxcui: RxNorm CUI string.

    Returns:
        Brand name string (e.g. ``"Lasix"``), or ``None``.

    Raises:
        RxNavBrandNameError: On HTTP error or unexpected response structure.
    """
    url = f"{_RXNAV_BASE_URL}/rxcui/{rxcui}/related.json"
    params = {"tty": "BN"}
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RxNavBrandNameError(
            f"RxNav brand name HTTP {exc.response.status_code} for rxcui={rxcui}"
        ) from exc
    except httpx.RequestError as exc:
        raise RxNavBrandNameError(
            f"RxNav brand name request failed for rxcui={rxcui}: {exc}"
        ) from exc

    data = response.json()
    concept_groups = (
        data.get("relatedGroup", {})
        .get("conceptGroup", [])
    )
    for group in concept_groups:
        for concept in group.get("conceptProperties", []):
            name = concept.get("name")
            if name:
                logger.debug("RxNav brand name resolved: rxcui=%s brand=%s", rxcui, name)
                return name

    logger.debug("No brand name found for rxcui=%s (generic drug)", rxcui)
    return None
