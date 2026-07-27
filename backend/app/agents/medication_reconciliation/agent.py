"""Medication Reconciliation Agent — three-way FHIR comparison.

US-030 TASK-004: Implements the MedicationReconciliationAgent that orchestrates
the FHIR fetch → normalisation → three-way comparison pipeline, applies duplicate
and missing-chronic-medication detection, and persists categorised results to
the medication table.

Design refs:
    - US-030 TASK-004 — MedicationReconciliationAgent implementation
    - US-030 TASK-002 — FHIRMedicationFetcher
    - US-030 TASK-003 — RxNormNormaliser, DoseParser
    - US-030 TASK-001 — Medication ORM model
    - US-024 — BaseAgent framework
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base_agent import BaseAgent
from app.models.medication import (
    Medication,
    MedicationListSource,
    ReconciliationCategory,
    ReconciliationFlag,
)
from app.agents.medication_reconciliation.fhir_fetcher import FHIRMedicationFetcher
from app.agents.medication_reconciliation.models import RawMedicationEntry
from app.agents.medication_reconciliation.rxnorm import RxNormNormaliser
from app.agents.medication_reconciliation.dose_parser import parse_dose

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MedicationReconciliationAgent(BaseAgent):
    """
    Compares pre-admission, inpatient, and discharge FHIR medication lists
    and categorises every drug as CONTINUED | NEW | STOPPED | DOSE_CHANGED.

    Detects DUPLICATE and STOPPED_WITHOUT_ORDER conditions and creates
    pharmacist alerts for each.

    Attributes:
        agent_name: Identifier for this agent type ("medication_reconciliation")
        _fetcher: FHIRMedicationFetcher instance for retrieving FHIR medications
        _normaliser: RxNormNormaliser instance for CUI lookups
        _session: SQLAlchemy async session for database operations

    Design refs:
        US-030 TASK-004 — MedicationReconciliationAgent implementation
    """

    agent_name = "medication_reconciliation"

    def __init__(
        self,
        fhir_fetcher: FHIRMedicationFetcher,
        normaliser: RxNormNormaliser,
        session: AsyncSession,
    ) -> None:
        """Initialize the medication reconciliation agent.

        Args:
            fhir_fetcher: Configured FHIRMedicationFetcher for retrieving medications
            normaliser: RxNormNormaliser for mapping drug names to CUIs
            session: Async SQLAlchemy session for database operations
        """
        # Initialize BaseAgent with a placeholder subscription_id
        # In production, this would be configured from settings
        super().__init__(subscription_id="medication-reconciliation-sub")
        self._fetcher = fhir_fetcher
        self._normaliser = normaliser
        self._session = session

    async def run(self, encounter_id: str) -> list[Medication]:
        """
        Execute full medication reconciliation for an encounter.

        This is the main entry point that orchestrates the complete workflow:
        1. Fetch all three medication lists from FHIR
        2. Normalize all drug names to RxNorm CUIs
        3. Parse dose strings into structured values
        4. Perform three-way comparison and categorize
        5. Detect duplicates and missing chronic medications
        6. Create pharmacist alerts for flagged items
        7. Persist all results to database

        Args:
            encounter_id: FHIR Encounter resource ID

        Returns:
            List of persisted Medication ORM records

        Design refs:
            US-030 TASK-004 AC1-AC8
        """
        logger.info(
            "Starting medication reconciliation for encounter %s", encounter_id
        )

        # Step 1: Fetch all three lists
        raw_lists = await self._fetcher.fetch_all(encounter_id)

        # Step 2: Normalise all drug names to RxNorm CUIs
        all_entries: list[RawMedicationEntry] = [
            entry for entries in raw_lists.values() for entry in entries
        ]
        unique_names = list({e.name for e in all_entries})
        cui_map = await self._normaliser.normalise_batch(unique_names)

        # Step 3: Parse doses and assign CUIs
        for entry in all_entries:
            entry.dose_value, entry.dose_unit = parse_dose(entry.dose_string)
            entry.rxnorm_cui = cui_map.get(entry.name)

        # Step 4: Three-way comparison
        medications = self._compare(raw_lists)

        # Step 5: Flag duplicates and missing chronics
        self._detect_duplicates(medications)
        await self._detect_missing_chronic(medications, encounter_id)

        # Step 6: Create pharmacist alerts
        await self._create_alerts(medications, encounter_id)

        # Step 7: Persist to database
        now = datetime.now(timezone.utc)
        for med in medications:
            med.encounter_id = encounter_id
            med.reconciliation_completed_at = now
            self._session.add(med)
        
        await self._session.commit()

        logger.info(
            "Reconciliation complete for %s: %d medications categorised",
            encounter_id,
            len(medications),
        )
        return medications

    # ── Comparison ──────────────────────────────────────────────────────

    def _compare(
        self,
        raw_lists: dict[MedicationListSource, list[RawMedicationEntry]],
    ) -> list[Medication]:
        """Categorise each drug across pre-admit, inpatient, and discharge.

        Builds a unified medication list by comparing drugs across all three
        FHIR lists. Uses RxNorm CUI as the primary key for matching; falls
        back to normalized drug name if CUI is unavailable.

        Args:
            raw_lists: Dictionary mapping each MedicationListSource to its entries

        Returns:
            List of Medication ORM instances with categories assigned

        Design refs:
            US-030 TASK-004 AC1-AC5 — Category assignment logic
        """
        pre_admit = raw_lists.get(MedicationListSource.PRE_ADMIT, [])
        inpatient = raw_lists.get(MedicationListSource.INPATIENT, [])
        discharge = raw_lists.get(MedicationListSource.DISCHARGE, [])

        # Key = CUI if available, otherwise lowercased name
        def key(entry: RawMedicationEntry) -> str:
            return entry.rxnorm_cui or entry.name.lower().strip()

        pre_map: dict[str, RawMedicationEntry] = {key(e): e for e in pre_admit}
        inp_map: dict[str, RawMedicationEntry] = {key(e): e for e in inpatient}
        dis_map: dict[str, RawMedicationEntry] = {key(e): e for e in discharge}

        all_keys = set(pre_map) | set(inp_map) | set(dis_map)
        medications: list[Medication] = []

        for drug_key in all_keys:
            in_pre = drug_key in pre_map
            in_inp = drug_key in inp_map
            in_dis = drug_key in dis_map

            pre_entry = pre_map.get(drug_key)
            inp_entry = inp_map.get(drug_key)
            dis_entry = dis_map.get(drug_key)
            
            # Use the most recent entry as the base record
            entry = dis_entry or inp_entry or pre_entry

            # Build sources list
            sources = []
            if in_pre:
                sources.append(MedicationListSource.PRE_ADMIT)
            if in_inp:
                sources.append(MedicationListSource.INPATIENT)
            if in_dis:
                sources.append(MedicationListSource.DISCHARGE)

            # Determine reconciliation category
            category = self._determine_category(pre_entry, dis_entry, in_pre, in_dis)

            # Extract dose information (with proper attribute check)
            dose_value = getattr(entry, "dose_value", None)
            dose_unit = getattr(entry, "dose_unit", None)
            rxnorm_cui = getattr(entry, "rxnorm_cui", None)

            med = Medication(
                name=entry.name,
                rxnorm_cui=rxnorm_cui,
                reconciliation_category=category,
                flags=[],
                dose_value=dose_value,
                dose_unit=dose_unit,
                route=entry.route,
                frequency=entry.frequency,
                sources=sources,
            )
            medications.append(med)

        return medications

    @staticmethod
    def _determine_category(
        pre: RawMedicationEntry | None,
        dis: RawMedicationEntry | None,
        in_pre: bool,
        in_dis: bool,
    ) -> ReconciliationCategory:
        """Determine the reconciliation category for a medication.

        Logic:
        - CONTINUED: Present in both pre-admit and discharge (with same dose)
        - DOSE_CHANGED: Present in both but with different parsed doses
        - NEW: Present in discharge only
        - STOPPED: Present in pre-admit but not in discharge

        Args:
            pre: Pre-admission medication entry (if exists)
            dis: Discharge medication entry (if exists)
            in_pre: True if medication found in pre-admission list
            in_dis: True if medication found in discharge list

        Returns:
            Assigned ReconciliationCategory

        Design refs:
            US-030 TASK-004 AC2-AC5 — Category determination rules
        """
        if in_pre and in_dis:
            # Check for dose change
            if pre and dis:
                pre_dose = getattr(pre, "dose_value", None)
                dis_dose = getattr(dis, "dose_value", None)
                
                if (
                    pre_dose is not None 
                    and dis_dose is not None 
                    and pre_dose != dis_dose
                ):
                    return ReconciliationCategory.DOSE_CHANGED
            
            return ReconciliationCategory.CONTINUED
        
        if in_dis and not in_pre:
            return ReconciliationCategory.NEW
        
        # in_pre and not in_dis
        return ReconciliationCategory.STOPPED

    # ── Duplicate Detection ──────────────────────────────────────────────

    def _detect_duplicates(self, medications: list[Medication]) -> None:
        """Flag discharge medications sharing CUI + route as DUPLICATE.

        Groups medications by (rxnorm_cui, route) tuple. If 2+ medications
        share the same group key, all are flagged as DUPLICATE.

        Args:
            medications: List of Medication instances (modified in-place)

        Design refs:
            US-030 TASK-004 AC6 — Duplicate detection
        """
        discharge_meds = [
            m
            for m in medications
            if MedicationListSource.DISCHARGE in m.sources
        ]

        grouped: dict[tuple, list[Medication]] = defaultdict(list)
        
        for med in discharge_meds:
            # Group by (CUI or name, route)
            group_key = (
                med.rxnorm_cui or med.name.lower(),
                (med.route or "").lower(),
            )
            grouped[group_key].append(med)

        # Flag all members of groups with 2+ medications
        for group in grouped.values():
            if len(group) >= 2:
                for med in group:
                    if ReconciliationFlag.DUPLICATE not in med.flags:
                        med.flags = [*med.flags, ReconciliationFlag.DUPLICATE]
                        logger.debug(
                            "Flagged duplicate medication: %s (route=%s)",
                            med.name,
                            med.route,
                        )

    # ── Missing Chronic Detection ────────────────────────────────────────

    async def _detect_missing_chronic(
        self, medications: list[Medication], encounter_id: str
    ) -> None:
        """
        For STOPPED medications with no documented stop order in FHIR,
        upgrade to STOPPED_WITHOUT_ORDER flag.

        Queries FHIR for MedicationRequest resources with status=stopped
        for each stopped medication. If no stop order is found, the
        medication is flagged as potentially requiring pharmacist review.

        Args:
            medications: List of Medication instances (modified in-place)
            encounter_id: FHIR Encounter resource ID

        Design refs:
            US-030 TASK-004 AC7 — Missing chronic detection
        """
        stopped_meds = [
            m
            for m in medications
            if m.reconciliation_category == ReconciliationCategory.STOPPED
        ]

        for med in stopped_meds:
            has_stop_order = await self._check_stop_order(med, encounter_id)
            if not has_stop_order:
                med.flags = [
                    *med.flags,
                    ReconciliationFlag.STOPPED_WITHOUT_ORDER,
                ]
                logger.warning(
                    "No stop order found for discontinued medication: %s (CUI=%s)",
                    med.name,
                    med.rxnorm_cui,
                )

    async def _check_stop_order(
        self, med: Medication, encounter_id: str
    ) -> bool:
        """
        Returns True if a MedicationRequest with status=stopped exists for this drug.

        Args:
            med: Medication instance to check
            encounter_id: FHIR Encounter resource ID

        Returns:
            True if a documented stop order exists, False otherwise
        """
        try:
            search_params = {"encounter": encounter_id, "status": "stopped"}
            
            if med.rxnorm_cui:
                search_params["code"] = (
                    f"http://www.nlm.nih.gov/research/umls/rxnorm|{med.rxnorm_cui}"
                )
            
            bundle = await self._fetcher._client.search(
                "MedicationRequest", search_params
            )
            
            has_order = len(bundle.get("entry", [])) > 0
            
            logger.debug(
                "Stop order check for %s: %s",
                med.name,
                "found" if has_order else "not found",
            )
            
            return has_order
            
        except Exception as exc:
            logger.warning(
                "Stop order check failed for %s: %s", med.name, exc
            )
            # Treat as no stop order on error to be conservative
            return False

    # ── Alert Creation ────────────────────────────────────────────────────

    async def _create_alerts(
        self, medications: list[Medication], encounter_id: str
    ) -> None:
        """Publish pharmacist alerts for flagged medications.

        Creates alerts for:
        - STOPPED_WITHOUT_ORDER: High-severity alert
        - DUPLICATE: Medium-severity alert

        Args:
            medications: List of Medication instances
            encounter_id: FHIR Encounter resource ID

        Design refs:
            US-030 TASK-004 AC6-AC7 — Alert creation
        """
        for med in medications:
            if ReconciliationFlag.STOPPED_WITHOUT_ORDER in med.flags:
                await self._publish_alert(
                    encounter_id=encounter_id,
                    drug_name=med.name,
                    flag=ReconciliationFlag.STOPPED_WITHOUT_ORDER,
                    severity="HIGH",
                )
            
            if ReconciliationFlag.DUPLICATE in med.flags:
                await self._publish_alert(
                    encounter_id=encounter_id,
                    drug_name=med.name,
                    flag=ReconciliationFlag.DUPLICATE,
                    severity="MEDIUM",
                )

    async def _publish_alert(
        self,
        encounter_id: str,
        drug_name: str,
        flag: ReconciliationFlag,
        severity: str,
    ) -> None:
        """Publish a pharmacist alert to the pharmacist-alerts Pub/Sub topic.

        Note: This is a stub implementation. In production, this would use
        the BaseAgent's publish_event method once US-024 is fully implemented.

        Args:
            encounter_id: FHIR Encounter resource ID
            drug_name: Name of the flagged medication
            flag: ReconciliationFlag that triggered the alert
            severity: Alert severity (HIGH, MEDIUM, LOW)
        """
        # Stub implementation: log the alert instead of publishing to Pub/Sub
        # TODO: Replace with BaseAgent.publish_event once US-024 is complete
        logger.warning(
            "PHARMACIST ALERT: %s severity for %s in encounter %s: %s",
            severity,
            drug_name,
            encounter_id,
            flag.value,
        )

    # ── BaseAgent Interface Implementation ───────────────────────────────

    def can_handle(self, event_type: str) -> bool:
        """Return True if this agent can process the given ADT event type.

        For medication reconciliation, we handle discharge events (A03).

        Args:
            event_type: ADT event type code (e.g. "A01", "A03")

        Returns:
            True if this agent should process the event type
        """
        # Handle discharge events (A03) — when medication reconciliation is needed
        return event_type in ("A03",)

    async def process(self, event: dict) -> None:
        """Process a single ADT event.

        This is the BaseAgent interface method. For medication reconciliation,
        we extract the encounter_id from the event and run the reconciliation.

        Args:
            event: ADT event dictionary with encounter_id

        Raises:
            KeyError: If encounter_id not found in event
        """
        encounter_id = event.get("encounter_id")
        if not encounter_id:
            logger.error("No encounter_id found in event: %s", event)
            raise KeyError("encounter_id required in ADT event")

        await self.run(encounter_id)
