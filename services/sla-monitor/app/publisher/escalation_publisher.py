"""EscalationPublisher — publishes SUPERVISOR_ESCALATION messages to Pub/Sub.

Implements idempotency per US-021 Technical Notes:
  - Only one escalation fires per (encounter_id, agent_type, breach_window_key).
  - Dedup window derived from SLAConfig.escalation_dedup_window_minutes.
  - In-process set used for single-instance deduplication.
  - Phase 2: replace with Redis TTL key for multi-instance deduplication.

Pub/Sub topic: `notification-requests` (US-021 Scenario 1).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from google.cloud import pubsub_v1

from app.config.sla_loader import load_sla_config

logger = logging.getLogger(__name__)


class EscalationPublisher:
    """Publishes SUPERVISOR_ESCALATION Pub/Sub messages with idempotency guard.

    Args:
        project_id: GCP project ID.
        topic_id: Pub/Sub topic name (default: ``notification-requests``).
    """

    def __init__(
        self,
        project_id: str,
        topic_id: str = "notification-requests",
    ) -> None:
        self._topic_path = pubsub_v1.PublisherClient.topic_path(project_id, topic_id)
        self._publisher = pubsub_v1.PublisherClient()
        self._config = load_sla_config()
        # In-process idempotency set: (encounter_id_str, agent_type, window_bucket)
        # Phase 2: Replace with Redis SETNX TTL for cross-instance dedup.
        self._published_keys: set[tuple[str, str, int]] = set()

    def _breach_window_bucket(self, fired_at: datetime) -> int:
        """Derive a time bucket for dedup window partitioning.

        Tasks are bucketed into windows of `escalation_dedup_window_minutes`.
        Two calls within the same window for the same task map to the same bucket.

        Example: dedup_window=30, fired_at=10:47 → bucket = 10:47 // 30 = 21
        """
        total_minutes_since_epoch = int(fired_at.timestamp() / 60)
        return total_minutes_since_epoch // self._config.escalation_dedup_window_minutes

    async def publish(
        self,
        encounter_id: UUID,
        agent_type: str,
        minutes_elapsed: int,
        supervisor_id: UUID | None,
    ) -> None:
        """Publish a SUPERVISOR_ESCALATION message to the notification-requests topic.

        Skips publishing if an identical escalation was already fired within the
        current dedup window (in-process idempotency).

        Args:
            encounter_id: Encounter UUID being escalated.
            agent_type: Agent type whose SLA was breached.
            minutes_elapsed: Minutes since task creation at time of breach.
            supervisor_id: Supervisor to notify (may be None if unresolved).
        """
        fired_at = datetime.now(tz=timezone.utc)
        window_bucket = self._breach_window_bucket(fired_at)
        dedup_key = (str(encounter_id), agent_type, window_bucket)

        if dedup_key in self._published_keys:
            logger.debug(
                "Escalation suppressed (dedup): encounter_id=%s agent_type=%s window_bucket=%d",
                encounter_id,
                agent_type,
                window_bucket,
            )
            return

        payload = {
            "notification_type": "SUPERVISOR_ESCALATION",
            "encounter_id": str(encounter_id),
            "agent_type": agent_type,
            "minutes_elapsed": minutes_elapsed,
            "supervisor_id": str(supervisor_id) if supervisor_id else None,
            "fired_at": fired_at.isoformat(),
        }
        data = json.dumps(payload).encode("utf-8")

        try:
            future = self._publisher.publish(
                self._topic_path,
                data,
                notification_type="SUPERVISOR_ESCALATION",
                encounter_id=str(encounter_id),
                agent_type=agent_type,
            )
            message_id = future.result(timeout=10)
            self._published_keys.add(dedup_key)
            logger.info(
                "Escalation published: message_id=%s encounter_id=%s agent_type=%s "
                "minutes_elapsed=%d supervisor_id=%s",
                message_id,
                encounter_id,
                agent_type,
                minutes_elapsed,
                supervisor_id,
            )
        except Exception:
            logger.exception(
                "Failed to publish escalation: encounter_id=%s agent_type=%s",
                encounter_id,
                agent_type,
            )
            # Do NOT add to _published_keys on failure — allows retry on next tick.
            raise
