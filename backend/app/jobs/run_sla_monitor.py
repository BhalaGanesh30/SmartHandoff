"""Entry point for the Alert SLA Monitor Cloud Run Job.

Invoked on a Cloud Scheduler cron trigger (every 30 minutes).

Design refs:
    US-032 AC Scenario 3 — 24h SLA threshold
    ADR-002              — Cloud Run stateless job
"""
from __future__ import annotations

import asyncio
import logging
import sys

from app.db.session import create_db_engines, get_db_session_context
from app.services.alert_sla_monitor import AlertSLAMonitor

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the SLA monitor and exit with code 0 on success, 1 on failure."""
    # Initialize DB engines (required for standalone Cloud Run jobs)
    create_db_engines()

    async with get_db_session_context() as db:
        monitor = AlertSLAMonitor(db=db)
        results = await monitor.run()
        await db.commit()
    logger.info("SLA monitor job finished: %s", results)


if __name__ == "__main__":
    try:
        asyncio.run(main())
        sys.exit(0)
    except Exception as exc:
        logger.exception("SLA monitor job failed: %s", exc)
        sys.exit(1)
