"""
Pydantic schemas for the PatientInstructionsGenerator structured output.

These models define the Gemini structured-output contract for patient-friendly
discharge instructions and per-language translation storage in Document.translations.

Supported languages (FR-022): English, Spanish, French, Chinese Simplified, Portuguese.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class SupportedLanguage(str, Enum):
    """BCP-47 language codes supported for patient instruction generation (FR-022)."""
    EN = "en"
    ES = "es"
    FR = "fr"
    ZH = "zh"
    PT = "pt"


class PatientInstructionsContent(BaseModel):
    """
    Structured patient instructions returned by Gemini Flash.

    All sections must use plain language at ≤6th-grade reading level (Scenario 1).
    Medical jargon must be replaced with common equivalents.
    """
    home_care_instructions: str = Field(
        ...,
        description=(
            "Step-by-step home care instructions written at a 6th-grade reading level. "
            "Use short sentences and common words. Avoid medical jargon."
        ),
    )
    medications: str = Field(
        ...,
        description=(
            "List each medicine with name, dose, when to take it, and why. "
            "Use plain language. Example: 'Take 1 white pill called metformin with breakfast each morning.'"
        ),
    )
    warning_signs: str = Field(
        ...,
        description=(
            "Clear signs that mean the patient should call a doctor or go to the emergency room. "
            "Use plain language bullet points."
        ),
    )
    follow_up_appointments: str = Field(
        ...,
        description=(
            "Who to call, when to make the appointment, and what to say. "
            "Include phone numbers if available."
        ),
    )
    diet_and_activity: str = Field(
        ...,
        description="Foods to eat or avoid, and what physical activities are safe.",
    )
    emergency_contact: str = Field(
        ...,
        description="When and how to contact emergency services or the care team.",
    )


class TranslationEntry(BaseModel):
    """A single translated version of patient instructions with quality metadata."""
    language_code: str = Field(..., description="BCP-47 language code, e.g. 'es'")
    content: PatientInstructionsContent = Field(
        ..., description="Translated instruction content"
    )
    back_translation_similarity: Optional[float] = Field(
        default=None,
        description=(
            "Cosine similarity (0.0–1.0) between original English and back-translated text. "
            "Must be ≥0.85 to pass quality check (Scenario 2)."
        ),
    )
    quality_check_passed: Optional[bool] = Field(
        default=None,
        description="True if back-translation similarity ≥ 0.85.",
    )
    flesch_kincaid_grade: Optional[float] = Field(
        default=None,
        description="Flesch-Kincaid Grade Level of this content (target ≤ 6.0).",
    )


class PatientInstructionsDocument(BaseModel):
    """
    Top-level container for patient instructions document.

    Stores the primary language output and all generated translations.
    Stored as JSON in Document.translations JSONB column.
    """
    primary_language: str = Field(
        ...,
        description="BCP-47 code of the primary output language derived from FHIR Patient.communication.",
    )
    primary_content: PatientInstructionsContent = Field(
        ..., description="Instructions in the primary language."
    )
    primary_flesch_kincaid_grade: float = Field(
        ...,
        description="FK Grade of primary (English base) content. Must be ≤ 6.0 after retry.",
    )
    translations: Dict[str, TranslationEntry] = Field(
        default_factory=dict,
        description="Keyed by BCP-47 language code. Populated for all 5 supported languages.",
    )
    language_fallback: bool = Field(
        default=False,
        description="True when patient's preferred language is not in SupportedLanguage.",
    )
    requested_language: Optional[str] = Field(
        default=None,
        description="The original BCP-47 code requested when fallback was triggered.",
    )

    def translations_as_dict(self) -> dict:
        """
        Serialise translations to a plain dict suitable for JSONB storage.

        Uses Pydantic model_dump() to ensure all nested models are serialised.
        """
        return {
            lang_code: entry.model_dump()
            for lang_code, entry in self.translations.items()
        }
