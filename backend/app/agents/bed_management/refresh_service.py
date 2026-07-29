"""BedBoardRefreshService — issues CONCURRENTLY refresh of mv_bed_board.

Called by BedManagementAgent (TASK-001) immediately after each bed status
write to ensure the materialised view is updated within the 60-second SLA
(US-035 AC Scenarios 1 and 2).

Design refs:
    US-035 Technical Notes — REFRESH MATERIALIZED VIEW CONCURRENTLY mv_bed_board
    US-035 AC Scenario 1   — board shows OCCUPIED within 60 s of A01
    US-035 AC Scenario 2   — board shows DIRTY within 60 s of A03
    design.md §6.3 DR-007  — mv_bed_board baseline refresh every 60 s
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_REFRESH_SQL = "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_bed_board"


class BedBoardRefreshService:
    """Issues a CONCURRENTLY materialised-view refresh in a background task.

    The refresh is fired-and-forgotten via ``asyncio.create_task`` so it does
    not block the agent's Pub/Sub acknowledgement path.

    Args:
        write_session_factory: Async SQLAlchemy session factory bound to the
            primary DB (required — REFRESH MV must run on primary, not replica).
    """

    def __init__(self, write_session_factory: Any) -> None:
        self._factory = write_session_factory

    async def refresh_async(self) -> None:
        """Schedule a background CONCURRENTLY refresh without blocking the caller."""
        asyncio.create_task(self._do_refresh(), name="mv_bed_board_refresh")

    async def refresh_sync(self) -> None:
        """Execute the refresh and await completion (used during startup seeding)."""
        await self._do_refresh()

    async def _do_refresh(self) -> None:
        """Execute REFRESH MATERIALIZED VIEW CONCURRENTLY mv_bed_board."""
        try:
            async with self._factory() as session:
                await session.execute(_REFRESH_SQL)
                await session.commit()
            logger.info("mv_bed_board CONCURRENTLY refresh completed")
        except Exception:
            # Refresh failure is non-fatal — pg_cron will retry within 60 s
            logger.exception("mv_bed_board CONCURRENTLY refresh failed (non-fatal)")
