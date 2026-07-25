"""SLA Monitor service entry point.

Starts the APScheduler SLAMonitor as a FastAPI lifespan background job.
Exposes /health and /ready probes for Cloud Run (TR-016).

US-021 DoD: SLAMonitor runs every 5 minutes via APScheduler AsyncIOScheduler.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.monitor.sla_monitor import SLAMonitor
from app.publisher.escalation_publisher import EscalationPublisher
from app.settings import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager — starts and stops the SLA monitor."""
    publisher = EscalationPublisher(
        project_id=settings.gcp_project_id,
        topic_id="notification-requests",
    )
    monitor = SLAMonitor(publisher=publisher)
    monitor.start()
    logger.info("SLA Monitor service started")
    yield
    monitor.shutdown()
    logger.info("SLA Monitor service stopped")


app = FastAPI(title="SLA Monitor", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    """Liveness probe (TR-016)."""
    return {"status": "ok", "service": "sla-monitor"}


@app.get("/ready")
async def ready() -> dict:
    """Readiness probe (TR-016)."""
    return {"status": "ready", "service": "sla-monitor"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        log_level=settings.log_level.lower(),
    )
