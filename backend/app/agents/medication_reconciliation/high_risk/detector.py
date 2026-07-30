"""HighRiskDrugClassDetector — scans discharge medication list for ISMP high-alert drugs.

For each medication in the discharge list, performs a case-insensitive exact-match
against the pre-built drug_to_class reverse lookup from HighRiskDrugConfig.
Dose and strength tokens (e.g. "5mg", "10 units") are stripped before matching.

Detection is ADDITIVE: a drug can trigger both a drug-interaction alert (US-031)
and a high-risk drug class alert (US-032) simultaneously.

Design refs:
    US-032 AC Scenario 1   — Warfarin 5mg → ANTICOAGULANT, severity=HIGH
    US-032 Technical Notes — case-insensitive match; ADDITIVE with interaction alerts
    design.md §3.1         — Medication Reconciliation Agent
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.agents.medication_reconciliation.drug_interaction.checker import (
    DischargedMedication,
)
from app.agents.medication_reconciliation.high_risk.config_loader import (
    HighRiskDrugConfig,
    high_risk_drug_config as _default_config,
)

logger = logging.getLogger(__name__)

# Tokens that represent dose/strength/form information.
# Pattern: optional space + digit(s) + optional unit suffix (including /mL style ratios).
_DOSE_TOKEN_PATTERN: re.Pattern[str] = re.compile(
    r"\s+\d[\d.,]*\s*(?:mg|mcg|g|ml|units?|iu|meq|mmol|%)?"
    r"(?:/(?:ml|mL|L|kg|day|dose|hr|h))?"
    r"(?:\s+(?:patch|tab|cap|sr|er|xr|ir))?\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class HighRiskDrugMatch:
    """A single high-risk drug detection result.

    Attributes:
        drug_name: Original drug name from the discharge list (unnormalised).
        normalised_name: Lower-cased, dose-stripped name used for matching.
        drug_class: ISMP high-risk class (ANTICOAGULANT | INSULIN | OPIOID | CHEMOTHERAPY).
        severity: Always HIGH per US-032 AC Scenario 1 and ISMP mandate.
    """

    drug_name: str
    normalised_name: str
    drug_class: str
    severity: str = "HIGH"


class HighRiskDrugClassDetector:
    """Scans a discharge medication list and identifies ISMP high-alert medications.

    Args:
        config: Optional custom :class:`HighRiskDrugConfig` instance.
                Defaults to the module-level singleton loaded from
                ``config/high_risk_drugs.yaml``.

    Example::

        detector = HighRiskDrugClassDetector()
        matches = detector.detect([DischargedMedication(rxcui="11289", drug_name="Warfarin 5mg")])
        # matches[0].drug_class == "ANTICOAGULANT"
        # matches[0].severity  == "HIGH"
    """

    def __init__(self, config: HighRiskDrugConfig | None = None) -> None:
        self._config: HighRiskDrugConfig = config or _default_config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, medications: list[DischargedMedication]) -> list[HighRiskDrugMatch]:
        """Identify high-risk medications from a discharge list.

        Args:
            medications: List of discharged medications from US-030 normalisation.

        Returns:
            List of :class:`HighRiskDrugMatch` — one entry per matched drug.
            Empty list if no high-risk drugs found.
        """
        matches: list[HighRiskDrugMatch] = []
        for med in medications:
            match = self._check_medication(med)
            if match:
                logger.info(
                    "High-risk drug detected: drug_name=%r class=%s",
                    med.drug_name,
                    match.drug_class,
                )
                matches.append(match)
        return matches

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_medication(
        self, med: DischargedMedication
    ) -> HighRiskDrugMatch | None:
        """Check a single medication against the YAML lookup table.

        Returns:
            :class:`HighRiskDrugMatch` if matched, otherwise ``None``.
        """
        normalised = self._normalise(med.drug_name)
        drug_class = self._config.drug_to_class.get(normalised)
        if drug_class is None:
            return None
        return HighRiskDrugMatch(
            drug_name=med.drug_name,
            normalised_name=normalised,
            drug_class=drug_class,
            severity="HIGH",
        )

    @staticmethod
    def _normalise(drug_name: str) -> str:
        """Strip dose/strength tokens and lower-case the drug name.

        Args:
            drug_name: Raw drug name from discharge list (e.g. ``"Warfarin 5mg"``).

        Returns:
            Lower-cased, dose-stripped name (e.g. ``"warfarin"``).
        """
        # First strip dose/strength tokens
        stripped = _DOSE_TOKEN_PATTERN.sub("", drug_name)
        # Then strip standalone form suffixes (tablet, capsule, etc.)
        form_pattern = re.compile(
            r"\s+(?:tablet|capsule|cap|injection|syrup|solution|suspension|cream|ointment|patch|powder)s?\b",
            flags=re.IGNORECASE,
        )
        stripped = form_pattern.sub("", stripped)
        return stripped.strip().lower()
