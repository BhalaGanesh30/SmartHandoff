"""BedInventorySeeder — idempotent startup population of the bed table.

Reads ``config/bed_inventory.yaml`` and inserts bed records using
``INSERT INTO bed ... ON CONFLICT (unit, room, bed_number) DO NOTHING``
to guarantee idempotency across service restarts.

After successful seeding, triggers a synchronous mv_bed_board refresh so
the materialised view is populated before the agent starts consuming events.

Design refs:
    US-035 AC Scenario 4 — idempotent seeding; mv_bed_board populated on first deploy
    US-035 DoD           — INSERT ... ON CONFLICT DO NOTHING from YAML config
    design.md §6.4 DR-020 — MRN deduplication pattern (same ON CONFLICT principle)
"""
from __future__ import annotations

import logging
import pathlib
import uuid
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.bed_management.refresh_service import BedBoardRefreshService
from app.agents.bed_management.schemas import (
    BedInventoryConfig,
    BedInventoryEntry,
    BedStatus,
)

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = pathlib.Path("config/bed_inventory.yaml")


class BedInventorySeeder:
    """Seeds the ``bed`` table from a YAML configuration file.

    Args:
        session_factory: Async SQLAlchemy write session factory.
        refresh_service: ``BedBoardRefreshService`` for post-seed mv refresh.
        config_path: Path to ``bed_inventory.yaml``; defaults to
            ``config/bed_inventory.yaml`` relative to the working directory.
    """

    def __init__(
        self,
        session_factory: Any,
        refresh_service: BedBoardRefreshService,
        config_path: pathlib.Path = _DEFAULT_CONFIG_PATH,
    ) -> None:
        self._session_factory = session_factory
        self._refresh_service = refresh_service
        self._config_path = config_path

    async def seed(self) -> int:
        """Seed the bed table and return the number of rows inserted.

        Returns:
            Number of new bed rows inserted (0 if all rows already existed).
        """
        config = self._load_config()
        beds = config.flat_beds()
        logger.info("Seeding %d beds from %s", len(beds), self._config_path)

        inserted = 0
        async with self._session_factory() as session:
            inserted = await self._insert_beds(session, beds)
            await session.commit()

        logger.info("Seeding complete: %d new beds inserted", inserted)

        # Always refresh the materialised view after seeding (sync — blocks startup
        # until the view is ready, satisfying AC Scenario 4)
        await self._refresh_service.refresh_sync()
        return inserted

    async def _insert_beds(
        self, session: AsyncSession, beds: list[BedInventoryEntry]
    ) -> int:
        """Execute bulk idempotent INSERT for all bed entries.

        Uses ``ON CONFLICT (unit, room, bed_number) DO NOTHING`` — requires a
        unique constraint on ``(unit, room, bed_number)`` in the ``bed`` table
        (established by US-006 migration).

        Returns:
            Total number of rows actually inserted.
        """
        total_inserted = 0
        for entry in beds:
            result = await session.execute(
                text(
                    """
                    INSERT INTO bed
                        (id, unit, room, bed_number, bed_type,
                         status, isolation_required, gender_designation)
                    VALUES
                        (:id, :unit, :room, :bed_number, :bed_type,
                         :status, :isolation_required, :gender_designation)
                    ON CONFLICT (unit, room, bed_number) DO NOTHING
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "unit": entry.unit,
                    "room": entry.room,
                    "bed_number": entry.bed_number,
                    "bed_type": entry.bed_type,
                    "status": BedStatus.VACANT.value,
                    "isolation_required": entry.isolation_required,
                    "gender_designation": entry.gender_designation,
                },
            )
            total_inserted += result.rowcount
        return total_inserted

    def _load_config(self) -> BedInventoryConfig:
        """Load and validate the YAML config file.

        Raises:
            FileNotFoundError: If the config file does not exist.
            pydantic.ValidationError: If the YAML structure is invalid.
        """
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"Bed inventory config not found: {self._config_path}"
            )
        raw = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
        return BedInventoryConfig(**raw)
