"""Model evaluation — MAE, RMSE, and percentage within ±2 hours.

Design refs:
    US-036 AC Scenario 2 — ≥80% predictions within ±2 h; MAE ≤2 h
    US-036 DoD           — evaluation metrics must be logged and gated
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUALITY_GATE_MAE_HOURS = 2.0
QUALITY_GATE_WITHIN_2H_PCT = 0.80


class EvaluationResult(NamedTuple):
    """Evaluation result container."""
    mae_hours: float
    rmse_hours: float
    pct_within_2h: float
    passed: bool


def evaluate(pipeline_path: Path, X_test: pd.DataFrame, y_test: pd.Series) -> EvaluationResult:
    """Load the serialised pipeline and evaluate on the provided holdout set.

    Raises:
        SystemExit: If quality gates are not met (CI gate behaviour).

    Returns:
        ``EvaluationResult`` with computed metrics.
    """
    pipeline = joblib.load(pipeline_path)
    y_pred = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    within_2h = float(np.mean(np.abs(y_pred - y_test.to_numpy()) <= 2.0))

    result = EvaluationResult(
        mae_hours=mae,
        rmse_hours=rmse,
        pct_within_2h=within_2h,
        passed=(mae <= QUALITY_GATE_MAE_HOURS and within_2h >= QUALITY_GATE_WITHIN_2H_PCT),
    )

    logger.info("Evaluation — MAE: %.2f h | RMSE: %.2f h | Within ±2h: %.1f%%",
                mae, rmse, within_2h * 100)

    if not result.passed:
        logger.error(
            "QUALITY GATE FAILED — MAE=%.2f (threshold %.1f) | Within±2h=%.1f%% (threshold %.0f%%)",
            mae, QUALITY_GATE_MAE_HOURS, within_2h * 100, QUALITY_GATE_WITHIN_2H_PCT * 100,
        )
        raise SystemExit(1)

    logger.info("✓ Quality gates PASSED")
    return result
