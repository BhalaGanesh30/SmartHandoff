"""
Pydantic schemas for the Documentation Agent structured output.

These models define the contract between Vertex AI Gemini structured output
(response_schema) and the DocumentationAgent. They are also used by the
Jinja2 template fallback renderer to ensure structural consistency.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class GenerationType(str, Enum):
    """Indicates how the discharge summary was produced."""
    AI = "AI"
    TEMPLATE = "TEMPLATE"


class DiagnosisEntry(BaseModel):
    """Single diagnosis with ICD-10 code and human-readable description."""
    icd10_code: str = Field(
        ...,
        description="ICD-10-CM code, e.g. 'E11.9' for Type 2 diabetes without complications",
    )
    description: str = Field(
        ...,
        description="Generic clinical description — must NOT include patient name or DOB",
    )
    is_primary: bool = Field(
        default=False,
        description="True if this is the primary admission diagnosis",
    )


class MedicationEntry(BaseModel):
    """Medication at discharge with dosage and frequency."""
    drug_name: str = Field(..., description="Generic drug name (not brand name)")
    dose: str = Field(..., description="Dose with unit, e.g. '500 mg'")
    frequency: str = Field(..., description="Frequency, e.g. 'twice daily with meals'")
    route: str = Field(..., description="Route of administration, e.g. 'oral'")
    rxnorm_code: Optional[str] = Field(
        default=None,
        description="RxNorm concept identifier if available",
    )


class ProcedureEntry(BaseModel):
    """Clinical procedure performed during the encounter."""
    cpt_code: Optional[str] = Field(default=None, description="CPT code if applicable")
    description: str = Field(..., description="Procedure description")
    date_performed: Optional[str] = Field(
        default=None,
        description="ISO 8601 date string, e.g. '2026-07-14'",
    )


class FollowUpInstruction(BaseModel):
    """Single follow-up instruction item."""
    instruction: str = Field(..., description="Actionable follow-up step for the patient")
    timeframe: Optional[str] = Field(
        default=None,
        description="Timeframe for action, e.g. 'within 7 days'",
    )
    provider_type: Optional[str] = Field(
        default=None,
        description="Type of provider to follow up with, e.g. 'primary care physician'",
    )


class DischargeSummarySchema(BaseModel):
    """
    Structured discharge summary schema.

    Used as:
    - Vertex AI Gemini response_schema (TASK-004)
    - Template fallback output contract (TASK-005)

    All six mandatory sections must be populated. The LLM is instructed to
    use ICD-10 codes and generic descriptions — NOT patient PII.
    """

    encounter_id: str = Field(
        ...,
        description="Encounter identifier (non-PHI reference key)",
    )

    # --- Mandatory Sections (Scenario 3) ---
    diagnosis_summary: List[DiagnosisEntry] = Field(
        ...,
        min_length=1,
        description="Primary and secondary diagnoses with ICD-10 codes",
    )
    procedures: List[ProcedureEntry] = Field(
        default_factory=list,
        description="Procedures performed during the encounter",
    )
    medications_at_discharge: List[MedicationEntry] = Field(
        ...,
        min_length=1,
        description="Complete medication list at time of discharge",
    )
    follow_up_instructions: List[FollowUpInstruction] = Field(
        ...,
        min_length=1,
        description="Actionable follow-up steps the patient must take",
    )
    warning_signs: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "Symptom warning signs that should prompt the patient to seek immediate care. "
            "Plain language, reading level ≤8th grade."
        ),
    )
    activity_restrictions: List[str] = Field(
        ...,
        min_length=1,
        description="Physical activity restrictions or limitations post-discharge",
    )

    # --- Optional Enrichment ---
    diet_instructions: Optional[List[str]] = Field(
        default=None,
        description="Dietary recommendations if applicable",
    )
    wound_care_instructions: Optional[str] = Field(
        default=None,
        description="Wound care or dressing change instructions if applicable",
    )

    # --- Generation Metadata ---
    generation_type: GenerationType = Field(
        default=GenerationType.AI,
        description="Whether this summary was AI-generated or template-generated (fallback)",
    )
    generation_duration_ms: Optional[int] = Field(
        default=None,
        description="Wall-clock milliseconds taken to generate this summary",
    )
