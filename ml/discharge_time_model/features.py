"""Feature engineering for discharge time prediction.

Extracts and encodes a feature vector from a raw encounter record.
The same logic is used at training time and inference time to guarantee
train-serve symmetry.

Design refs:
    US-036 Technical Notes — feature list, los_so_far_hours derivation
    US-036 DoD — features: admit_diagnosis_group, patient_age,
                           los_so_far_hours, pending_procedures,
                           unit, day_of_week
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import pandas as pd

# Categorical columns that require one-hot encoding.
CATEGORICAL_FEATURES = ["admit_diagnosis_group", "unit"]

# Numeric columns used as-is after imputation.
NUMERIC_FEATURES = [
    "patient_age",
    "los_so_far_hours",
    "pending_procedures",
    "day_of_week",  # 0=Monday … 6=Sunday
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def compute_los_so_far_hours(admit_time: datetime, reference_time: datetime | None = None) -> float:
    """Return elapsed hours since admission (float, ≥0).

    Args:
        admit_time: UTC-aware ``datetime`` of the encounter admission.
        reference_time: Reference point for elapsed time. Defaults to ``datetime.now(UTC)``.

    Returns:
        Length-of-stay so far in fractional hours.
    """
    ref = reference_time or datetime.now(timezone.utc)
    delta = ref - admit_time.replace(tzinfo=timezone.utc) if admit_time.tzinfo is None else ref - admit_time
    return max(delta.total_seconds() / 3600.0, 0.0)


def build_feature_dataframe(encounters: list[dict[str, Any]], reference_time: datetime | None = None) -> pd.DataFrame:
    """Build a feature DataFrame from a list of raw encounter dicts.

    Args:
        encounters: List of encounter dicts with at minimum the keys:
            ``admit_time``, ``patient_dob``, ``admit_diagnosis_group``,
            ``unit``, ``pending_procedures_count``, ``admit_date``.
        reference_time: Passed through to ``compute_los_so_far_hours``.

    Returns:
        ``pd.DataFrame`` with columns matching ``ALL_FEATURES``.
    """
    rows = []
    for enc in encounters:
        admit_time: datetime = enc["admit_time"]
        dob: datetime = enc["patient_dob"]
        age = math.floor((admit_time - dob).days / 365.25)

        row = {
            "patient_age": age,
            "los_so_far_hours": compute_los_so_far_hours(admit_time, reference_time),
            "pending_procedures": int(enc.get("pending_procedures_count", 0)),
            "day_of_week": admit_time.weekday(),
            "admit_diagnosis_group": str(enc.get("admit_diagnosis_group", "UNKNOWN")),
            "unit": str(enc.get("unit", "UNKNOWN")),
        }
        rows.append(row)

    return pd.DataFrame(rows, columns=ALL_FEATURES)


def build_single_feature_vector(encounter: dict[str, Any], reference_time: datetime | None = None) -> dict[str, Any]:
    """Return a single-row dict for inference-time feature construction.

    Convenience wrapper for building a 1-row DataFrame from a single encounter.
    The returned dict is suitable for ``pd.DataFrame([result])``.
    """
    return build_feature_dataframe([encounter], reference_time).iloc[0].to_dict()
