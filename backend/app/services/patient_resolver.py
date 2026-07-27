"""Patient identity resolution service with MRN and name+DOB fallback.

This service orchestrates patient identity resolution using a cascading strategy:
1. MRN primary lookup via FHIR Patient?identifier search
2. Name+DOB fallback via FHIR Patient?family+given+birthdate search  
3. Ambiguous/unresolvable error handling with care team alerts

Design refs:
    US-019 AC1-AC4 — MRN → name+DOB cascading resolution
    AIR-014        — Patient resolution with fallback strategy
    DR-024         — PHI completeness validation
"""
from __future__ import annotations

import logging
import warnings
from datetime import datetime
from typing import Optional

from app.core.config import get_settings
from app.core.fhir.client import FHIRClient
from app.core.fhir.exceptions import (
    FHIRClientError,
    FHIRNetworkError,
    FHIRServerError,
    PatientAmbiguousError,
    PatientNotFoundWarning,
)
from app.core.fhir.models import PatientModel, PatientResolutionMethod

logger = logging.getLogger(__name__)


class PatientResolver:
    """Resolves patient identity from FHIR using cascading lookup strategy.

    Resolution order:
    1. Primary: MRN identifier lookup
    2. Fallback: Family name + given name + DOB lookup
    3. Error handling: Ambiguous (>1 match) or Unresolvable (0 matches)

    All FHIR calls include:
    - Circuit breaker protection (US-018)
    - Exponential backoff retry (US-018)
    - Rate limiting (100 req/min per instance)

    Usage:
        resolver = PatientResolver()
        patient = await resolver.resolve_patient(
            mrn="MRN-789",
            name={"family": "Smith", "given": "John"},
            dob="1980-01-15",
            encounter_id="enc-001"
        )
    """

    def __init__(self, fhir_client: Optional[FHIRClient] = None):
        """Initialize resolver with FHIR client dependency.

        Args:
            fhir_client: FHIR client instance (injected for testing, or creates new instance)
        """
        self.fhir_client = fhir_client or FHIRClient()
        self._settings = get_settings()

    async def resolve_patient(
        self,
        mrn: str,
        name: dict[str, str],
        dob: str,
        encounter_id: Optional[str] = None,
    ) -> Optional[PatientModel]:
        """Resolve patient identity using MRN primary lookup with name+DOB fallback.

        Args:
            mrn: Medical Record Number
            name: Dict with 'family' and 'given' keys (e.g., {"family": "Smith", "given": "John"})
            dob: Date of birth in YYYY-MM-DD format (e.g., "1980-01-15")
            encounter_id: Optional encounter ID for logging context

        Returns:
            PatientModel if resolved, None if unresolvable

        Raises:
            PatientAmbiguousError: If multiple patients match fallback criteria
            FHIRClientError: If FHIR API returns 4xx error
            FHIRServerError: If FHIR API fails after retries
            FHIRNetworkError: If network failure after retries

        Example:
            >>> resolver = PatientResolver()
            >>> patient = await resolver.resolve_patient(
            ...     mrn="MRN-789",
            ...     name={"family": "Smith", "given": "John"},
            ...     dob="1980-01-15",
            ...     encounter_id="enc-001"
            ... )
            >>> print(patient.resolution_method)
            'MRN'
        """
        context = {"encounter_id": encounter_id, "mrn": mrn}

        # Step 1: Primary MRN lookup
        logger.info(
            f"Attempting MRN lookup for encounter {encounter_id}",
            extra={**context, "event": "patient_resolution_start"},
        )

        patient = await self._lookup_by_mrn(mrn)

        if patient:
            # Success: MRN resolved on first attempt
            patient.resolution_method = PatientResolutionMethod.MRN
            patient.partial_match = False
            logger.info(
                f"Patient resolved via MRN for encounter {encounter_id}",
                extra={
                    **context,
                    "event": "patient_resolved_mrn",
                    "patient_id": patient.id,
                },
            )
            return patient

        # Step 2: Fallback to name+DOB lookup
        logger.warning(
            f"MRN lookup failed for {mrn}, attempting name+DOB fallback",
            extra={**context, "event": "patient_resolution_fallback"},
        )

        patients = await self._lookup_by_name_dob(name, dob)

        # Step 3: Handle fallback results
        if len(patients) == 1:
            # Success: exactly one match
            patient = patients[0]
            patient.resolution_method = PatientResolutionMethod.NAME_DOB
            patient.partial_match = True
            logger.warning(
                f"Patient resolved via name+DOB fallback for encounter {encounter_id}",
                extra={
                    **context,
                    "event": "patient_resolved_fallback",
                    "patient_id": patient.id,
                    "fallback_criteria": {"family": name.get("family"), "dob": dob},
                },
            )
            return patient

        elif len(patients) > 1:
            # Ambiguous: multiple matches
            criteria = {
                "family": name.get("family"),
                "given": name.get("given"),
                "dob": dob,
                "match_count": len(patients),
            }
            logger.critical(
                f"Ambiguous patient match for encounter {encounter_id}: {len(patients)} patients found",
                extra={
                    **context,
                    **criteria,
                    "event": "patient_resolution_ambiguous",
                },
            )
            raise PatientAmbiguousError(match_count=len(patients), criteria=criteria)

        else:
            # Unresolvable: zero matches
            logger.critical(
                f"Unresolvable patient for encounter {encounter_id}: no matches found",
                extra={**context, "event": "patient_resolution_failed"},
            )
            warnings.warn(
                f"Patient not found for MRN {mrn} and name {name}",
                PatientNotFoundWarning,
            )
            return None

    async def _lookup_by_mrn(self, mrn: str) -> Optional[PatientModel]:
        """Execute FHIR Patient search by MRN identifier.

        Args:
            mrn: Medical Record Number

        Returns:
            PatientModel if exactly 1 match, None otherwise

        Raises:
            FHIRClientError: If FHIR API returns 4xx error
            FHIRServerError: If FHIR API fails after retries
            FHIRNetworkError: If network failure after retries
        """
        # Build URL and params for FHIR search
        url = f"{self._settings.FHIR_BASE_URL}/Patient"
        params = {"identifier": f"{self._settings.FHIR_MRN_SYSTEM}|{mrn}"}

        # Execute FHIR search (resilience wrappers applied by FHIRClient)
        try:
            bundle = await self.fhir_client._fetch_with_retry(url, params)
        except FHIRClientError as exc:
            # 4xx errors (e.g., 404) indicate patient not found - this is expected
            if exc.status_code == 404:
                logger.info(
                    f"Patient not found via MRN lookup (404)",
                    extra={"event": "mrn_lookup_not_found", "mrn": mrn},
                )
                return None
            # Other 4xx errors are unexpected
            logger.error(
                f"FHIR client error during MRN lookup",
                extra={
                    "event": "mrn_lookup_client_error",
                    "status_code": exc.status_code,
                    "mrn": mrn,
                },
            )
            raise

        # Parse FHIR Bundle response
        patients = self._parse_fhir_bundle(bundle)

        # Return patient only if exactly 1 match (0 or >1 triggers fallback)
        return patients[0] if len(patients) == 1 else None

    async def _lookup_by_name_dob(
        self, name: dict[str, str], dob: str
    ) -> list[PatientModel]:
        """Execute FHIR Patient search by family name, given name, and date of birth.

        Args:
            name: Dict with 'family' and 'given' keys
            dob: Date of birth in YYYY-MM-DD format

        Returns:
            List of PatientModel instances (may be empty, 1, or multiple)

        Raises:
            FHIRClientError: If FHIR API returns 4xx error
            FHIRServerError: If FHIR API fails after retries
            FHIRNetworkError: If network failure after retries
        """
        family = name.get("family", "")
        given = name.get("given", "")

        # Build URL and params for FHIR search
        url = f"{self._settings.FHIR_BASE_URL}/Patient"
        params = {
            "family": family,
            "given": given,
            "birthdate": dob,
        }

        # Execute FHIR search
        try:
            bundle = await self.fhir_client._fetch_with_retry(url, params)
        except FHIRClientError as exc:
            # 4xx errors (e.g., 404) indicate no patients found - this is expected
            if exc.status_code == 404:
                logger.info(
                    f"No patients found via name+DOB lookup (404)",
                    extra={
                        "event": "name_dob_lookup_not_found",
                        "family": family,
                        "dob": dob,
                    },
                )
                return []
            # Other 4xx errors are unexpected
            logger.error(
                f"FHIR client error during name+DOB lookup",
                extra={
                    "event": "name_dob_lookup_client_error",
                    "status_code": exc.status_code,
                    "family": family,
                    "dob": dob,
                },
            )
            raise

        # Parse FHIR Bundle response
        return self._parse_fhir_bundle(bundle)

    def _parse_fhir_bundle(self, bundle: dict) -> list[PatientModel]:
        """Parse FHIR Bundle response into PatientModel instances.

        Args:
            bundle: FHIR Bundle resource dict

        Returns:
            List of PatientModel instances

        Note:
            Malformed Patient resources are logged and skipped (not raised).
            This ensures partial results are returned even if some entries are invalid.
        """
        patients = []
        entries = bundle.get("entry", [])

        for entry in entries:
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Patient":
                try:
                    # Map FHIR resource to PatientModel using existing from_fhir method
                    from fhir.resources.patient import Patient as FHIRPatient

                    fhir_patient = FHIRPatient(**resource)
                    patient = PatientModel.from_fhir(fhir_patient)
                    patients.append(patient)
                except Exception as exc:
                    # Log and skip malformed resources
                    logger.error(
                        f"Failed to parse FHIR Patient resource: {exc}",
                        extra={
                            "event": "fhir_parse_error",
                            "resource_id": resource.get("id"),
                            "error": str(exc),
                        },
                    )
                    # Continue processing remaining entries

        return patients

    async def close(self):
        """Close the underlying FHIR client HTTP connection.

        Call this when done using the resolver to release resources.

        Example:
            resolver = PatientResolver()
            try:
                patient = await resolver.resolve_patient(...)
            finally:
                await resolver.close()
        """
        if hasattr(self.fhir_client, "close"):
            await self.fhir_client.close()
