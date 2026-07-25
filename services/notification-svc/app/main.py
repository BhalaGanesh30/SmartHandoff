"""notification-service Cloud Run entrypoint.

Starts the Pub/Sub consumer on service startup.
Exposes /health and /ready HTTP probes for Cloud Run liveness checks (TR-016).
"""
from __future__ import annotations

import asyncio
import os

import uvicorn
from fastapi import FastAPI

from app.consumer import run_consumer
from app.db.session import init_db
from app.webhooks.twilio import router as twilio_router

app = FastAPI(title="SmartHandoff Notification Service")
app.include_router(twilio_router)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint for Cloud Run liveness probe."""
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    """Readiness check endpoint for Cloud Run startup probe."""
    return {"status": "ready"}


@app.on_event("startup")
async def _startup() -> None:
    """Initialize database and start Pub/Sub consumer on service startup."""
    await init_db()
    project_id = os.environ["GCP_PROJECT_ID"]
    subscription_id = os.environ.get("PUBSUB_SUBSCRIPTION_ID", "notification-service-sub")
    asyncio.create_task(run_consumer(project_id, subscription_id))


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
