"""Shared intermediate models for medication reconciliation.

This module defines the RawMedicationEntry dataclass used to normalize
medication data from different FHIR resource types (MedicationStatement,
MedicationAdministration, MedicationRequest) into a common format for
processing by the reconciliation algorithm.
"""
from dataclasses import dataclass

from app.models.medication import MedicationListSource


@dataclass
class RawMedicationEntry:
    """Normalised representation of a single medication from any FHIR list.
    
    This source-agnostic model is used as input for RxNorm normalisation
    and comparison in the three-way reconciliation algorithm.
    
    Attributes:
        source: Which FHIR list this medication came from
        fhir_id: Original FHIR resource ID
        name: Display text from FHIR (e.g. "Metformin 500mg oral")
        dose_string: Raw dose string (e.g. "500 mg")
        route: Administration route (e.g. "oral", "IV")
        frequency: Dosing frequency (e.g. "twice daily", "BID")
        status: FHIR status field (active, stopped, completed)
    
    Design refs:
        US-030 TASK-002 — FHIR medication fetcher intermediate model
    """
    source: MedicationListSource
    fhir_id: str
    name: str
    dose_string: str | None = None
    route: str | None = None
    frequency: str | None = None
    status: str | None = None
