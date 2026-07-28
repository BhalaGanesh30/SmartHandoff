"""Unit tests for discharge time feature engineering (features.py).

Coverage:
    compute_los_so_far_hours: positive, zero, negative (clipped), timezone-naive input
    build_feature_dataframe: correct column names, age derivation, LOS computation
    build_single_feature_vector: returns dict matching ALL_FEATURES

Design refs:
    US-036 TASK-006 — Unit test requirements
    US-036 TASK-001 — Feature engineering implementation
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from features import (
    ALL_FEATURES,
    compute_los_so_far_hours,
    build_feature_dataframe,
    build_single_feature_vector,
)


# ──────────────────────────────────────────────
# compute_los_so_far_hours
# ──────────────────────────────────────────────

def test_los_so_far_hours_positive():
    """LOS computation for normal case (admit before reference)."""
    admit = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    ref = datetime(2026, 7, 17, 14, 0, tzinfo=timezone.utc)  # 6 hours later
    assert compute_los_so_far_hours(admit, ref) == pytest.approx(6.0, abs=0.01)


def test_los_so_far_hours_clips_to_zero_for_future_admit():
    """If admit_time is in the future (data quality issue), return 0.0 not negative."""
    admit = datetime(2026, 7, 17, 14, 0, tzinfo=timezone.utc)
    ref = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    assert compute_los_so_far_hours(admit, ref) == 0.0


def test_los_so_far_hours_handles_timezone_naive_admit():
    """Timezone-naive admit_time is assumed UTC (no crash)."""
    admit = datetime(2026, 7, 17, 8, 0)  # no tzinfo
    ref = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)
    result = compute_los_so_far_hours(admit, ref)
    assert result == pytest.approx(2.0, abs=0.01)


def test_los_so_far_hours_zero_when_admit_equals_reference():
    """LOS = 0 when admit time equals reference time."""
    t = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    assert compute_los_so_far_hours(t, t) == 0.0


def test_los_so_far_hours_fractional():
    """LOS computation with fractional hours."""
    admit = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    ref = datetime(2026, 7, 17, 12, 30, tzinfo=timezone.utc)  # 4.5 hours
    assert compute_los_so_far_hours(admit, ref) == pytest.approx(4.5, abs=0.01)


# ──────────────────────────────────────────────
# build_feature_dataframe
# ──────────────────────────────────────────────

def _make_encounter(**overrides):
    """Helper to create encounter dict with defaults."""
    base = {
        "admit_time": datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
        "patient_dob": datetime(1960, 3, 15, tzinfo=timezone.utc),
        "admit_diagnosis_group": "CARDIAC",
        "unit": "3A",
        "pending_procedures_count": 2,
    }
    return {**base, **overrides}


def test_build_feature_dataframe_returns_correct_columns():
    """Feature DataFrame has all expected columns."""
    df = build_feature_dataframe([_make_encounter()])
    assert list(df.columns) == ALL_FEATURES


def test_build_feature_dataframe_computes_age_correctly():
    """Patient age derived correctly from DOB and admit time."""
    enc = _make_encounter(
        admit_time=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
        patient_dob=datetime(1960, 7, 17, tzinfo=timezone.utc),
    )
    df = build_feature_dataframe([enc])
    # Exact birthday → 66 years old
    assert df.iloc[0]["patient_age"] == 66


def test_build_feature_dataframe_pending_procedures_defaults_to_zero():
    """Missing pending_procedures_count defaults to 0."""
    enc = _make_encounter()
    enc.pop("pending_procedures_count", None)
    df = build_feature_dataframe([enc])
    assert df.iloc[0]["pending_procedures"] == 0


def test_build_feature_dataframe_day_of_week_range():
    """day_of_week must be 0-6."""
    df = build_feature_dataframe([_make_encounter()])
    assert 0 <= df.iloc[0]["day_of_week"] <= 6


def test_build_feature_dataframe_multiple_encounters():
    """DataFrame handles multiple encounters."""
    encounters = [
        _make_encounter(unit="3A"),
        _make_encounter(unit="ICU"),
        _make_encounter(unit="2B"),
    ]
    df = build_feature_dataframe(encounters)
    assert len(df) == 3
    assert df["unit"].tolist() == ["3A", "ICU", "2B"]


def test_build_feature_dataframe_los_computation():
    """LOS is computed correctly in feature dataframe."""
    admit = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    enc = _make_encounter(admit_time=admit)
    df = build_feature_dataframe([enc])
    # LOS should be >= 0 (computed relative to "now" or provided reference)
    assert df.iloc[0]["los_so_far_hours"] >= 0


# ──────────────────────────────────────────────
# build_single_feature_vector
# ──────────────────────────────────────────────

def test_build_single_feature_vector_returns_dict_with_all_features():
    """Feature vector dict contains all expected features."""
    result = build_single_feature_vector(_make_encounter())
    for feature in ALL_FEATURES:
        assert feature in result, f"Missing feature: {feature}"


def test_build_single_feature_vector_patient_age():
    """Patient age is correctly computed in single vector."""
    enc = _make_encounter(
        admit_time=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
        patient_dob=datetime(1990, 7, 17, tzinfo=timezone.utc),
    )
    result = build_single_feature_vector(enc)
    assert result["patient_age"] == 36


def test_build_single_feature_vector_categorical_fields():
    """Categorical fields preserved in vector."""
    enc = _make_encounter(
        admit_diagnosis_group="RESPIRATORY",
        unit="ICU",
    )
    result = build_single_feature_vector(enc)
    assert result["admit_diagnosis_group"] == "RESPIRATORY"
    assert result["unit"] == "ICU"


def test_build_single_feature_vector_numeric_fields():
    """Numeric fields have correct types."""
    result = build_single_feature_vector(_make_encounter())
    assert isinstance(result["patient_age"], (int, float))
    assert isinstance(result["los_so_far_hours"], (int, float))
    assert isinstance(result["day_of_week"], int)
    assert isinstance(result["pending_procedures"], int)
