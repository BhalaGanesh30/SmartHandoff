"""Unit tests for individual bed scoring factor functions (factors.py).

Coverage:
    score_acuity_match    — exact, over-resourced, under-resourced, unknown
    score_care_type_match — exact, general-purpose, mismatch, unknown
    score_isolation_match — all four combinations (2×2 isolation/capable matrix)
    score_gender_match    — exact, any-designation, mismatch, unknown
"""
from __future__ import annotations

import pytest

from app.agents.bed_management.scoring.factors import (
    score_acuity_match,
    score_care_type_match,
    score_gender_match,
    score_isolation_match,
)


# ──────────────────────────────────────────────
# score_acuity_match
# ──────────────────────────────────────────────

class TestScoreAcuityMatch:
    def test_exact_match_returns_1_0(self):
        assert score_acuity_match("ICU-step-down", "ICU-step-down") == 1.0

    def test_over_resourced_returns_0_8(self):
        # Patient needs MED-SURG, bed is ICU-step-down (higher capability)
        assert score_acuity_match("MED-SURG", "ICU-step-down") == 0.8

    def test_under_resourced_returns_0_0(self):
        # Patient needs ICU, bed is MED-SURG (insufficient)
        assert score_acuity_match("ICU", "MED-SURG") == 0.0

    def test_unknown_patient_acuity_returns_0_0(self):
        assert score_acuity_match("UNKNOWN", "MED-SURG") == 0.0

    def test_unknown_bed_acuity_returns_0_0(self):
        assert score_acuity_match("MED-SURG", "UNKNOWN") == 0.0


# ──────────────────────────────────────────────
# score_care_type_match
# ──────────────────────────────────────────────

class TestScoreCareTypeMatch:
    def test_exact_match_returns_1_0(self):
        assert score_care_type_match("CARDIAC", "CARDIAC") == 1.0

    def test_general_bed_returns_0_6(self):
        assert score_care_type_match("CARDIAC", "GENERAL") == 0.6

    def test_med_surg_bed_returns_0_6(self):
        assert score_care_type_match("ORTHO", "MED-SURG") == 0.6

    def test_mismatch_returns_0_0(self):
        assert score_care_type_match("CARDIAC", "ORTHO") == 0.0

    def test_empty_patient_type_returns_neutral(self):
        assert score_care_type_match("", "CARDIAC") == 0.5

    def test_empty_bed_type_returns_neutral(self):
        assert score_care_type_match("CARDIAC", "") == 0.5


# ──────────────────────────────────────────────
# score_isolation_match
# ──────────────────────────────────────────────

class TestScoreIsolationMatch:
    def test_isolation_required_and_capable_returns_1_0(self):
        assert score_isolation_match(True, True) == 1.0

    def test_isolation_required_and_not_capable_returns_0_0(self):
        """Hard exclusion case — AC Scenario 2."""
        assert score_isolation_match(True, False) == 0.0

    def test_no_isolation_required_and_capable_returns_0_8(self):
        # Over-resourced isolation room for non-isolation patient
        assert score_isolation_match(False, True) == 0.8

    def test_no_isolation_required_and_not_capable_returns_1_0(self):
        # Standard patient in standard room — ideal
        assert score_isolation_match(False, False) == 1.0


# ──────────────────────────────────────────────
# score_gender_match
# ──────────────────────────────────────────────

class TestScoreGenderMatch:
    def test_exact_match_returns_1_0(self):
        assert score_gender_match("female", "female") == 1.0

    def test_any_designation_returns_0_8(self):
        assert score_gender_match("male", "any") == 0.8

    def test_mismatch_returns_0_0(self):
        assert score_gender_match("female", "male") == 0.0

    def test_empty_patient_gender_returns_neutral(self):
        assert score_gender_match("", "female") == 0.5

    def test_case_insensitive_match(self):
        assert score_gender_match("Female", "female") == 1.0
