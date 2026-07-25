"""
Template fallback renderer for DocumentationAgent.

Produces a deterministic DischargeSummarySchema from EncounterContext
when the Vertex AI Gemini call exceeds the 25-second timeout.
No LLM call is made. Output is fully deterministic.
"""
from __future__ import annotations

import logging
from typing import List

from agents.documentation.fhir_fetcher import EncounterContext
from agents.documentation.schemas import (
    DiagnosisEntry,
    DischargeSummarySchema,
    FollowUpInstruction,
    GenerationType,
    MedicationEntry,
    ProcedureEntry,
)

logger = logging.getLogger(__name__)


class TemplateFallbackRenderer:
    """
    Generates a structured DischargeSummarySchema from EncounterContext
    using deterministic field mapping — no LLM call.

    Used when Vertex AI Gemini exceeds the 25-second API timeout.
    All mandatory sections are populated with structured FHIR data or
    safe clinical defaults. Output generation_type is set to TEMPLATE.
    """

    def render(self, encounter: EncounterContext) -> DischargeSummarySchema:
        """
        Produce a template-based DischargeSummarySchema.

        Args:
            encounter: PHI-minimised FHIR encounter context.

        Returns:
            DischargeSummarySchema with generation_type=TEMPLATE.
            Never raises an exception.
        """
        logger.warning(
            "Using template fallback for discharge summary (AI timeout)",
            extra={"encounter_id": encounter.encounter_id},
        )

        return DischargeSummarySchema(
            encounter_id=encounter.encounter_id,
            generation_type=GenerationType.TEMPLATE,
            diagnosis_summary=self._map_diagnoses(encounter),
            procedures=self._map_procedures(encounter),
            medications_at_discharge=self._map_medications(encounter),
            follow_up_instructions=self._default_follow_up(),
            warning_signs=self._default_warning_signs(),
            activity_restrictions=self._default_activity_restrictions(encounter),
        )

    # -------------------------------------------------------------------------
    # Section mappers
    # -------------------------------------------------------------------------

    def _map_diagnoses(self, encounter: EncounterContext) -> List[DiagnosisEntry]:
        if not encounter.diagnoses:
            return [DiagnosisEntry(icd10_code="Z99.89", description="Condition details to be completed by physician", is_primary=True)]
        return [
            DiagnosisEntry(
                icd10_code=dx.icd10_code,
                description=dx.description,
                is_primary=dx.is_primary,
            )
            for dx in encounter.diagnoses
        ]

    def _map_medications(self, encounter: EncounterContext) -> List[MedicationEntry]:
        if not encounter.medications:
            return [MedicationEntry(drug_name="As prescribed", dose="As directed", frequency="As directed", route="oral")]
        return [
            MedicationEntry(
                drug_name=med.drug_name,
                dose=med.dose,
                frequency=med.frequency,
                route=med.route,
                rxnorm_code=med.rxnorm_code,
            )
            for med in encounter.medications
        ]

    def _map_procedures(self, encounter: EncounterContext) -> List[ProcedureEntry]:
        return [ProcedureEntry(description=proc) for proc in encounter.procedures_performed]

    def _default_follow_up(self) -> List[FollowUpInstruction]:
        return [
            FollowUpInstruction(
                instruction="Follow up with your primary care physician.",
                timeframe="within 7 days",
                provider_type="primary care physician",
            ),
            FollowUpInstruction(
                instruction="Contact your care team if your condition worsens.",
                timeframe="immediately if symptoms worsen",
            ),
        ]

    def _default_warning_signs(self) -> List[str]:
        return [
            "Call 911 or go to the emergency room if you have chest pain or trouble breathing.",
            "Call your doctor if you have a fever over 101°F (38.3°C).",
            "Call your doctor if your symptoms get worse or you have new symptoms.",
        ]

    def _default_activity_restrictions(self, encounter: EncounterContext) -> List[str]:
        los = encounter.length_of_stay_days or 0
        if los >= 3:
            return [
                "Rest at home for at least 2-3 days after discharge.",
                "Avoid strenuous activity until cleared by your doctor.",
                "Do not drive if you are taking narcotic pain medication.",
            ]
        return [
            "Resume normal activities gradually as tolerated.",
            "Avoid heavy lifting (over 10 lbs) until cleared by your doctor.",
        ]
