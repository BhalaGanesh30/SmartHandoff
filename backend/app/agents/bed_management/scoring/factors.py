"""Individual scoring factor functions for bed recommendation.

Each function returns a normalised score in [0.0, 1.0]:
    1.0 — perfect match
    0.0 — no match (or hard exclusion for isolation)

Design refs:
    US-037 AC Scenario 2 — isolation: non-isolation bed → 0.0 (excluded by algorithm.py)
    US-037 AC Scenario 3 — each factor independently in 0–1 range
    US-037 DoD           — factors: acuity_match, care_type_match, isolation_match, gender_match
"""
from __future__ import annotations


def score_acuity_match(patient_acuity: str, bed_acuity_level: str) -> float:
    """Score how well the bed's acuity level meets the patient's need.

    Acuity hierarchy (descending capability):
        ICU > ICU-step-down > MED-SURG > OBS > ED

    A bed with higher capability than required scores 0.8 (over-resourced).
    An exact match scores 1.0.
    A bed with lower capability than required scores 0.0 (unsafe — hard fail).

    Args:
        patient_acuity: Patient's required acuity level string.
        bed_acuity_level: Bed's acuity capability string.

    Returns:
        Float in [0.0, 1.0].
    """
    _HIERARCHY: list[str] = ["OBS", "ED", "MED-SURG", "ICU-step-down", "ICU"]

    patient_idx = _HIERARCHY.index(patient_acuity) if patient_acuity in _HIERARCHY else -1
    bed_idx = _HIERARCHY.index(bed_acuity_level) if bed_acuity_level in _HIERARCHY else -1

    if patient_idx < 0 or bed_idx < 0:
        return 0.0  # unknown acuity — conservative default

    if bed_idx == patient_idx:
        return 1.0  # exact match
    if bed_idx > patient_idx:
        return 0.8  # over-resourced — acceptable but not optimal
    return 0.0  # under-resourced — unsafe, hard fail


def score_care_type_match(patient_care_type: str, bed_care_type: str) -> float:
    """Score care type compatibility.

    Exact match → 1.0; compatible (e.g. patient needs general, bed offers step-down) → 0.6;
    incompatible → 0.0.

    Args:
        patient_care_type: Admit care type from ``ADTEvent.admit_type`` (e.g. ``"CARDIAC"``).
        bed_care_type: Bed's designated care type from the bed record.

    Returns:
        Float in [0.0, 1.0].
    """
    if not patient_care_type or not bed_care_type:
        return 0.5  # unknown — neutral score

    patient_norm = patient_care_type.strip().upper()
    bed_norm = bed_care_type.strip().upper()

    if patient_norm == bed_norm:
        return 1.0

    # General-purpose beds are compatible with any care type
    if bed_norm in ("GENERAL", "MED-SURG"):
        return 0.6

    return 0.0


def score_isolation_match(
    patient_isolation_required: bool,
    bed_isolation_capable: bool,
) -> float:
    """Score isolation compatibility.

    Hard rules (AC Scenario 2):
        - Isolation required + isolation capable  → 1.0
        - Isolation required + NOT capable        → 0.0  (excluded by caller)
        - No isolation required + capable         → 0.8  (over-resourced)
        - No isolation required + not capable     → 1.0  (perfect fit)

    Args:
        patient_isolation_required: Whether patient needs isolation room.
        bed_isolation_capable: Whether the bed's room supports isolation.

    Returns:
        Float in [0.0, 1.0].
    """
    if patient_isolation_required and bed_isolation_capable:
        return 1.0
    if patient_isolation_required and not bed_isolation_capable:
        return 0.0  # hard exclusion — caller must filter this out
    if not patient_isolation_required and bed_isolation_capable:
        return 0.8  # wastes an isolation room, penalised
    return 1.0  # non-isolation patient in standard room — ideal


def score_gender_match(patient_gender: str, bed_gender_designation: str) -> float:
    """Score gender designation compatibility.

    Rules:
        - Exact match (``female`` / ``female``) → 1.0
        - Bed is ``any`` (gender-neutral)        → 0.8
        - Mismatch                               → 0.0

    Args:
        patient_gender: Patient gender string (``female``, ``male``, ``other``).
        bed_gender_designation: Bed designation (``female``, ``male``, ``any``).

    Returns:
        Float in [0.0, 1.0].
    """
    if not patient_gender or not bed_gender_designation:
        return 0.5  # unknown — neutral score

    patient_norm = patient_gender.strip().lower()
    bed_norm = bed_gender_designation.strip().lower()

    if bed_norm == "any":
        return 0.8  # gender-neutral bed — acceptable
    if patient_norm == bed_norm:
        return 1.0
    return 0.0  # gender mismatch
