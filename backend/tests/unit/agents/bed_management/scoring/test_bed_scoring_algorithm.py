"""Unit tests for BedScoringAlgorithm (algorithm.py).

Coverage:
    Weighted score formula matches configurable weights (AC Scenario 3)
    Isolation-required patient: non-isolation beds excluded (AC Scenario 2)
    Results sorted descending by score
    Top-5 cap enforced when >5 beds available
    Empty input list → empty result
    All beds excluded by isolation filter → empty result
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents.bed_management.scoring.algorithm import (
    BedScoringAlgorithm,
    PatientAdmissionProfile,
)
from app.agents.bed_management.scoring.weight_loader import ScoringWeights


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

DEFAULT_WEIGHTS = ScoringWeights(acuity=0.4, care_type=0.35, isolation=0.15, gender=0.10)

STANDARD_PROFILE = PatientAdmissionProfile(
    acuity_level="ICU-step-down",
    admit_type="CARDIAC",
    isolation_required=False,
    gender="female",
)

ISOLATION_PROFILE = PatientAdmissionProfile(
    acuity_level="ICU",
    admit_type="GENERAL",
    isolation_required=True,
    gender="male",
)

def _make_bed(
    bed_id: str = "bed-001",
    unit: str = "3A",
    room: str = "301",
    bed_number: str = "A",
    bed_type: str = "ICU-step-down",
    care_type: str = "CARDIAC",
    isolation_capable: bool = False,
    gender_designation: str = "female",
) -> dict:
    return {
        "bed_id": bed_id,
        "unit": unit,
        "room": room,
        "bed_number": bed_number,
        "bed_type": bed_type,
        "care_type": care_type,
        "isolation_capable": isolation_capable,
        "gender_designation": gender_designation,
    }


# ──────────────────────────────────────────────
# Weighted score formula (AC Scenario 3)
# ──────────────────────────────────────────────

class TestWeightedScoreFormula:
    @patch(
        "app.agents.bed_management.scoring.algorithm.load_weights",
        return_value=DEFAULT_WEIGHTS,
    )
    def test_perfect_match_bed_scores_1_0(self, _mock_weights):
        """Exact match on all four factors with default weights → score = 1.0."""
        algo = BedScoringAlgorithm()
        bed = _make_bed(
            bed_type="ICU-step-down",
            care_type="CARDIAC",
            isolation_capable=False,  # non-isolation patient
            gender_designation="female",
        )
        results = algo.score_and_rank(STANDARD_PROFILE, [bed])
        assert len(results) == 1
        assert results[0].score == pytest.approx(1.0, abs=0.001)

    @patch(
        "app.agents.bed_management.scoring.algorithm.load_weights",
        return_value=DEFAULT_WEIGHTS,
    )
    def test_score_equals_weighted_sum_of_factors(self, _mock_weights):
        """score = acuity×0.4 + care_type×0.35 + isolation×0.15 + gender×0.10"""
        algo = BedScoringAlgorithm()
        # Over-resourced acuity (ICU bed for ICU-step-down patient) → acuity=0.8
        # Exact care type → care_type=1.0
        # Non-isolation patient + non-isolation bed → isolation=1.0
        # Exact gender → gender=1.0
        # Expected: 0.8×0.4 + 1.0×0.35 + 1.0×0.15 + 1.0×0.10 = 0.32 + 0.35 + 0.15 + 0.10 = 0.92
        bed = _make_bed(bed_type="ICU", care_type="CARDIAC", isolation_capable=False, gender_designation="female")
        results = algo.score_and_rank(STANDARD_PROFILE, [bed])
        assert results[0].score == pytest.approx(0.92, abs=0.001)

    @patch(
        "app.agents.bed_management.scoring.algorithm.load_weights",
        return_value=DEFAULT_WEIGHTS,
    )
    def test_results_sorted_descending_by_score(self, _mock_weights):
        """Top-ranked bed must have the highest score."""
        algo = BedScoringAlgorithm()
        beds = [
            _make_bed(bed_id="low", bed_type="OBS", care_type="ORTHO"),   # low score
            _make_bed(bed_id="high", bed_type="ICU-step-down", care_type="CARDIAC"),  # high score
        ]
        results = algo.score_and_rank(STANDARD_PROFILE, beds)
        assert results[0].bed_id == "high"
        assert results[0].score > results[1].score

    @patch(
        "app.agents.bed_management.scoring.algorithm.load_weights",
        return_value=DEFAULT_WEIGHTS,
    )
    def test_top_5_cap_enforced(self, _mock_weights):
        """Algorithm returns at most 5 results even when more beds are available."""
        algo = BedScoringAlgorithm()
        beds = [_make_bed(bed_id=f"bed-{i:03d}") for i in range(10)]
        results = algo.score_and_rank(STANDARD_PROFILE, beds)
        assert len(results) <= 5


# ──────────────────────────────────────────────
# Isolation hard filter (AC Scenario 2)
# ──────────────────────────────────────────────

class TestIsolationFilter:
    @patch(
        "app.agents.bed_management.scoring.algorithm.load_weights",
        return_value=DEFAULT_WEIGHTS,
    )
    def test_non_isolation_beds_excluded_for_isolation_patient(self, _mock_weights):
        """All non-isolation-capable beds must be excluded for isolation-required patient."""
        algo = BedScoringAlgorithm()
        beds = [
            _make_bed(bed_id="iso-001", isolation_capable=True),
            _make_bed(bed_id="std-001", isolation_capable=False),
            _make_bed(bed_id="std-002", isolation_capable=False),
        ]
        results = algo.score_and_rank(ISOLATION_PROFILE, beds)
        result_ids = {r.bed_id for r in results}
        assert "iso-001" in result_ids
        assert "std-001" not in result_ids
        assert "std-002" not in result_ids

    @patch(
        "app.agents.bed_management.scoring.algorithm.load_weights",
        return_value=DEFAULT_WEIGHTS,
    )
    def test_all_beds_excluded_returns_empty_list(self, _mock_weights):
        """If every bed fails the isolation filter, result is an empty list."""
        algo = BedScoringAlgorithm()
        beds = [
            _make_bed(bed_id="std-001", isolation_capable=False),
            _make_bed(bed_id="std-002", isolation_capable=False),
        ]
        results = algo.score_and_rank(ISOLATION_PROFILE, beds)
        assert results == []

    @patch(
        "app.agents.bed_management.scoring.algorithm.load_weights",
        return_value=DEFAULT_WEIGHTS,
    )
    def test_empty_bed_list_returns_empty(self, _mock_weights):
        algo = BedScoringAlgorithm()
        assert algo.score_and_rank(STANDARD_PROFILE, []) == []


# ──────────────────────────────────────────────
# Weight loader
# ──────────────────────────────────────────────

class TestWeightLoader:
    def test_load_weights_reads_yaml_values(self, tmp_path):
        yaml_content = (
            "weights:\n"
            "  acuity: 0.40\n"
            "  care_type: 0.35\n"
            "  isolation: 0.15\n"
            "  gender: 0.10\n"
        )
        weights_file = tmp_path / "bed_scoring_weights.yaml"
        weights_file.write_text(yaml_content)

        from app.agents.bed_management.scoring.weight_loader import load_weights
        w = load_weights(path=weights_file)

        assert w.acuity == pytest.approx(0.40)
        assert w.care_type == pytest.approx(0.35)
        assert w.isolation == pytest.approx(0.15)
        assert w.gender == pytest.approx(0.10)

    def test_weight_validation_raises_when_sum_not_1(self):
        from app.agents.bed_management.scoring.weight_loader import ScoringWeights
        bad_weights = ScoringWeights(acuity=0.5, care_type=0.5, isolation=0.1, gender=0.1)
        with pytest.raises(ValueError, match="sum to 1.0"):
            bad_weights.validate()
