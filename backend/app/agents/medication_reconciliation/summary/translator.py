"""Translates a MedicationSummaryOutput into the patient's preferred language.

Reuses the TranslationService (from US-027 translation pipeline) — no new translation
logic is added. Iterates over text fields in each medication entry and translates each
field individually to preserve structure, then reassembles a translated
MedicationSummaryOutput.

Design refs:
    US-033 AC Scenario 4       — preferred_language=es; stored under Document.translations.es
    US-033 Definition of Done  — reuse EP-004 translation pipeline (US-027)
    design.md §4.1             — Vertex AI Gemini 1.5 Flash for translation
"""
from __future__ import annotations

import logging

from app.services.translation_service import TranslationService
from app.agents.medication_reconciliation.summary.schema import (
    ChangedMedicationEntry,
    MedicationEntry,
    MedicationSummaryOutput,
    StoppedMedicationEntry,
)

logger = logging.getLogger(__name__)


class MedicationSummaryTranslator:
    """Translates a MedicationSummaryOutput using the translation service.

    Translates only human-readable text fields (instructions, purpose, side effects,
    reason). Drug names (generic_name, brand_name, dose) are NOT translated.

    Args:
        translation_service: TranslationService instance (from US-027).
    """

    def __init__(self, translation_service: TranslationService) -> None:
        self._svc = translation_service

    async def translate(
        self,
        summary: MedicationSummaryOutput,
        target_language: str,
    ) -> MedicationSummaryOutput:
        """Translate all text fields in the summary to target_language.

        Drug names (generic_name, brand_name, dose) are NOT translated —
        only human-readable instructions, purpose, side effects, and reason fields.

        Args:
            summary: English MedicationSummaryOutput to translate.
            target_language: ISO 639-1 language code (es, fr, zh, pt).

        Returns:
            New MedicationSummaryOutput with text fields translated.
        """
        logger.info(
            "Translating medication summary to language=%s (categories: new=%d, stopped=%d, changed=%d, continued=%d)",
            target_language,
            len(summary.new),
            len(summary.stopped),
            len(summary.changed),
            len(summary.continued),
        )

        # Translate each category independently
        translated_new = [
            await self._translate_medication_entry(med, target_language)
            for med in summary.new
        ]
        translated_stopped = [
            await self._translate_stopped_entry(med, target_language)
            for med in summary.stopped
        ]
        translated_changed = [
            await self._translate_changed_entry(med, target_language)
            for med in summary.changed
        ]
        translated_continued = [
            await self._translate_medication_entry(med, target_language)
            for med in summary.continued
        ]

        return MedicationSummaryOutput(
            new=translated_new,
            stopped=translated_stopped,
            changed=translated_changed,
            continued=translated_continued,
        )

    async def _translate_medication_entry(
        self, entry: MedicationEntry, lang: str
    ) -> MedicationEntry:
        """Translate MedicationEntry text fields (dosing_instructions, purpose, common_side_effects)."""
        # Translate common_side_effects list items individually
        translated_side_effects = [
            await self._svc.translate(effect, lang)
            for effect in entry.common_side_effects
        ]

        # Build update dict with translated fields
        return entry.model_copy(
            update={
                "dosing_instructions": await self._svc.translate(
                    entry.dosing_instructions, lang
                ),
                "purpose": await self._svc.translate(entry.purpose, lang),
                "common_side_effects": translated_side_effects,
            }
        )

    async def _translate_stopped_entry(
        self, entry: StoppedMedicationEntry, lang: str
    ) -> StoppedMedicationEntry:
        """Translate StoppedMedicationEntry text fields (reason only)."""
        # Translate reason if present (nullable field)
        reason = (
            await self._svc.translate(entry.reason, lang)
            if entry.reason
            else None
        )
        return entry.model_copy(update={"reason": reason})

    async def _translate_changed_entry(
        self, entry: ChangedMedicationEntry, lang: str
    ) -> ChangedMedicationEntry:
        """Translate ChangedMedicationEntry text fields (dosing_instructions, reason)."""
        # Translate reason if present (nullable field)
        reason = (
            await self._svc.translate(entry.reason, lang)
            if entry.reason
            else None
        )

        return entry.model_copy(
            update={
                "dosing_instructions": await self._svc.translate(
                    entry.dosing_instructions, lang
                ),
                "reason": reason,
            }
        )
