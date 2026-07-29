"""Feature schema for the 30-day readmission risk model.

Features aligned with US-039 Technical Notes and design.md FR-052.
All numeric features are scaled via StandardScaler before model training.

Design refs:
    US-039 FR-052 — Readmission risk prediction features
    design.md §4.1 — Scikit-learn 1.5+; LogisticRegression
"""
from __future__ import annotations

from dataclasses import dataclass


# Ordered list of feature names — order must match training and inference
FEATURE_NAMES: list[str] = [
    "age",                        # Patient age in years at admission
    "los_days",                   # Length of stay in days
    "num_comorbidities",          # Count of active Condition resources (FHIR)
    "num_prior_admissions_12mo",  # Count of encounters in prior 12 months (SmartHandoff DB)
    "medication_count",           # Number of active medications at discharge
    "discharge_disposition",      # Encoded: 0=home, 1=SNF, 2=rehab, 3=home_health, 4=AMA
    "primary_diagnosis_group",    # Encoded diagnosis group index (0–19); see feature_labels.yaml
]

# Numeric features requiring StandardScaler normalisation
NUMERIC_FEATURES: list[str] = [
    "age",
    "los_days",
    "num_comorbidities",
    "num_prior_admissions_12mo",
    "medication_count",
]

# Categorical features (already ordinally encoded before pipeline)
CATEGORICAL_FEATURES: list[str] = [
    "discharge_disposition",
    "primary_diagnosis_group",
]
