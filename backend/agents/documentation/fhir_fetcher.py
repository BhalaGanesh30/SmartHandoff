"""
FHIR encounter data fetcher for the Documentation Agent.

Fetches Patient, Encounter, Condition, and MedicationStatement resources
for a given encounter ID and returns a PHI-minimised EncounterContext
dataclass safe for inclusion in LLM prompt templates.

Design refs:
    US-025 AC Scenario 3 — Fetch conditions (ICD-10), medications (RxNorm), encounter context
    US-025 AC Scenario 4 — PHI stripping at fetcher level
    TASK-002            — FHIREncounterFetcher implementation
    US-017              — FHIRClient async HTTP client
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from app.core.fhir.client import FHIRClient
from app.core.fhir.exceptions import FHIRClientError

logger = logging.getLogger(__name__)


@dataclass
class DiagnosisContext:
    """PHI-safe diagnosis extracted from FHIR Condition resource."""
    icd10_code: str
    description: str
    is_primary: bool = False


@dataclass
class MedicationContext:
    """PHI-safe medication extracted from FHIR MedicationStatement resource."""
    drug_name: str
    dose: str
    frequency: str
    route: str
    rxnorm_code: Optional[str] = None


@dataclass
class EncounterContext:
    """
    PHI-minimised encounter context for LLM prompt rendering.

    DELIBERATELY EXCLUDES: patient_name, date_of_birth, address,
    phone_number, ssn, mrn. These fields must never appear here.

    Includes: encounter_id, admission_reason, diagnoses (ICD-10),
    medications, encounter_type, discharge_disposition.

    Design refs:
        US-025 AC Scenario 4 — PHI stripping at fetcher level
        SEC-003            — No direct patient identifiers in agent context
    """
    encounter_id: str
    admission_reason: str
    encounter_type: str
    discharge_disposition: Optional[str]
    length_of_stay_days: Optional[int]
    diagnoses: List[DiagnosisContext] = field(default_factory=list)
    medications: List[MedicationContext] = field(default_factory=list)
    procedures_performed: List[str] = field(default_factory=list)


class FHIREncounterFetcher:
    """
    Fetches and transforms FHIR encounter data into a PHI-minimised
    EncounterContext safe for LLM prompt rendering.

    This class enforces PHI minimisation at the data layer by:
    1. Not including direct identifiers in returned context
    2. Not exposing patient PII to downstream consumers
    3. Returning only clinical facts needed for documentation

    Args:
        fhir_client: Async FHIR R4 HTTP client (injected; from US-017).

    Usage:
        fetcher = FHIREncounterFetcher(fhir_client)
        context = await fetcher.fetch("ENC-001")
        # context.patient_name raises AttributeError (field does not exist)
    """

    def __init__(self, fhir_client: FHIRClient) -> None:
        self._client = fhir_client

    async def fetch(self, encounter_id: str) -> EncounterContext:
        """
        Fetch Patient, Encounter, Condition, and MedicationStatement resources
        and return a PHI-minimised EncounterContext.

        Implementation note:
            The existing FHIRClient (US-017) uses patient-scoped methods:
            - get_conditions(patient_id) returns all patient conditions
            - get_medication_statements(patient_id) returns all patient medications

            We first fetch the encounter to extract patient_id, then use that
            to fetch patient-level conditions and medications.

        Args:
            encounter_id: FHIR Encounter resource ID

        Returns:
            EncounterContext with PHI-stripped clinical data

        Raises:
            FHIRClientError: If the Encounter resource does not exist or other FHIR errors
        """
        logger.info("Fetching FHIR encounter context", extra={"encounter_id": encounter_id})

        # Step 1: Fetch Encounter resource to get patient_id and encounter details
        encounter_resource = await self._client.get_encounter_by_id(encounter_id)

        # Step 2: Parallel fetch of Conditions and MedicationStatements using patient_id
        import asyncio
        patient_id = encounter_resource.patient_id

        conditions_task = asyncio.create_task(
            self._client.get_conditions(patient_id)
        )
        medications_task = asyncio.create_task(
            self._client.get_medication_statements(patient_id)
        )

        conditions = await conditions_task
        medications = await medications_task

        # Step 3: Extract encounter details (period, class, etc.)
        # Note: The current EncounterModel from US-017 has minimal fields
        # We'll extract what we can and use sensible defaults for missing data
        encounter_type = encounter_resource.class_code or "inpatient"
        length_of_stay = self._calculate_los(
            encounter_resource.period_start,
            encounter_resource.period_end
        )

        # Step 4: Transform to PHI-minimised context
        context = EncounterContext(
            encounter_id=encounter_id,
            admission_reason=self._extract_admission_reason(conditions),
            encounter_type=encounter_type,
            discharge_disposition=None,  # Not available in current EncounterModel
            length_of_stay_days=length_of_stay,
            diagnoses=self._map_conditions(conditions),
            medications=self._map_medications(medications),
            procedures_performed=[],  # Not available from current FHIRClient methods
        )

        logger.debug(
            "FHIR context fetched — PHI stripped",
            extra={
                "encounter_id": encounter_id,
                "diagnosis_count": len(context.diagnoses),
                "medication_count": len(context.medications),
            },
        )
        return context

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _extract_admission_reason(self, conditions: list) -> str:
        """Extract admission reason from conditions (use first primary diagnosis)."""
        # First, look for encounter-diagnosis category conditions
        for condition in conditions:
            if condition.category and "encounter-diagnosis" in condition.category:
                return condition.code_display or "Not specified"
        
        # Fallback: use first condition if available
        if conditions and len(conditions) > 0:
            return conditions[0].code_display or "Not specified"
        
        return "Not specified"

    def _calculate_los(
        self,
        period_start: Optional[datetime],
        period_end: Optional[datetime]
    ) -> Optional[int]:
        """Calculate length of stay in days from period start/end."""
        if not period_start or not period_end:
            return None
        try:
            delta = period_end - period_start
            return max(0, delta.days)
        except Exception as exc:
            logger.warning(
                "Could not calculate length of stay",
                extra={"error": str(exc)}
            )
            return None

    def _map_conditions(self, conditions: list) -> List[DiagnosisContext]:
        """Map ConditionModel list to DiagnosisContext list."""
        diagnoses: List[DiagnosisContext] = []
        primary_assigned = False

        for condition_model in conditions:
            # Extract ICD-10 code and description from ConditionModel
            # Use code_value for ICD-10 code, code_display for description
            icd10_code = condition_model.code_value or "Unknown"
            description = condition_model.code_display or "Unknown condition"

            # Check if this is an encounter-diagnosis (primary)
            is_primary = False
            if condition_model.category and "encounter-diagnosis" in condition_model.category:
                is_primary = not primary_assigned
                if is_primary:
                    primary_assigned = True

            diagnoses.append(
                DiagnosisContext(
                    icd10_code=icd10_code,
                    description=description,
                    is_primary=is_primary,
                )
            )

        return diagnoses

    def _map_medications(self, medications: list) -> List[MedicationContext]:
        """Map MedicationStatementModel list to MedicationContext list."""
        medication_contexts: List[MedicationContext] = []

        for med_model in medications:
            # Extract medication details from MedicationStatementModel
            drug_name = getattr(med_model, 'medication_display', 'Unknown')
            rxnorm_code = getattr(med_model, 'medication_code', None)
            dosage_text = getattr(med_model, 'dosage_text', None) or "As directed"

            # Parse dosage text to extract dose/frequency/route
            # For now, use simple defaults; could be enhanced with parsing logic
            medication_contexts.append(
                MedicationContext(
                    drug_name=drug_name,
                    dose=dosage_text,
                    frequency="As directed",  # Could parse from dosage_text
                    route="oral",  # Default; could be extracted if available
                    rxnorm_code=rxnorm_code,
                )
            )

        return medication_contexts
