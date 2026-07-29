"""Pydantic v2 output schema for the patient-readable medication change summary.

This module defines the canonical data contract produced by
``MedicationSummaryGenerator`` and consumed by:
  - Document storage integration (medications_section JSONB column)
  - Translation pipeline (EP-004 / US-027 reuse)
  - Patient portal API response serialisation

Output structure:
    {
        "new":       [MedicationEntry, ...],
        "stopped":   [StoppedMedicationEntry, ...],
        "changed":   [ChangedMedicationEntry, ...],
        "continued": [MedicationEntry, ...]
    }

Design refs:
    US-033 Definition of Done — output schema four-category structure
    US-033 AC Scenario 1      — new: purpose + dosing + side effects; stopped; changed
    design.md §4.2            — Pydantic v2 strict validation
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MedicationEntry(BaseModel):
    """A single medication in the 'new' or 'continued' category.

    Attributes:
        generic_name: Generic (INN) drug name, e.g. ``"Lisinopril"``.
        brand_name: Brand name if available, e.g. ``"Prinivil"``. ``None`` for generics.
        dose: Dose string, e.g. ``"10 mg"``.
        dosing_instructions: Plain-language dosing, e.g. ``"Take 1 tablet once daily"``.
        purpose: Plain-language purpose, e.g. ``"to lower your blood pressure"``.
        common_side_effects: List of common side effects in plain language.
    """

    generic_name: str = Field(..., description="Generic (INN) drug name")
    brand_name: str | None = Field(None, description="Brand name, if available")
    dose: str = Field(..., description="Dose string, e.g. '10 mg'")
    dosing_instructions: str = Field(
        ..., description="Plain-language dosing instructions"
    )
    purpose: str = Field(
        ..., description="Plain-language purpose for the patient"
    )
    common_side_effects: list[str] = Field(
        default_factory=list,
        description="Up to 3 plain-language common side effects",
    )


class StoppedMedicationEntry(BaseModel):
    """A single medication in the 'stopped' category.

    Attributes:
        generic_name: Generic (INN) drug name.
        brand_name: Brand name if available.
        dose: Last known dose string.
        reason: Plain-language reason the medication was stopped, if known.
    """

    generic_name: str
    brand_name: str | None = None
    dose: str
    reason: str | None = Field(
        None,
        description="Plain-language reason medication was stopped (optional)",
    )


class ChangedMedicationEntry(BaseModel):
    """A single medication in the 'changed' (dose or frequency modified) category.

    Attributes:
        generic_name: Generic (INN) drug name.
        brand_name: Brand name if available.
        previous_dose: Previous dose string.
        new_dose: New (current) dose string.
        dosing_instructions: Updated plain-language dosing instructions.
        reason: Plain-language reason for the change, if known.
    """

    generic_name: str
    brand_name: str | None = None
    previous_dose: str = Field(..., description="Dose before the change")
    new_dose: str = Field(..., description="Dose after the change")
    dosing_instructions: str
    reason: str | None = None


class MedicationSummaryOutput(BaseModel):
    """Root output model for the patient-readable medication change summary.

    Attributes:
        new: Medications newly added at discharge.
        stopped: Medications that were discontinued.
        changed: Medications with a dose or frequency change.
        continued: Medications continued unchanged (included for completeness).
    """

    new: list[MedicationEntry] = Field(default_factory=list)
    stopped: list[StoppedMedicationEntry] = Field(default_factory=list)
    changed: list[ChangedMedicationEntry] = Field(default_factory=list)
    continued: list[MedicationEntry] = Field(default_factory=list)
