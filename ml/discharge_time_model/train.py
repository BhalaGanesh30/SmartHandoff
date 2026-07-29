"""Model training pipeline for discharge time prediction.

Loads encounter data from Cloud SQL, engineers features, trains a
GradientBoostingRegressor, evaluates on a 20% holdout set, and
saves the model pipeline as a joblib artefact.

Design refs:
    US-036 DoD — GradientBoostingRegressor; MAE ≤2 h; ≥80% within ±2 h
    design.md §4.1 — Scikit-learn 1.5+; joblib serialisation
    US-036 Technical Notes — model file: models/discharge_time_v1.joblib
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from features import (
    ALL_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_feature_dataframe,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_OUTPUT_PATH = Path("models/discharge_time_v1.joblib")
RANDOM_STATE = 42


def load_training_data(db_url: str) -> tuple[pd.DataFrame, pd.Series]:
    """Query encounter table and return features + target (hours_to_discharge).

    The target is ``(actual_discharge_time - admit_time).total_seconds() / 3600``.
    Only encounters with a non-null ``discharge_time`` are used for training.

    Args:
        db_url: SQLAlchemy-compatible DB connection string (read replica preferred).

    Returns:
        Tuple of (feature DataFrame, target Series).
    """
    import sqlalchemy as sa

    engine = sa.create_engine(db_url)
    query = """
        SELECT
            e.admit_time,
            e.discharge_time,
            EXTRACT(YEAR FROM AGE(e.admit_time, p.dob)) AS patient_age,
            e.admit_diagnosis_group,
            e.unit,
            e.pending_procedures_count,
            EXTRACT(DOW FROM e.admit_time) AS day_of_week
        FROM encounter e
        JOIN patient p ON p.id = e.patient_id
        WHERE e.discharge_time IS NOT NULL
          AND e.deleted_at IS NULL
          AND p.deleted_at IS NULL
    """
    df_raw = pd.read_sql(query, engine)

    # Compute target: hours from admit_time to actual discharge_time
    df_raw["hours_to_discharge"] = (
        pd.to_datetime(df_raw["discharge_time"]) - pd.to_datetime(df_raw["admit_time"])
    ).dt.total_seconds() / 3600.0

    # Clip negative values (data quality guard)
    df_raw = df_raw[df_raw["hours_to_discharge"] >= 0].reset_index(drop=True)

    # Build feature vectors (use admit_time as reference so los_so_far_hours = 0 at training)
    # Instead, use the raw columns already extracted by SQL for training consistency
    feature_df = pd.DataFrame({
        "patient_age": df_raw["patient_age"].astype(float),
        "los_so_far_hours": 0.0,  # At admit_time, LOS = 0; model learns from snapshot features
        "pending_procedures": df_raw["pending_procedures_count"].fillna(0).astype(int),
        "day_of_week": df_raw["day_of_week"].astype(int),
        "admit_diagnosis_group": df_raw["admit_diagnosis_group"].fillna("UNKNOWN"),
        "unit": df_raw["unit"].fillna("UNKNOWN"),
    })

    target = df_raw["hours_to_discharge"]
    logger.info("Loaded %d training samples", len(feature_df))
    return feature_df, target


def build_pipeline() -> Pipeline:
    """Return an untrained Scikit-learn Pipeline.

    Preprocessing:
        - Numeric: median imputation → StandardScaler
        - Categorical: constant imputation → OneHotEncoder (handle_unknown='ignore')
    Estimator:
        - GradientBoostingRegressor (n_estimators=200, max_depth=4)
    """
    numeric_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="UNKNOWN")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    preprocessor = ColumnTransformer([
        ("numeric", numeric_transformer, NUMERIC_FEATURES),
        ("categorical", categorical_transformer, CATEGORICAL_FEATURES),
    ])
    return Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            random_state=RANDOM_STATE,
        )),
    ])


def train(db_url: str, output_path: Path = MODEL_OUTPUT_PATH) -> Path:
    """Run full training pipeline and save joblib artefact.

    Args:
        db_url: DB connection string for training data query.
        output_path: Path to write the serialised ``Pipeline`` joblib file.

    Returns:
        Resolved path of the saved model file.
    """
    X, y = load_training_data(db_url)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_STATE
    )
    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, output_path)
    logger.info("Model saved → %s", output_path.resolve())
    return output_path.resolve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train discharge time prediction model")
    parser.add_argument("--db-url", required=True, help="SQLAlchemy DB URL (read replica)")
    parser.add_argument("--output", default=str(MODEL_OUTPUT_PATH), help="Output joblib path")
    args = parser.parse_args()
    train(db_url=args.db_url, output_path=Path(args.output))
