"""GCS model loader — downloads and caches the discharge time pipeline at startup.

Design refs:
    US-036 DoD — inference service loads latest model on startup
    design.md §5.1 (TR-007) — models pre-loaded in memory; no per-request cold-load
    US-036 Technical Notes — model file: discharge_time/latest/discharge_time.joblib
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import joblib
from google.cloud import storage

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, Any] = {}

GCS_BUCKET = os.environ.get("ML_MODELS_BUCKET", "ml-models")
GCS_OBJECT = "discharge_time/latest/discharge_time.joblib"


def load_model(bucket_name: str = GCS_BUCKET, object_name: str = GCS_OBJECT) -> Any:
    """Download the model from GCS and cache it in memory.

    Uses a module-level cache so subsequent calls within the same Cloud Run
    instance skip the GCS download (critical for sub-500 ms inference latency).

    Args:
        bucket_name: GCS bucket name.
        object_name: GCS object path to the joblib artefact.

    Returns:
        Loaded Scikit-learn ``Pipeline`` object.

    Raises:
        RuntimeError: If the GCS download or joblib deserialization fails.
    """
    cache_key = f"{bucket_name}/{object_name}"
    if cache_key in _MODEL_CACHE:
        logger.debug("Model cache hit: %s", cache_key)
        return _MODEL_CACHE[cache_key]

    logger.info("Loading model from gs://%s/%s", bucket_name, object_name)
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            pipeline = joblib.load(tmp.name)
            Path(tmp.name).unlink()  # Clean up temp file

        _MODEL_CACHE[cache_key] = pipeline
        logger.info("Model loaded and cached: %s", cache_key)
        return pipeline

    except Exception as exc:
        raise RuntimeError(f"Failed to load model from GCS: gs://{bucket_name}/{object_name}") from exc


def get_model_version(bucket_name: str = GCS_BUCKET) -> str:
    """Return the custom metadata version tag of the latest model blob.

    Falls back to ``"unknown"`` if metadata is unavailable.
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.get_blob("discharge_time/latest/discharge_time.joblib")
        return (blob.metadata or {}).get("version_tag", "unknown") if blob else "unknown"
    except Exception:
        return "unknown"
