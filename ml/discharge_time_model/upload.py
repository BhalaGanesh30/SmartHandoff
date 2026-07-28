"""Upload trained model artefact to GCS ml-models bucket with version tag.

Design refs:
    US-036 DoD — model stored in GCS ml-models bucket with version tag
    US-036 Technical Notes — model file: models/discharge_time_v1.joblib
"""
from __future__ import annotations

import logging
from pathlib import Path

from google.cloud import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GCS_BUCKET = "ml-models"
GCS_OBJECT_PREFIX = "discharge_time"


def upload_model(local_path: Path, version_tag: str, bucket_name: str = GCS_BUCKET) -> str:
    """Upload the model file to GCS and return the GCS URI.

    The object is uploaded to two paths:
    - ``discharge_time/{version_tag}/discharge_time.joblib`` (versioned)
    - ``discharge_time/latest/discharge_time.joblib`` (inference service pointer)

    Args:
        local_path: Path to the local ``joblib`` file.
        version_tag: Semantic version string, e.g. ``"v1"`` or ``"v20260717"``.
        bucket_name: GCS bucket name (default: ``ml-models``).

    Returns:
        GCS URI of the versioned upload.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    versioned_blob_name = f"{GCS_OBJECT_PREFIX}/{version_tag}/discharge_time.joblib"
    latest_blob_name = f"{GCS_OBJECT_PREFIX}/latest/discharge_time.joblib"

    for blob_name in (versioned_blob_name, latest_blob_name):
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(local_path))
        logger.info("Uploaded → gs://%s/%s", bucket_name, blob_name)

    gcs_uri = f"gs://{bucket_name}/{versioned_blob_name}"
    logger.info("Model artefact available at: %s", gcs_uri)
    return gcs_uri
