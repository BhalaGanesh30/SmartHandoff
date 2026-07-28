"""HousekeepingNotifier — publishes housekeeping requests to Pub/Sub on A03.

Published within 5 seconds of an A03 discharge event per US-035 AC Scenario 2.
Payload contains no PHI — only bed coordinates and a deterministic
idempotency key (bed_id + encounter_id hash).

Design refs:
    US-035 AC Scenario 2     — 5-second SLA for housekeeping notification
    US-035 DoD               — notification-requests Pub/Sub topic
    design.md §7.5 AIR-040   — idempotency key prevents duplicate sends
    BR-020                   — no PHI in Pub/Sub payloads
"""
from __future__ import annotations

import json
import logging
import uuid as _uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.bed_management.schemas import HousekeepingNotificationPayload
from app.models.bed import Bed

logger = logging.getLogger(__name__)

_TOPIC_ID = "notification-requests"


class HousekeepingNotifier:
    """Publishes a housekeeping notification to the ``notification-requests`` topic.

    Args:
        pubsub_client: Configured GCP Pub/Sub ``PublisherClient``.
        project_id: GCP project ID (read from Secret Manager / env var).
        read_session_factory: Async SQLAlchemy session factory bound to the
            read replica (used to look up bed coordinates: unit, room, bed_number).
    """

    def __init__(
        self,
        pubsub_client: Any,
        project_id: str,
        read_session_factory: Any,
    ) -> None:
        self._pubsub = pubsub_client
        self._topic_path = pubsub_client.topic_path(project_id, _TOPIC_ID)
        self._read_session_factory = read_session_factory

    async def notify(self, bed_id: str, encounter_id: str) -> None:
        """Publish a housekeeping notification for the given bed.

        Fetches bed coordinates (unit, room, bed_number) from the read replica,
        then publishes the notification. Failure is logged but not re-raised —
        the agent acknowledgement path must not be blocked.

        Args:
            bed_id: UUID string of the bed that requires cleaning.
            encounter_id: UUID string of the encounter that triggered A03.
        """
        try:
            bed = await self._fetch_bed_coordinates(bed_id)
            payload = HousekeepingNotificationPayload.build(
                bed_id=bed_id,
                unit=bed.unit,
                room=bed.room,
                bed_number=bed.bed_number,
                encounter_id=encounter_id,
            )
            await self._publish(payload)
            logger.info(
                "Housekeeping notification published bed_id=%s encounter_id=%s "
                "idempotency_key=%s",
                bed_id,
                encounter_id,
                payload.idempotency_key,
            )
        except Exception:
            logger.exception(
                "Failed to publish housekeeping notification bed_id=%s encounter_id=%s",
                bed_id,
                encounter_id,
            )

    async def _fetch_bed_coordinates(self, bed_id: str) -> Bed:
        """Load bed record from the read replica for coordinate lookup.
        
        Args:
            bed_id: UUID string of the bed.
        
        Returns:
            Bed ORM instance with unit, room, bed_number.
        
        Raises:
            ValueError: If bed not found.
        """
        async with self._read_session_factory() as session:
            result = await session.execute(
                select(Bed).where(Bed.id == _uuid.UUID(bed_id))
            )
            bed = result.scalar_one_or_none()
            if bed is None:
                raise ValueError(f"Bed not found for housekeeping notification: {bed_id}")
            return bed

    async def _publish(self, payload: HousekeepingNotificationPayload) -> None:
        """Publish JSON-encoded payload to the ``notification-requests`` topic.
        
        Args:
            payload: HousekeepingNotificationPayload to publish.
        
        Raises:
            Exception: If publish fails or exceeds 5-second timeout.
        """
        data = json.dumps(payload.model_dump()).encode("utf-8")
        # Pub/Sub attributes for message filtering by the Notification Service
        attributes = {
            "notification_type": payload.notification_type,
            "idempotency_key": payload.idempotency_key,
        }
        future = self._pubsub.publish(self._topic_path, data, **attributes)
        future.result(timeout=5)  # enforce 5-second SLA (US-035 AC Scenario 2)
