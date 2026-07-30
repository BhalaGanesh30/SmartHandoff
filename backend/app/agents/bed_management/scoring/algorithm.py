"""BedScoringAlgorithm — scores VACANT beds against a patient admission profile.

Consumes four factor functions and configurable weights loaded from YAML.
Isolation-required patients are hard-filtered: beds without isolation capability
receive score 0.0 and are excluded from results before ranking (AC Scenario 2).

Design refs:
    US-037 AC Scenario 1   — response contains ≥3 ranked beds with score_breakdown
    US-037 AC Scenario 2   — isolation patients: non-isolation beds excluded
    US-037 AC Scenario 3   — score = Σ(weight_i × factor_i); weights configurable
    US-037 Technical Notes — score range 0.0–1.0; sort descending; return top 5
    US-037 DoD             — BedScoringAlgorithm class; score_breakdown for transparency
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.agents.bed_management.scoring.factors import (
    score_acuity_match,
    score_care_type_match,
    score_gender_match,
    score_isolation_match,
)
from app.agents.bed_management.scoring.weight_loader import ScoringWeights, load_weights

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PatientAdmissionProfile:
    """Minimal patient attributes required for bed scoring.

    Sourced from the ``ADTEvent`` record associated with the encounter.
    No PHI fields — uses coded values only (ACR Scenario 1 / AIR-021).
    """

    acuity_level: str          # e.g. "ICU-step-down"
    admit_type: str            # e.g. "CARDIAC"
    isolation_required: bool
    gender: str                # e.g. "female"


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """Per-factor score breakdown for transparency (AC Scenario 1)."""

    acuity_match: float
    care_type_match: float
    isolation_match: float
    gender_match: float


@dataclass(frozen=True, slots=True)
class BedRecommendation:
    """A single ranked bed recommendation returned by the algorithm."""

    bed_id: str
    unit: str
    room: str
    bed_number: str
    score: float
    score_breakdown: ScoreBreakdown


@dataclass
class BedScoringAlgorithm:
    """Scores and ranks VACANT beds against a patient admission profile.

    Usage::

        algo = BedScoringAlgorithm()
        recommendations = algo.score_and_rank(profile, beds)

    Args:
        weights_path: Optional override for the YAML weights file (used in tests).
    """

    weights_path: Path | None = field(default=None, repr=False)

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def score_and_rank(
        self,
        profile: PatientAdmissionProfile,
        beds: list[dict[str, Any]],
    ) -> list[BedRecommendation]:
        """Score all VACANT beds and return the top 5, ranked descending by score.

        Isolation filter: If ``profile.isolation_required`` is ``True``, any bed
        with ``isolation_capable=False`` is silently excluded before scoring
        (AC Scenario 2).

        Args:
            profile: Patient admission attributes for scoring.
            beds: List of bed dicts from ``mv_bed_board`` with keys:
                  ``bed_id``, ``unit``, ``room``, ``bed_number``, ``bed_type``,
                  ``isolation_capable``, ``gender_designation``.

        Returns:
            Up to 5 :class:`BedRecommendation` objects sorted highest score first.
        """
        weights: ScoringWeights = load_weights(self.weights_path)

        recommendations: list[BedRecommendation] = []

        for bed in beds:
            bed_isolation_capable: bool = bool(bed.get("isolation_capable", False))

            # Hard isolation filter — AC Scenario 2
            if profile.isolation_required and not bed_isolation_capable:
                logger.debug(
                    "Bed %s excluded: isolation required but bed not capable",
                    bed["bed_id"],
                )
                continue

            breakdown = self._compute_breakdown(profile, bed)
            score = self._weighted_score(breakdown, weights)

            recommendations.append(
                BedRecommendation(
                    bed_id=bed["bed_id"],
                    unit=bed["unit"],
                    room=bed["room"],
                    bed_number=bed["bed_number"],
                    score=round(score, 4),
                    score_breakdown=breakdown,
                )
            )

        recommendations.sort(key=lambda r: r.score, reverse=True)
        top_5 = recommendations[:5]
        logger.info(
            "Bed scoring complete: %d candidates → %d recommendations",
            len(beds),
            len(top_5),
        )
        return top_5

    # -----------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------

    def _compute_breakdown(
        self,
        profile: PatientAdmissionProfile,
        bed: dict[str, Any],
    ) -> ScoreBreakdown:
        return ScoreBreakdown(
            acuity_match=score_acuity_match(profile.acuity_level, bed.get("bed_type", "")),
            care_type_match=score_care_type_match(
                profile.admit_type, bed.get("care_type", "")
            ),
            isolation_match=score_isolation_match(
                profile.isolation_required, bool(bed.get("isolation_capable", False))
            ),
            gender_match=score_gender_match(
                profile.gender, bed.get("gender_designation", "any")
            ),
        )

    @staticmethod
    def _weighted_score(breakdown: ScoreBreakdown, weights: ScoringWeights) -> float:
        return (
            weights.acuity * breakdown.acuity_match
            + weights.care_type * breakdown.care_type_match
            + weights.isolation * breakdown.isolation_match
            + weights.gender * breakdown.gender_match
        )
