"""
Language utility helpers for patient instruction generation.

Provides FHIR preferred-language extraction and SupportedLanguage resolution.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from agents.documentation.patient_instructions_schemas import SupportedLanguage

logger = logging.getLogger(__name__)

_SUPPORTED_CODES: frozenset[str] = frozenset(lang.value for lang in SupportedLanguage)


def resolve_patient_language(
    fhir_patient: dict,
) -> Tuple[SupportedLanguage, bool, Optional[str]]:
    """
    Extract preferred language from FHIR Patient.communication[0].language.coding[0].code.

    Returns:
        Tuple of (resolved_language, is_fallback, requested_language_code)

    Behaviour:
        - If preferred language is in SupportedLanguage → return it, fallback=False
        - If preferred language is not supported → return SupportedLanguage.EN, fallback=True
        - If Patient.communication is absent → return SupportedLanguage.EN, fallback=False
    """
    requested_code: Optional[str] = None

    try:
        communication = fhir_patient.get("communication", [])
        if communication:
            coding = (
                communication[0]
                .get("language", {})
                .get("coding", [{}])
            )
            requested_code = coding[0].get("code") if coding else None
    except (IndexError, KeyError, AttributeError):
        logger.warning("Failed to parse Patient.communication — defaulting to English.")
        return SupportedLanguage.EN, False, None

    if requested_code is None:
        return SupportedLanguage.EN, False, None

    # Normalise to lowercase BCP-47 base tag (e.g. "zh-CN" → "zh")
    normalised = requested_code.lower().split("-")[0]

    if normalised in _SUPPORTED_CODES:
        return SupportedLanguage(normalised), False, None

    logger.info(
        "Unsupported language '%s' requested — falling back to English.", requested_code
    )
    return SupportedLanguage.EN, True, requested_code
