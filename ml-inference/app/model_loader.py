"""Loads model artifacts from GCS (or local path) at service startup.

The model and scaler are loaded once and held in module-level singletons.
This satisfies TR-007: inference latency <500ms with no cold-load per request.

Environment variables:
    ML_MODEL_GCS_URI  : GCS prefix, e.g. gs://smarthandoff-ml-models/ml-models/readmission-risk/v1
    ML_MODEL_LOCAL_DIR: Local directory for dev/test (overrides GCS)
    ML_MODEL_VERSION  : Semantic version string, e.g. "1.0.0"

Design refs:
    US-039 TASK-002 — Model preloading at startup
    design.md §4.1 TR-007 — models pre-loaded in container memory; <500ms inference latency
    ADR-002 — Cloud Run stateless; model artifact loaded from GCS at startup
"""
from __future__ import annotations

import io
import logging
import os
import pathlib

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

_model: LogisticRegression | None = None
_scaler: StandardScaler | None = None
_model_version: str = "unknown"


def _load_local(directory: str) -> tuple[LogisticRegression, StandardScaler]:
    """Load model and scaler from a local directory (dev/test)."""
    base = pathlib.Path(directory)
    model = joblib.load(base / "model.joblib")
    scaler = joblib.load(base / "scaler.joblib")
    logger.info("Model loaded from local path: %s", directory)
    return model, scaler


def _load_from_gcs(gcs_uri: str) -> tuple[LogisticRegression, StandardScaler]:
    """Download model and scaler bytes from GCS and deserialise in memory."""
    from google.cloud import storage

    # gcs_uri format: gs://bucket/prefix
    assert gcs_uri.startswith("gs://"), f"Invalid GCS URI: {gcs_uri}"
    without_scheme = gcs_uri[5:]
    bucket_name, _, prefix = without_scheme.partition("/")

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    def _download(filename: str):
        blob = bucket.blob(f"{prefix}/{filename}")
        buf = io.BytesIO()
        blob.download_to_file(buf)
        buf.seek(0)
        return joblib.load(buf)

    model = _download("model.joblib")
    scaler = _download("scaler.joblib")
    logger.info("Model loaded from GCS: %s", gcs_uri)
    return model, scaler


def load_model() -> None:
    """Load model + scaler at startup. Called once from FastAPI lifespan."""
    global _model, _scaler, _model_version

    local_dir = os.getenv("ML_MODEL_LOCAL_DIR")
    gcs_uri = os.getenv("ML_MODEL_GCS_URI")
    _model_version = os.getenv("ML_MODEL_VERSION", "1.0.0")

    if local_dir:
        _model, _scaler = _load_local(local_dir)
    elif gcs_uri:
        _model, _scaler = _load_from_gcs(gcs_uri)
    else:
        raise RuntimeError(
            "Neither ML_MODEL_LOCAL_DIR nor ML_MODEL_GCS_URI is set. "
            "Cannot load readmission risk model."
        )

    logger.info("Readmission risk model v%s loaded successfully.", _model_version)


def get_model() -> LogisticRegression:
    """Get the loaded LogisticRegression model."""
    if _model is None:
        raise RuntimeError("Model not loaded. Call load_model() during startup.")
    return _model


def get_scaler() -> StandardScaler:
    """Get the loaded StandardScaler."""
    if _scaler is None:
        raise RuntimeError("Scaler not loaded. Call load_model() during startup.")
    return _scaler


def get_model_version() -> str:
    """Get the model version string."""
    return _model_version
