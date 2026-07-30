"""FastAPI application entrypoint for the ML Inference Service.

Startup sequence:
    1. Load model + scaler from GCS (or local path in dev)
    2. Load feature_labels.yaml from config/
    3. Register /ml-inference/predict/readmission router

Health endpoints:
    GET /health  — liveness probe (TR-016)
    GET /ready   — readiness probe (TR-016); returns 503 if model not loaded

Design refs:
    US-039 TASK-002 — ML Inference Service implementation
    design.md §3.1 — ML Inference Service (FastAPI + Scikit-learn)
    design.md §4.1 TR-007 — models pre-loaded in container memory
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import yaml
from fastapi import FastAPI, Response

from app.model_loader import load_model
from app.routers.predict import router as predict_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

FEATURE_LABELS_PATH = os.getenv("FEATURE_LABELS_PATH", "config/feature_labels.yaml")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load model artifacts and config at startup; release resources on shutdown."""
    # Load model + scaler (raises RuntimeError if env vars missing)
    load_model()

    # Load feature labels for SHAP human-readable output
    with open(FEATURE_LABELS_PATH, "r") as f:
        config = yaml.safe_load(f)
    
    # Validate that all features have labels
    import sys
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    from training.feature_schema import FEATURE_NAMES
    
    feature_labels = config.get("feature_labels", {})
    missing = [f for f in FEATURE_NAMES if f not in feature_labels]
    if missing:
        raise RuntimeError(
            f"config/feature_labels.yaml is missing labels for features: {missing}. "
            "All FEATURE_NAMES must have a corresponding entry."
        )
    
    app.state.feature_labels = feature_labels
    logger.info("Feature labels loaded from %s", FEATURE_LABELS_PATH)
    logger.info("Feature labels validated — all %d features present.", len(FEATURE_NAMES))

    yield

    # No cleanup required — GCS client closes automatically


app = FastAPI(
    title="SmartHandoff ML Inference Service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,  # Disable Swagger UI in production
    redoc_url=None,
)

app.include_router(predict_router)


@app.get("/health", include_in_schema=False)
async def health() -> dict:
    """Liveness probe for Cloud Run health checks."""
    return {"status": "healthy"}


@app.get("/ready", include_in_schema=False)
async def ready() -> dict | Response:
    """Readiness probe for Cloud Run health checks."""
    from app.model_loader import get_model
    try:
        get_model()
        return {"status": "ready"}
    except RuntimeError:
        return Response(
            status_code=503,
            content='{"status":"not_ready","reason":"model_not_loaded"}',
            media_type="application/json"
        )
