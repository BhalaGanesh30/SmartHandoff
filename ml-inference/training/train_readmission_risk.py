"""Training pipeline for 30-day readmission risk LogisticRegression model.

Pipeline:
    1. Load encounter features from CSV (dev) or Cloud SQL (prod via --source=db)
    2. Split 80/20 train/test (stratified)
    3. Scale numeric features with StandardScaler
    4. Fit LogisticRegression (L2, C=1.0, max_iter=500, solver=lbfgs)
    5. Evaluate on holdout: AUC-ROC, precision, recall, F1
    6. Fail the script if AUC < 0.80 (CI quality gate)
    7. Serialise model and scaler to GCS (or local path in dev)

Usage:
    # Development (synthetic data, local output)
    python -m training.train_readmission_risk \
        --source csv --data data/synthetic_encounters.csv \
        --output models/

    # Production (real DB, GCS upload)
    python -m training.train_readmission_risk \
        --source db --db-url postgresql+asyncpg://... \
        --gcs-bucket smarthandoff-ml-models --version 1

Design refs:
    US-039 TASK-001 — LogisticRegression training pipeline
    US-039 AC Scenario 3 — AUC-ROC ≥ 0.80 on 20% holdout
    design.md §3.1 — ML Inference Service (Scikit-learn models)
    design.md §4.1 — Scikit-learn 1.5+; LogisticRegression
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from training.feature_schema import FEATURE_NAMES, NUMERIC_FEATURES

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Quality gate — CI fails the build if AUC drops below this threshold
MIN_AUC_THRESHOLD = 0.80
RANDOM_SEED = 42


def load_from_csv(path: str) -> pd.DataFrame:
    """Load encounter data from CSV file.

    Args:
        path: Path to CSV file with FEATURE_NAMES + readmitted_30d columns.

    Returns:
        DataFrame with encounter features and labels.
    """
    logger.info("Loading data from CSV: %s", path)
    return pd.read_csv(path)


def train(df: pd.DataFrame, output_dir: pathlib.Path) -> dict:
    """Train the readmission risk model and return the evaluation metrics dict.

    Args:
        df: DataFrame with columns matching FEATURE_NAMES + "readmitted_30d".
        output_dir: Local directory to write model artifacts.

    Returns:
        Dict with keys: auc_roc, precision, recall, f1, threshold_low, threshold_high.

    Raises:
        ValueError: If AUC < MIN_AUC_THRESHOLD.
    """
    logger.info("Starting model training with %d encounters", len(df))
    
    X = df[FEATURE_NAMES].values
    y = df["readmitted_30d"].values

    logger.info("Train/test split (80/20 stratified)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_SEED
    )

    # Fit scaler on train only — prevent data leakage
    logger.info("Fitting StandardScaler on training data...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    logger.info("Training LogisticRegression model...")
    model = LogisticRegression(
        penalty="l2",
        C=1.0,
        solver="lbfgs",
        max_iter=500,
        random_state=RANDOM_SEED,
        class_weight="balanced",  # Compensate for ~20% readmission base rate
    )
    model.fit(X_train_scaled, y_train)

    # Evaluate on holdout
    logger.info("Evaluating on holdout test set...")
    y_prob = model.predict_proba(X_test_scaled)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    auc_roc = roc_auc_score(y_test, y_prob)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    logger.info("Holdout evaluation — AUC: %.4f | Precision: %.4f | Recall: %.4f | F1: %.4f",
                auc_roc, precision, recall, f1)

    # Quality gate
    if auc_roc < MIN_AUC_THRESHOLD:
        raise ValueError(
            f"Model AUC {auc_roc:.4f} is below the required threshold {MIN_AUC_THRESHOLD}. "
            "Training failed. Improve feature engineering or increase training data."
        )

    logger.info("✓ Quality gate passed: AUC %.4f >= %.2f", auc_roc, MIN_AUC_THRESHOLD)

    # Serialise model and scaler
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_dir / "model.joblib")
    joblib.dump(scaler, output_dir / "scaler.joblib")
    logger.info("Model artifacts written to %s", output_dir)

    metrics = {
        "auc_roc": round(auc_roc, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "readmission_rate_train": round(float(y_train.mean()), 4),
        "readmission_rate_test": round(float(y_test.mean()), 4),
        "min_auc_threshold": MIN_AUC_THRESHOLD,
        "quality_gate": "PASSED",
    }

    # Write evaluation report (JSON)
    report_path = output_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(metrics, indent=2))
    logger.info("Evaluation report written to %s", report_path)

    return metrics


def upload_to_gcs(local_dir: pathlib.Path, bucket: str, version: int) -> None:
    """Upload model artifacts and evaluation report to GCS.

    GCS paths:
        ml-models/readmission-risk/v{N}/model.joblib
        ml-models/readmission-risk/v{N}/scaler.joblib
        ml-models/readmission-risk/v{N}/evaluation_report.json

    Args:
        local_dir: Local directory containing model artifacts.
        bucket: GCS bucket name (e.g. ``"smarthandoff-ml-models"``).
        version: Numeric model version (e.g. ``1``).
    """
    from google.cloud import storage  # Deferred import — not required in dev

    logger.info("Uploading model artifacts to GCS bucket: %s", bucket)
    client = storage.Client()
    bucket_obj = client.bucket(bucket)
    prefix = f"ml-models/readmission-risk/v{version}"

    for filename in ["model.joblib", "scaler.joblib", "evaluation_report.json"]:
        local_path = local_dir / filename
        blob = bucket_obj.blob(f"{prefix}/{filename}")
        blob.upload_from_filename(str(local_path))
        logger.info("Uploaded gs://%s/%s/%s", bucket, prefix, filename)

    logger.info("✓ GCS upload complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train readmission risk model")
    parser.add_argument("--source", choices=["csv", "db"], default="csv",
                        help="Data source: csv (dev) or db (prod)")
    parser.add_argument("--data", default="data/synthetic_encounters.csv",
                        help="Path to CSV data file (when source=csv)")
    parser.add_argument("--output", default="models/",
                        help="Local output directory for model artifacts")
    parser.add_argument("--gcs-bucket", default=None,
                        help="GCS bucket name for uploading model (optional)")
    parser.add_argument("--version", type=int, default=1,
                        help="Model version number for GCS path")
    args = parser.parse_args()

    if args.source == "csv":
        df = load_from_csv(args.data)
    else:
        raise NotImplementedError("DB source not implemented in this task — use CSV for dev")

    metrics = train(df, pathlib.Path(args.output))

    if args.gcs_bucket:
        upload_to_gcs(pathlib.Path(args.output), args.gcs_bucket, args.version)
        logger.info("Upload complete. Metrics: %s", metrics)
    else:
        logger.info("Local training complete. Metrics: %s", metrics)
