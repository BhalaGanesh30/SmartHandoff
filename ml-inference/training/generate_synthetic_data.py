"""Generates a synthetic encounter dataset for local development and CI testing.

NOT used in production — production training uses the SmartHandoff DB + FHIR history.
Generates statistically plausible correlations so AUC ≥ 0.80 is achievable.

Usage:
    python -m training.generate_synthetic_data --output data/synthetic_encounters.csv --n 5000

Design refs:
    US-039 TASK-001 — Synthetic data generator for dev/test
    US-039 AC Scenario 3 — AUC-ROC ≥ 0.80 requirement
"""
from __future__ import annotations

import argparse
import numpy as np
import pandas as pd

from training.feature_schema import FEATURE_NAMES

RANDOM_SEED = 42


def generate(n: int = 5_000, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Return a DataFrame of synthetic encounter features with readmission label.

    Label generation logic:
    - Higher prior admissions, more comorbidities, SNF/AMA discharge disposition,
      and longer LOS increase readmission probability.
    - Roughly 20% base readmission rate (realistic for acute care).

    Args:
        n: Number of synthetic encounters to generate.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with columns matching FEATURE_NAMES + "readmitted_30d".
    """
    rng = np.random.default_rng(seed)

    age = rng.integers(18, 95, n).astype(float)
    los_days = rng.exponential(4.5, n).clip(1, 90)
    num_comorbidities = rng.poisson(2.8, n).clip(0, 15).astype(float)
    num_prior_admissions_12mo = rng.poisson(0.8, n).clip(0, 10).astype(float)
    medication_count = rng.poisson(5, n).clip(0, 30).astype(float)
    discharge_disposition = rng.choice([0, 1, 2, 3, 4], n, p=[0.55, 0.15, 0.10, 0.15, 0.05])
    primary_diagnosis_group = rng.integers(0, 20, n)

    # Build linear score to generate realistic labels
    # Tuned for ~25% base rate with strong predictive correlations for AUC ≥ 0.80
    logit = (
        -4.0
        + 0.025 * (age - 65)
        + 0.12 * los_days
        + 0.40 * num_comorbidities
        + 0.75 * num_prior_admissions_12mo
        + 0.10 * medication_count
        + np.where(discharge_disposition == 4, 1.5, 0.0)   # AMA discharge (high risk)
        + np.where(discharge_disposition == 1, 0.8, 0.0)   # SNF (moderate risk)
        + np.where(discharge_disposition == 3, 0.5, 0.0)   # Home health (low-moderate risk)
        + rng.normal(0, 0.35, n)                            # noise (balanced for signal/realistic)
    )
    prob = 1 / (1 + np.exp(-logit))
    readmitted_30d = (rng.uniform(size=n) < prob).astype(int)

    return pd.DataFrame(
        {
            "age": age,
            "los_days": los_days,
            "num_comorbidities": num_comorbidities,
            "num_prior_admissions_12mo": num_prior_admissions_12mo,
            "medication_count": medication_count,
            "discharge_disposition": discharge_disposition.astype(float),
            "primary_diagnosis_group": primary_diagnosis_group.astype(float),
            "readmitted_30d": readmitted_30d,
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic encounter data")
    parser.add_argument("--output", default="data/synthetic_encounters.csv", help="Output CSV path")
    parser.add_argument("--n", type=int, default=5_000, help="Number of encounters to generate")
    args = parser.parse_args()

    df = generate(args.n)
    df.to_csv(args.output, index=False)
    print(f"Generated {len(df)} rows → {args.output}")
    print(f"Readmission rate: {df['readmitted_30d'].mean():.2%}")
