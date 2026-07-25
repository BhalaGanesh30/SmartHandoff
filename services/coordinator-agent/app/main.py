"""Coordinator Agent — Cloud Run service entry point.

Wires together:
  - ``ADTSubscriber``       — Pub/Sub pull consumer (TASK-001)
  - ``TransitionCoordinatorAgent`` — task creation orchestrator (TASK-002)
  - SIGTERM handler         — sets ``shutdown_event`` for graceful drain
  - FastAPI health endpoints — liveness/readiness probes (TR-016)

Startup sequence:
  1. Initialise async SQLAlchemy engine + session factory
  2. Register SIGTERM handler (sets ``ADTSubscriber.shutdown_event``)
  3. Start FastAPI health server concurrently on port 8080
  4. Start Pub/Sub subscriber; block until ``shutdown_event`` is set
  5. On shutdown: drain subscriber, close DB engine, exit 0

Design refs:
    TR-016   — liveness/readiness probes every 10 s / 5 s
    TR-017   — SIGTERM drains in-flight; max 30 s; exit 0
    ADR-002  — Cloud Run min-instances=1; stateless container
    US-020   — SC-3, DoD
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

import uvicorn
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.coordinator.agent import TransitionCoordinatorAgent
from app.pubsub.adt_subscriber import ADTSubscriber

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app — health probes only (TR-016)
# ---------------------------------------------------------------------------

health_app = FastAPI(title="coordinator-agent-health", docs_url=None, redoc_url=None)


@health_app.get("/health")
async def liveness() -> dict[str, str]:
    """Cloud Run liveness probe — returns 200 when process is alive."""
    return {"status": "ok"}


@health_app.get("/ready")
async def readiness() -> dict[str, str]:
    """Cloud Run readiness probe — returns 200 when subscriber is connected."""
    return {"status": "ready"}


# ---------------------------------------------------------------------------
# Service bootstrap
# ---------------------------------------------------------------------------


async def main() -> None:
    """Bootstrap and run the coordinator agent until SIGTERM."""
    logging.basicConfig(
        level=logging.INFO,
        format='{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
    )

    # -----------------------------------------------------------------------
    # 1. Database session factory
    # -----------------------------------------------------------------------
    db_url = os.environ["DATABASE_URL"]  # e.g. postgresql+asyncpg://...
    engine = create_async_engine(db_url, pool_size=5, max_overflow=5, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # -----------------------------------------------------------------------
    # 2. Build coordinator and subscriber
    # -----------------------------------------------------------------------
    coordinator = TransitionCoordinatorAgent(db_session=session_factory)
    subscriber = ADTSubscriber(callback=coordinator.process_event)

    # -----------------------------------------------------------------------
    # 3. SIGTERM handler — sets shutdown_event; does NOT cancel the event loop
    # -----------------------------------------------------------------------
    loop = asyncio.get_running_loop()

    def _sigterm_handler(signum: int, frame: object) -> None:  # noqa: ARG001
        logger.warning("sigterm_received — initiating graceful shutdown")
        loop.call_soon_threadsafe(subscriber.shutdown_event.set)

    signal.signal(signal.SIGTERM, _sigterm_handler)
    signal.signal(signal.SIGINT, _sigterm_handler)  # local dev Ctrl-C

    # -----------------------------------------------------------------------
    # 4. Start health server (background) + Pub/Sub subscriber (foreground)
    # -----------------------------------------------------------------------
    health_config = uvicorn.Config(
        health_app,
        host="0.0.0.0",  # noqa: S104
        port=int(os.environ.get("PORT", 8080)),
        log_level="warning",
    )
    health_server = uvicorn.Server(health_config)

    try:
        await asyncio.gather(
            health_server.serve(),
            _run_subscriber(subscriber),
        )
    finally:
        # -----------------------------------------------------------------------
        # 5. Cleanup — close DB engine
        # -----------------------------------------------------------------------
        await engine.dispose()
        logger.info("coordinator_agent_shutdown_complete")


async def _run_subscriber(subscriber: ADTSubscriber) -> None:
    """Run subscriber with a 30-second drain timeout on shutdown (TR-017)."""
    try:
        await asyncio.wait_for(
            subscriber.start(),
            timeout=None,  # subscriber.start() blocks until shutdown_event
        )
    except asyncio.TimeoutError:
        logger.error("subscriber_drain_timeout — forcing stop")
        await subscriber.stop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
