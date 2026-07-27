"""RxNorm CUI normalisation via NIH RxNav REST API.

US-030 TASK-003: Maps drug display names to canonical RxNorm Concept Unique
Identifiers (CUIs) using the public RxNav REST API maintained by the National
Library of Medicine.

Design refs:
    - US-030 TASK-003 — RxNorm Normalisation Service
    - https://lhncbc.nlm.nih.gov/RxNav/APIs/api-RxNorm.getApproximateTerm.html
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RxNormNormaliser:
    """Maps drug display names to RxNorm CUIs using the RxNav public API.

    Caches results in-memory for the lifetime of the agent run to avoid
    redundant API calls for the same drug appearing on multiple lists
    (pre-admit, inpatient, discharge).

    Usage::

        normaliser = RxNormNormaliser()
        cui = await normaliser.normalise("Metformin 500mg")
        # Returns: "6809" (RxNorm CUI for metformin)

        cuis = await normaliser.normalise_batch([
            "Atorvastatin 20mg",
            "Lisinopril 10mg",
        ])
        # Returns: {"Atorvastatin 20mg": "83367", "Lisinopril 10mg": "104376"}

    Attributes:
        _cache: In-process cache mapping lowercased drug names to CUIs.
                Key is drug_name.lower().strip(), value is CUI string or None.

    Design refs:
        US-030 TASK-003 — RxNorm Normalisation Service
    """

    def __init__(self) -> None:
        """Initialise RxNormNormaliser with empty cache."""
        self._cache: dict[str, str | None] = {}

    async def normalise(self, drug_name: str) -> str | None:
        """Look up RxNorm CUI for a single drug name.

        Args:
            drug_name: Display drug name from FHIR (e.g. "Metformin 500mg oral").

        Returns:
            RxNorm CUI string (e.g. "6809") if found, None if not found or error.

        Notes:
            - Cache is case-insensitive (lowercased key)
            - RxNav timeouts and errors return None without raising
            - If multiple CUIs match, returns the first (most specific)
        """
        cache_key = drug_name.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        cui = await self._fetch_cui(drug_name)
        self._cache[cache_key] = cui
        return cui

    async def normalise_batch(
        self, names: list[str]
    ) -> dict[str, str | None]:
        """Concurrently normalise a list of drug names.

        Args:
            names: List of display drug names from FHIR.

        Returns:
            Dictionary mapping each drug name to its CUI (or None).

        Notes:
            - All API calls execute concurrently (wall time ≈ single call)
            - Cache hits avoid redundant HTTP requests
            - Use asyncio.Semaphore(20) if batch size > 20 to avoid overwhelming RxNav
        """
        results = await asyncio.gather(
            *[self.normalise(name) for name in names], return_exceptions=False
        )
        return dict(zip(names, results))

    async def _fetch_cui(self, drug_name: str) -> str | None:
        """Fetch RxNorm CUI from RxNav REST API.

        Args:
            drug_name: Display drug name from FHIR.

        Returns:
            First matching RxNorm CUI string, or None if not found / error.

        RxNav API documentation:
            GET /REST/rxcui.json?name={drug}&search=1
            Response: {"idGroup": {"rxnormId": ["6809", ...]}}
        """
        # Import settings here to avoid circular dependency
        from app.core.config import get_settings
        settings = get_settings()

        try:
            async with httpx.AsyncClient(
                timeout=settings.RXNAV_TIMEOUT_SECONDS
            ) as client:
                response = await client.get(
                    f"{settings.RXNAV_BASE_URL}/rxcui.json",
                    params={"name": drug_name, "search": 1},
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract RxNorm IDs from response
                id_group = data.get("idGroup", {})
                rxnorm_ids = id_group.get("rxnormId", [])
                
                if rxnorm_ids:
                    # Return first (most specific) match
                    cui = str(rxnorm_ids[0])
                    logger.debug(
                        "RxNav lookup success: '%s' → CUI %s", drug_name, cui
                    )
                    return cui
                
                logger.debug("RxNav lookup: no CUI found for '%s'", drug_name)
                return None
                
        except httpx.TimeoutException:
            logger.warning(
                "RxNav timeout (%ds) for drug: %s",
                settings.RXNAV_TIMEOUT_SECONDS,
                drug_name,
            )
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "RxNav HTTP error for drug '%s': %s %s",
                drug_name,
                exc.response.status_code,
                exc.response.text,
            )
            return None
        except Exception as exc:
            logger.warning(
                "RxNav unexpected error for drug '%s': %s", drug_name, exc
            )
            return None
