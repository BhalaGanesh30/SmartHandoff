"""FHIR medication list fetcher for three-way reconciliation.

This module provides the FHIRMedicationFetcher service which retrieves
medication lists from FHIR R4 for a given encounter and normalizes them
into RawMedicationEntry objects for downstream processing.
"""
import asyncio
import logging
from typing import Any

from app.core.fhir.client import FHIRClient
from app.models.medication import MedicationListSource
from app.agents.medication_reconciliation.models import RawMedicationEntry

logger = logging.getLogger(__name__)


class FHIRMedicationFetcher:
    """Fetches pre-admission, inpatient, and discharge medication lists from FHIR R4.
    
    This service queries three different FHIR resource types and normalizes
    them into a common RawMedicationEntry format:
    - Pre-admission: MedicationStatement (patient-reported medications)
    - Inpatient: MedicationAdministration (medications given during stay)
    - Discharge: MedicationRequest (prescribed discharge medications)
    
    Usage:
        fetcher = FHIRMedicationFetcher(fhir_client)
        results = await fetcher.fetch_all("encounter-123")
        pre_admit_meds = results[MedicationListSource.PRE_ADMIT]
    
    Design refs:
        US-030 TASK-002 — FHIR medication fetcher implementation
        US-017 — FHIR client infrastructure
    """

    def __init__(self, fhir_client: FHIRClient) -> None:
        """Initialize fetcher with FHIR client.
        
        Args:
            fhir_client: Configured FHIRClient instance for API calls
        """
        self._client = fhir_client

    async def fetch_all(
        self, encounter_id: str
    ) -> dict[MedicationListSource, list[RawMedicationEntry]]:
        """Concurrently fetch all three FHIR medication lists.
        
        Executes three FHIR searches in parallel using asyncio.gather for
        optimal performance (wall time ≈ single call time, not 3×).
        
        Args:
            encounter_id: FHIR Encounter resource ID
        
        Returns:
            Dictionary mapping each MedicationListSource to its medication list
        
        Example:
            {
                MedicationListSource.PRE_ADMIT: [RawMedicationEntry(...), ...],
                MedicationListSource.INPATIENT: [...],
                MedicationListSource.DISCHARGE: [...]
            }
        """
        pre_admit, inpatient, discharge = await asyncio.gather(
            self.fetch_pre_admit(encounter_id),
            self.fetch_inpatient(encounter_id),
            self.fetch_discharge(encounter_id),
        )
        
        logger.info(
            "Fetched all medication lists for encounter",
            extra={
                "event": "medication_fetch_complete",
                "encounter_id": encounter_id,
                "pre_admit_count": len(pre_admit),
                "inpatient_count": len(inpatient),
                "discharge_count": len(discharge),
            },
        )
        
        return {
            MedicationListSource.PRE_ADMIT: pre_admit,
            MedicationListSource.INPATIENT: inpatient,
            MedicationListSource.DISCHARGE: discharge,
        }

    async def fetch_pre_admit(self, encounter_id: str) -> list[RawMedicationEntry]:
        """Fetch MedicationStatement resources (pre-admission list).
        
        Queries: MedicationStatement?context={encounter_id}
        
        MedicationStatement represents medications the patient reports taking
        before admission (home medications).
        
        Args:
            encounter_id: FHIR Encounter resource ID
        
        Returns:
            List of RawMedicationEntry (empty if none found)
        """
        bundle = await self._client.search(
            "MedicationStatement", {"context": encounter_id}
        )
        entries = [
            self._parse_medication_statement(r)
            for r in self._extract_entries(bundle)
        ]
        
        logger.debug(
            "Fetched pre-admission medications",
            extra={
                "event": "fetch_pre_admit",
                "encounter_id": encounter_id,
                "count": len(entries),
            },
        )
        
        return entries

    async def fetch_inpatient(self, encounter_id: str) -> list[RawMedicationEntry]:
        """Fetch MedicationAdministration resources (inpatient list).
        
        Queries: MedicationAdministration?context={encounter_id}
        
        MedicationAdministration represents medications actually administered
        to the patient during the inpatient stay.
        
        Args:
            encounter_id: FHIR Encounter resource ID
        
        Returns:
            List of RawMedicationEntry (empty if none found)
        """
        bundle = await self._client.search(
            "MedicationAdministration", {"context": encounter_id}
        )
        entries = [
            self._parse_medication_administration(r)
            for r in self._extract_entries(bundle)
        ]
        
        logger.debug(
            "Fetched inpatient medications",
            extra={
                "event": "fetch_inpatient",
                "encounter_id": encounter_id,
                "count": len(entries),
            },
        )
        
        return entries

    async def fetch_discharge(self, encounter_id: str) -> list[RawMedicationEntry]:
        """Fetch MedicationRequest resources (discharge list).
        
        Queries: MedicationRequest?encounter={encounter_id}
        
        MedicationRequest represents medications prescribed at discharge.
        Note: Uses 'encounter' parameter (not 'context' like other resources).
        
        IMPORTANT: Does NOT filter by status — stopped/cancelled requests are
        preserved for reconciliation algorithm to detect documented stop orders.
        
        Args:
            encounter_id: FHIR Encounter resource ID
        
        Returns:
            List of RawMedicationEntry (empty if none found)
        """
        bundle = await self._client.search(
            "MedicationRequest",
            {"encounter": encounter_id},  # Note: 'encounter' not 'context'
        )
        entries = [
            self._parse_medication_request(r)
            for r in self._extract_entries(bundle)
        ]
        
        logger.debug(
            "Fetched discharge medications",
            extra={
                "event": "fetch_discharge",
                "encounter_id": encounter_id,
                "count": len(entries),
            },
        )
        
        return entries

    # ── Private parsers ───────────────────────────────────────────────

    def _parse_medication_statement(self, resource: dict) -> RawMedicationEntry:
        """Parse FHIR MedicationStatement to RawMedicationEntry.
        
        Extracts medication name, dose, route, frequency from FHIR dosage array.
        
        Args:
            resource: FHIR MedicationStatement resource as dict
        
        Returns:
            RawMedicationEntry with PRE_ADMIT source
        """
        return RawMedicationEntry(
            source=MedicationListSource.PRE_ADMIT,
            fhir_id=resource.get("id", ""),
            name=self._extract_med_name(resource),
            dose_string=self._extract_dose_string(resource.get("dosage", [])),
            route=self._extract_route(resource.get("dosage", [])),
            frequency=self._extract_frequency(resource.get("dosage", [])),
            status=resource.get("status"),
        )

    def _parse_medication_administration(self, resource: dict) -> RawMedicationEntry:
        """Parse FHIR MedicationAdministration to RawMedicationEntry.
        
        IMPORTANT: MedicationAdministration.dosage is a single object (not array).
        We wrap it in a list before passing to shared extractors.
        
        Args:
            resource: FHIR MedicationAdministration resource as dict
        
        Returns:
            RawMedicationEntry with INPATIENT source
        """
        # Wrap single dosage object in list for consistent extractor interface
        dosage = [resource.get("dosage", {})]
        
        return RawMedicationEntry(
            source=MedicationListSource.INPATIENT,
            fhir_id=resource.get("id", ""),
            name=self._extract_med_name(resource),
            dose_string=self._extract_dose_string(dosage),
            route=self._extract_route(dosage),
            status=resource.get("status"),
        )

    def _parse_medication_request(self, resource: dict) -> RawMedicationEntry:
        """Parse FHIR MedicationRequest to RawMedicationEntry.
        
        MedicationRequest uses 'dosageInstruction' field (not 'dosage').
        
        Args:
            resource: FHIR MedicationRequest resource as dict
        
        Returns:
            RawMedicationEntry with DISCHARGE source
        """
        return RawMedicationEntry(
            source=MedicationListSource.DISCHARGE,
            fhir_id=resource.get("id", ""),
            name=self._extract_med_name(resource),
            dose_string=self._extract_dose_string(
                resource.get("dosageInstruction", [])
            ),
            route=self._extract_route(resource.get("dosageInstruction", [])),
            frequency=self._extract_frequency(
                resource.get("dosageInstruction", [])
            ),
            status=resource.get("status"),
        )

    def _extract_med_name(self, resource: dict) -> str:
        """Extract display name from medicationCodeableConcept or medicationReference.
        
        Fallback chain:
        1. medicationCodeableConcept.text
        2. medicationCodeableConcept.coding[0].display
        3. medicationReference.display
        4. "Unknown"
        
        Args:
            resource: FHIR medication resource
        
        Returns:
            Human-readable medication name
        """
        # Try medicationCodeableConcept.text
        concept = resource.get("medicationCodeableConcept", {})
        if text := concept.get("text"):
            return text
        
        # Try medicationCodeableConcept.coding[0].display
        codings = concept.get("coding", [])
        if codings:
            return codings[0].get("display", "Unknown")
        
        # Try medicationReference.display
        ref = resource.get("medicationReference", {})
        return ref.get("display", "Unknown")

    def _extract_dose_string(self, dosage_list: list[dict]) -> str | None:
        """Extract first dose quantity text from dosage instructions.
        
        Parses FHIR doseAndRate[0].doseQuantity structure to extract
        numeric value and unit (e.g. "500 mg").
        
        Args:
            dosage_list: Array of FHIR dosage instruction objects
        
        Returns:
            Formatted dose string or None if not found
        """
        for dosage in dosage_list:
            dose_and_rate = dosage.get("doseAndRate", [])
            if dose_and_rate:
                qty = dose_and_rate[0].get("doseQuantity", {})
                value = qty.get("value")
                unit = qty.get("unit", "")
                if value is not None:
                    return f"{value} {unit}".strip()
        return None

    def _extract_route(self, dosage_list: list[dict]) -> str | None:
        """Extract administration route from dosage instructions.
        
        Fallback: route.text → route.coding[0].display
        
        Args:
            dosage_list: Array of FHIR dosage instruction objects
        
        Returns:
            Route text (e.g. "oral", "IV") or None
        """
        for dosage in dosage_list:
            route = dosage.get("route", {})
            if text := route.get("text"):
                return text
            codings = route.get("coding", [])
            if codings:
                return codings[0].get("display")
        return None

    def _extract_frequency(self, dosage_list: list[dict]) -> str | None:
        """Extract dosing frequency from timing.code.
        
        Args:
            dosage_list: Array of FHIR dosage instruction objects
        
        Returns:
            Frequency text (e.g. "BID", "twice daily") or None
        """
        for dosage in dosage_list:
            timing = dosage.get("timing", {})
            code = timing.get("code", {})
            if text := code.get("text"):
                return text
        return None

    @staticmethod
    def _extract_entries(bundle: dict) -> list[dict]:
        """Safely extract resource entries from a FHIR Bundle.
        
        Handles empty bundles gracefully (returns empty list).
        
        Args:
            bundle: FHIR Bundle response
        
        Returns:
            List of resource dicts (empty if bundle has no entries)
        """
        return [
            entry["resource"]
            for entry in bundle.get("entry", [])
            if "resource" in entry
        ]
