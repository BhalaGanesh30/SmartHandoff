"""FHIR R4 client with async resource fetch methods.

Design refs:
    US-017 AC Scenario 1 — Fetch methods return typed Pydantic models
    AIR-011              — Retry + circuit breaker
    AIR-013              — Rate limiting (100 req/min)
    AIR-012              — FHIR data not persisted (in-memory only)
    US-017 Technical Notes — Parse FHIR Bundle responses

IMPORTANT: FHIR data is NEVER persisted to SmartHandoff database.
All fetch methods return in-memory Pydantic models only.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
from fhir.resources.allergyintolerance import AllergyIntolerance
from fhir.resources.bundle import Bundle
from fhir.resources.condition import Condition
from fhir.resources.encounter import Encounter
from fhir.resources.medicationadministration import MedicationAdministration
from fhir.resources.medicationrequest import MedicationRequest
from fhir.resources.medicationstatement import MedicationStatement
from fhir.resources.patient import Patient

from app.core.config import get_settings
from app.core.fhir.auth import FHIRAuthClient
from app.core.fhir.circuit_breaker import circuit_breaker
from app.core.fhir.exceptions import (
    FHIRClientError,
    FHIRNetworkError,
    FHIRServerError,
)
from app.core.fhir.metrics import increment_retry_outcome, observe_fetch_duration
from app.core.fhir.models import (
    AllergyIntoleranceModel,
    ConditionModel,
    EncounterModel,
    MedicationAdministrationModel,
    MedicationRequestModel,
    MedicationStatementModel,
    PatientModel,
    PatientResolutionMethod,
)
from app.core.fhir.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


class FHIRClient:
    """FHIR R4 client for async resource fetching.

    This client provides typed async fetch methods for FHIR resources:
    - Patient, Encounter
    - MedicationStatement, MedicationAdministration, MedicationRequest
    - AllergyIntolerance, Condition

    Features:
    - OAuth 2.0 authentication via FHIRAuthClient (US-016)
    - Exponential backoff retry (3 attempts: 1s/2s/4s)
    - Circuit breaker (10 failures → open for 120s)
    - Rate limiting (100 req/min per instance)
    - Pydantic model validation (TASK-001)

    IMPORTANT: FHIR data returned in-memory only; never persisted to SmartHandoff DB.

    Usage:
        client = FHIRClient()
        patient = await client.get_patient_by_mrn("MRN-001")
        medications = await client.get_medication_statements(patient.id)
        await client.close()
    """

    def __init__(self) -> None:
        """Initialize FHIR client with auth, rate limiter, and circuit breaker."""
        self._settings = get_settings()
        self._auth_client = FHIRAuthClient()
        self._http_client = httpx.AsyncClient(
            verify=True,
            timeout=httpx.Timeout(30.0),  # 30s timeout for FHIR requests
            follow_redirects=True,
        )
        self._rate_limiter = TokenBucketRateLimiter(capacity=100, refill_rate=1.67)
        # Circuit breaker uses module-level singleton (shared across all instances)
        logger.info(
            "FHIRClient initialized",
            extra={
                "event": "fhir_client_init",
                "base_url": self._settings.FHIR_BASE_URL,
            },
        )

    @circuit_breaker
    async def _fetch_with_retry(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Fetch FHIR resource with exponential backoff retry.

        Retry policy:
        - 3 attempts total with delays: [1s, 2s, 4s]
        - Retry on: 5xx status codes, network timeouts, connection errors
        - NO retry on: 4xx status codes (client errors)

        Args:
            url: FHIR resource URL (absolute)
            params: Query parameters (optional)

        Returns:
            Parsed JSON response body

        Raises:
            FHIRClientError: On 4xx status (no retry)
            FHIRServerError: On 5xx status after exhausted retries
            FHIRNetworkError: On network failure after exhausted retries
            CircuitBreakerError: If circuit breaker is open

        Design refs:
            US-018 AC Scenario 1 — Retry succeeds after 503
            US-018 Technical Notes — Selective retry (no 4xx retry)
            AIR-011 — Exponential backoff: [1s, 2s, 4s]
        """
        max_attempts = 3
        backoff_delays = [1.0, 2.0, 4.0]
        
        # Get OAuth token
        token = await self._auth_client.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/fhir+json",
        }
        
        last_exception: Exception | None = None
        
        for attempt in range(max_attempts):
            try:
                start_time = time.monotonic()
                
                # Make HTTP request
                response = await self._http_client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=30.0,
                )
                
                # Record fetch duration
                duration = time.monotonic() - start_time
                resource_type = self._extract_resource_type(url)
                observe_fetch_duration(resource_type, duration)
                
                # ── Success (2xx/3xx) ────────────────────────────────────────
                if response.status_code < 400:
                    if attempt == 0:
                        increment_retry_outcome("no_retry_needed")
                    else:
                        increment_retry_outcome("success")
                        logger.info(
                            "FHIR fetch succeeded after retry",
                            extra={
                                "event": "fhir_retry_success",
                                "url": url,
                                "attempt": attempt + 1,
                                "status_code": response.status_code,
                            },
                        )
                    return response.json()
                
                # ── Client Error (4xx) — NO RETRY ─────────────────────────────
                elif 400 <= response.status_code < 500:
                    increment_retry_outcome("no_retry_needed")
                    logger.error(
                        "FHIR client error (no retry)",
                        extra={
                            "event": "fhir_client_error",
                            "url": url,
                            "status_code": response.status_code,
                            "response_body": response.text[:500],
                        },
                    )
                    raise FHIRClientError(
                        message=(
                            f"FHIR API client error: {response.status_code} "
                            f"{response.reason_phrase}"
                        ),
                        status_code=response.status_code,
                        url=url,
                        response_body=response.text,
                    )
                
                # ── Server Error (5xx) — RETRY ────────────────────────────────
                else:
                    last_exception = FHIRServerError(
                        message=(
                            f"FHIR API server error: {response.status_code} "
                            f"{response.reason_phrase}"
                        ),
                        status_code=response.status_code,
                        url=url,
                        attempts=attempt + 1,
                    )
                    
                    if attempt == max_attempts - 1:
                        # Exhausted retries
                        increment_retry_outcome("exhausted")
                        logger.error(
                            "FHIR fetch failed after exhausted retries",
                            extra={
                                "event": "fhir_retry_exhausted",
                                "url": url,
                                "attempts": max_attempts,
                                "status_code": response.status_code,
                            },
                        )
                        raise last_exception
                    
                    # Retry with backoff
                    delay = backoff_delays[attempt]
                    logger.warning(
                        "FHIR server error, retrying with backoff",
                        extra={
                            "event": "fhir_retry_attempt",
                            "url": url,
                            "attempt": attempt + 1,
                            "max_attempts": max_attempts,
                            "status_code": response.status_code,
                            "backoff_seconds": delay,
                        },
                    )
                    await asyncio.sleep(delay)
            
            except (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.NetworkError,
            ) as exc:
                # ── Network Error — RETRY ─────────────────────────────────────
                last_exception = FHIRNetworkError(
                    message=f"FHIR API network error: {type(exc).__name__}",
                    url=url,
                    attempts=attempt + 1,
                    original_error=exc,
                )
                
                if attempt == max_attempts - 1:
                    # Exhausted retries
                    increment_retry_outcome("exhausted")
                    logger.error(
                        "FHIR network error after exhausted retries",
                        extra={
                            "event": "fhir_retry_exhausted",
                            "url": url,
                            "attempts": max_attempts,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
                    raise last_exception from exc
                
                # Retry with backoff
                delay = backoff_delays[attempt]
                logger.warning(
                    "FHIR network error, retrying with backoff",
                    extra={
                        "event": "fhir_retry_attempt",
                        "url": url,
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                        "error_type": type(exc).__name__,
                        "backoff_seconds": delay,
                    },
                )
                await asyncio.sleep(delay)
        
        # Should never reach here (safety fallback)
        increment_retry_outcome("exhausted")
        raise last_exception or FHIRServerError(
            "FHIR fetch failed (unknown reason)", 500, url, max_attempts
        )
    
    @staticmethod
    def _extract_resource_type(url: str) -> str:
        """Extract FHIR resource type from URL for metrics.
        
        Examples:
            https://ehr.example.com/fhir/Patient/123 → Patient
            https://ehr.example.com/fhir/Encounter?patient=123 → Encounter
        """
        parts = url.rstrip("/").split("/")
        for i, part in enumerate(parts):
            if part in {
                "Patient",
                "Encounter",
                "MedicationStatement",
                "MedicationAdministration",
                "MedicationRequest",
                "AllergyIntolerance",
                "Condition",
            }:
                return part
        return "unknown"

    async def get_encounter_by_id(self, encounter_id: str) -> EncounterModel:
        """Fetch Encounter resource by ID.

        Args:
            encounter_id: FHIR Encounter resource ID

        Returns:
            EncounterModel with validated fields

        Raises:
            FHIRValidationError: If resource invalid
            httpx.HTTPError: If request fails after retries
            CircuitBreakerError: If circuit breaker open

        Note: FHIR data returned in-memory only; never persisted to SmartHandoff DB.
        """
        await self._rate_limiter.acquire()
        url = f"{self._settings.FHIR_BASE_URL}/Encounter/{encounter_id}"
        fhir_json = await self._fetch_with_retry(url)
        fhir_encounter = Encounter(**fhir_json)
        return EncounterModel.from_fhir(fhir_encounter)

    async def get_medication_statements(
        self, patient_id: str
    ) -> list[MedicationStatementModel]:
        """Fetch MedicationStatement resources for patient.

        Args:
            patient_id: FHIR Patient resource ID

        Returns:
            List of MedicationStatementModel (empty if none found)

        Note: FHIR data returned in-memory only; never persisted to SmartHandoff DB.
        """
        await self._rate_limiter.acquire()
        url = f"{self._settings.FHIR_BASE_URL}/MedicationStatement"
        params = {"patient": patient_id}
        fhir_json = await self._fetch_with_retry(url, params)

        # Parse Bundle
        bundle = Bundle(**fhir_json)
        results = []
        if bundle.entry:
            for entry in bundle.entry:
                if entry.resource and hasattr(entry.resource, '__resource_type__') and entry.resource.__resource_type__ == "MedicationStatement":
                    fhir_med_statement = MedicationStatement(**entry.resource.dict())
                    results.append(MedicationStatementModel.from_fhir(fhir_med_statement))

        logger.info(
            "Fetched MedicationStatements",
            extra={
                "event": "fhir_fetch_medication_statements",
                "patient_id": patient_id,
                "count": len(results),
            },
        )
        return results

    async def get_medication_administrations(
        self, encounter_id: str
    ) -> list[MedicationAdministrationModel]:
        """Fetch MedicationAdministration resources for encounter.

        Args:
            encounter_id: FHIR Encounter resource ID

        Returns:
            List of MedicationAdministrationModel (empty if none found)

        Note: FHIR data returned in-memory only; never persisted to SmartHandoff DB.
        """
        await self._rate_limiter.acquire()
        url = f"{self._settings.FHIR_BASE_URL}/MedicationAdministration"
        params = {"encounter": encounter_id}
        fhir_json = await self._fetch_with_retry(url, params)

        bundle = Bundle(**fhir_json)
        results = []
        if bundle.entry:
            for entry in bundle.entry:
                if (
                    entry.resource
                    and hasattr(entry.resource, '__resource_type__')
                    and entry.resource.__resource_type__ == "MedicationAdministration"
                ):
                    fhir_med_admin = MedicationAdministration(**entry.resource.dict())
                    results.append(MedicationAdministrationModel.from_fhir(fhir_med_admin))

        logger.info(
            "Fetched MedicationAdministrations",
            extra={
                "event": "fhir_fetch_medication_administrations",
                "encounter_id": encounter_id,
                "count": len(results),
            },
        )
        return results

    async def get_medication_requests(
        self, patient_id: str
    ) -> list[MedicationRequestModel]:
        """Fetch MedicationRequest resources for patient.

        Args:
            patient_id: FHIR Patient resource ID

        Returns:
            List of MedicationRequestModel (empty if none found)

        Note: FHIR data returned in-memory only; never persisted to SmartHandoff DB.
        """
        await self._rate_limiter.acquire()
        url = f"{self._settings.FHIR_BASE_URL}/MedicationRequest"
        params = {"patient": patient_id}
        fhir_json = await self._fetch_with_retry(url, params)

        bundle = Bundle(**fhir_json)
        results = []
        if bundle.entry:
            for entry in bundle.entry:
                if entry.resource and hasattr(entry.resource, '__resource_type__') and entry.resource.__resource_type__ == "MedicationRequest":
                    fhir_med_request = MedicationRequest(**entry.resource.dict())
                    results.append(MedicationRequestModel.from_fhir(fhir_med_request))

        logger.info(
            "Fetched MedicationRequests",
            extra={
                "event": "fhir_fetch_medication_requests",
                "patient_id": patient_id,
                "count": len(results),
            },
        )
        return results

    async def get_allergy_intolerances(
        self, patient_id: str
    ) -> list[AllergyIntoleranceModel]:
        """Fetch AllergyIntolerance resources for patient.

        Args:
            patient_id: FHIR Patient resource ID

        Returns:
            List of AllergyIntoleranceModel (empty if none found)

        Note: FHIR data returned in-memory only; never persisted to SmartHandoff DB.
        """
        await self._rate_limiter.acquire()
        url = f"{self._settings.FHIR_BASE_URL}/AllergyIntolerance"
        params = {"patient": patient_id}
        fhir_json = await self._fetch_with_retry(url, params)

        bundle = Bundle(**fhir_json)
        results = []
        if bundle.entry:
            for entry in bundle.entry:
                if entry.resource and hasattr(entry.resource, '__resource_type__') and entry.resource.__resource_type__ == "AllergyIntolerance":
                    fhir_allergy = AllergyIntolerance(**entry.resource.dict())
                    results.append(AllergyIntoleranceModel.from_fhir(fhir_allergy))

        logger.info(
            "Fetched AllergyIntolerances",
            extra={
                "event": "fhir_fetch_allergy_intolerances",
                "patient_id": patient_id,
                "count": len(results),
            },
        )
        return results

    async def get_conditions(self, patient_id: str) -> list[ConditionModel]:
        """Fetch Condition resources for patient.

        Args:
            patient_id: FHIR Patient resource ID

        Returns:
            List of ConditionModel (empty if none found)

        Note: FHIR data returned in-memory only; never persisted to SmartHandoff DB.
        """
        await self._rate_limiter.acquire()
        url = f"{self._settings.FHIR_BASE_URL}/Condition"
        params = {"patient": patient_id}
        fhir_json = await self._fetch_with_retry(url, params)

        bundle = Bundle(**fhir_json)
        results = []
        if bundle.entry:
            for entry in bundle.entry:
                if entry.resource and hasattr(entry.resource, '__resource_type__') and entry.resource.__resource_type__ == "Condition":
                    fhir_condition = Condition(**entry.resource.dict())
                    results.append(ConditionModel.from_fhir(fhir_condition))

        logger.info(
            "Fetched Conditions",
            extra={
                "event": "fhir_fetch_conditions",
                "patient_id": patient_id,
                "count": len(results),
            },
        )
        return results

    async def get_patient_by_mrn(
        self,
        mrn: str,
        fallback_name: str | None = None,
        fallback_dob: str | None = None,
    ) -> PatientModel | None:
        """Fetch Patient resource by MRN with name+DOB fallback.

        Resolution strategy (AIR-014):
        1. Search by MRN in Patient.identifier (primary method)
        2. If not found and fallback params provided: search by name + birthdate
        3. If still not found: log warning and return None

        Args:
            mrn: Medical Record Number (e.g., "MRN-001")
            fallback_name: Patient family name for fallback search (optional)
            fallback_dob: Patient birth date in YYYY-MM-DD format (optional)

        Returns:
            PatientModel with resolution_method and partial_match fields, or None if unresolved

        Raises:
            httpx.HTTPError: If request fails after retries
            CircuitBreakerError: If circuit breaker open

        Note: FHIR data returned in-memory only; never persisted to SmartHandoff DB.

        Example:
            # MRN search
            patient = await client.get_patient_by_mrn("MRN-001")

            # MRN with fallback
            patient = await client.get_patient_by_mrn(
                mrn="MRN-UNKNOWN",
                fallback_name="Smith",
                fallback_dob="1980-01-01"
            )
        """
        await self._rate_limiter.acquire()
        
        # Step 1: Try MRN search
        url = f"{self._settings.FHIR_BASE_URL}/Patient"
        # Construct identifier search: system|value
        # System typically: http://hospital.org/mrn (configurable in settings)
        mrn_system = self._settings.FHIR_MRN_SYSTEM
        params = {"identifier": f"{mrn_system}|{mrn}"}

        try:
            fhir_json = await self._fetch_with_retry(url, params)
            bundle = Bundle(**fhir_json)

            if bundle.entry and len(bundle.entry) > 0:
                # MRN match found
                fhir_patient = Patient(**bundle.entry[0].resource.dict())
                patient_model = PatientModel.from_fhir(fhir_patient)
                patient_model.resolution_method = PatientResolutionMethod.MRN
                patient_model.partial_match = False

                logger.info(
                    "Patient resolved by MRN",
                    extra={
                        "event": "patient_resolution_mrn",
                        "mrn": mrn,
                        "patient_id": patient_model.id,
                    },
                )
                return patient_model

        except Exception as exc:
            logger.warning(
                "MRN search failed — will try fallback if available",
                extra={
                    "event": "patient_resolution_mrn_failed",
                    "mrn": mrn,
                    "error": str(exc),
                },
            )

        # Step 2: MRN not found — try name+DOB fallback
        if fallback_name and fallback_dob:
            logger.info(
                "MRN not found — attempting name+DOB fallback",
                extra={
                    "event": "patient_resolution_fallback",
                    "mrn": mrn,
                    "fallback_name": fallback_name,
                    "fallback_dob": fallback_dob,
                },
            )

            params_fallback = {"family": fallback_name, "birthdate": fallback_dob}

            try:
                fhir_json_fallback = await self._fetch_with_retry(url, params_fallback)
                bundle_fallback = Bundle(**fhir_json_fallback)

                if bundle_fallback.entry and len(bundle_fallback.entry) > 0:
                    if len(bundle_fallback.entry) > 1:
                        # Multiple matches — log warning but use first result
                        logger.warning(
                            "Name+DOB fallback returned multiple matches — using first",
                            extra={
                                "event": "patient_resolution_multiple_matches",
                                "match_count": len(bundle_fallback.entry),
                            },
                        )

                    fhir_patient_fallback = Patient(**bundle_fallback.entry[0].resource.dict())
                    patient_model_fallback = PatientModel.from_fhir(fhir_patient_fallback)
                    patient_model_fallback.resolution_method = PatientResolutionMethod.NAME_DOB
                    patient_model_fallback.partial_match = True

                    logger.warning(
                        "Patient resolved by name+DOB fallback — partial match",
                        extra={
                            "event": "patient_resolution_name_dob",
                            "mrn": mrn,
                            "patient_id": patient_model_fallback.id,
                            "partial_match": True,
                        },
                    )
                    return patient_model_fallback

            except Exception as exc:
                logger.warning(
                    "Name+DOB fallback search failed",
                    extra={
                        "event": "patient_resolution_fallback_failed",
                        "error": str(exc),
                    },
                )

        # Step 3: Both resolution methods failed — return None
        logger.warning(
            "Patient unresolvable — both MRN and name+DOB searches failed",
            extra={
                "event": "patient_resolution_unresolvable",
                "mrn": mrn,
                "fallback_provided": bool(fallback_name and fallback_dob),
            },
        )
        return None

    async def close(self) -> None:
        """Close HTTP clients and release resources."""
        await self._http_client.aclose()
        await self._auth_client.close()
        logger.info("FHIRClient closed")
