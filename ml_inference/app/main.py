"""ML Inference Service — Cloud Run FastAPI entrypoint.

Design refs:
    design.md §9.2 — ml-inference: min=1, max=5, 2 vCPU, 2 GB, concurrency=50
    design.md §5.1 (TR-007) — model pre-loaded at startup (no per-request cold-load)
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Response

from app.model_loader import load_model
from app.routers.discharge_time import router as discharge_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SmartHandoff ML Inference Service",
    version="1.0.0",
    description="Discharge time prediction endpoint for the Bed Management Agent",
    docs_url=None,   # Disable Swagger UI in production
    redoc_url=None,
)

app.include_router(discharge_router)


@app.on_event("startup")
async def _startup() -> None:
    """Pre-load model into memory at startup to satisfy TR-007 (<500 ms inference)."""
    logger.info("ML Inference Service starting — pre-loading discharge time model...")
    try:
        load_model()
        logger.info("Model pre-loaded successfully.")
    except RuntimeError as exc:
        logger.critical(
            "STARTUP FAILURE: Discharge time model could not be loaded from GCS. "
            "Inference requests will return 503 until the model is available. Error: %s",
            exc,
        )


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Health check endpoint for Cloud Run."""
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
async def ready() -> dict[str, str] | Response:
    """Readiness probe — returns 503 if model not loaded."""
    from app.model_loader import _MODEL_CACHE
    if not _MODEL_CACHE:
        return Response(status_code=503, content="Model not loaded")
    return {"status": "ready"}
