"""HTTP client for calling the ML Inference Service.

Calls: POST {ML_INFERENCE_SERVICE_URL}/ml-inference/predict/readmission

Design refs:
    US-039 DoD — ML Inference endpoint POST /ml-inference/predict/readmission
    AIR-011     — Async HTTP client (httpx) with exponential backoff retry (3 attempts)
    design.md TR-007 — inference latency < 500ms
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

ML_INFERENCE_URL = os.getenv("ML_INFERENCE_SERVICE_URL", "http://localhost:8081")
_RETRY_ATTEMPTS = 3
_TIMEOUT_SECONDS = 10.0


async def call_readmission_inference(features: dict[str, float]) -> dict:
    """POST to /ml-inference/predict/readmission and return the JSON response.

    Args:
        features: Dict mapping feature names to float values.

    Returns:
        JSON response dict containing ``risk_score``, ``risk_tier``,
        ``contributing_factors``, and ``model_version``.

    Raises:
        RuntimeError: After max retry attempts exhausted.
    """
    url = f"{ML_INFERENCE_URL}/ml-inference/predict/readmission"
    last_exc: Exception | None = None

    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=features)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_exc = exc
            delay = 2 ** (attempt - 1)
            logger.warning(
                "ML inference call failed (attempt %d/%d): %s. Retrying in %ds.",
                attempt, _RETRY_ATTEMPTS, exc, delay,
            )
            if attempt < _RETRY_ATTEMPTS:
                await asyncio.sleep(delay)

    raise RuntimeError(
        f"ML inference service unavailable after {_RETRY_ATTEMPTS} attempts: {last_exc}"
    )
