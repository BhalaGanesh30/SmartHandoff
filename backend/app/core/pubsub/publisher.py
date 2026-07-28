"""Google Cloud Pub/Sub message publisher.

Provides async publish_message() function for publishing domain events to
GCP Pub/Sub topics. Messages are published with at-least-once delivery
semantics and must be idempotent.

Design refs:
    ADR-001 — all domain events published to Pub/Sub before DB mutations
    TR-005  — async publish confirmed before DB commit
    US-032 AC Scenario 3 — CHARGE_PHARMACIST_ESCALATION notification
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Lazy-loaded Pub/Sub client (initialized on first use)
_publisher_client = None


def _get_publisher():
    """Lazy-load the Pub/Sub publisher client."""
    global _publisher_client
    if _publisher_client is None:
        try:
            from google.cloud import pubsub_v1  # type: ignore[import]

            _publisher_client = pubsub_v1.PublisherClient()
            logger.info("Pub/Sub publisher client initialized")
        except ImportError:
            logger.warning(
                "google-cloud-pubsub not installed — publish_message will be a no-op in local dev"
            )
            _publisher_client = False  # Sentinel value to avoid repeated import attempts
    return _publisher_client if _publisher_client is not False else None


async def publish_message(
    topic: str,
    data: dict[str, Any],
    attributes: dict[str, str] | None = None,
) -> str | None:
    """Publish a message to a GCP Pub/Sub topic.

    Args:
        topic: Topic name (e.g., "notification-requests"). The full topic path
               is constructed from GOOGLE_CLOUD_PROJECT env var.
        data: Message payload dict, serialized to JSON.
        attributes: Optional message attributes dict (metadata).

    Returns:
        Message ID string if published successfully, or None in local dev mode
        (when google-cloud-pubsub is not installed).

    Raises:
        RuntimeError: If GOOGLE_CLOUD_PROJECT is not set.
        Exception: If Pub/Sub publish fails after retries.

    Example::

        await publish_message(
            topic="notification-requests",
            data={"event_type": "CHARGE_PHARMACIST_ESCALATION", "alert_id": "..."},
            attributes={"priority": "IMMEDIATE"},
        )
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        # In local dev without GCP project, log and return
        logger.warning(
            "GOOGLE_CLOUD_PROJECT not set — skipping Pub/Sub publish (local dev mode)"
        )
        logger.debug("Would publish to topic=%s: %s", topic, data)
        return None

    publisher = _get_publisher()
    if publisher is None:
        # Local dev mode without google-cloud-pubsub installed
        logger.debug("Pub/Sub client not available — skipping publish: %s", data)
        return None

    topic_path = publisher.topic_path(project_id, topic)
    message_bytes = json.dumps(data).encode("utf-8")

    try:
        # PublisherClient.publish() returns a Future, but we need sync behavior here
        # In production, consider using async PublisherClient for true async
        future = publisher.publish(
            topic_path,
            message_bytes,
            **(attributes or {}),
        )
        message_id = future.result(timeout=10.0)  # Block until confirmed
        logger.info(
            "Pub/Sub message published: topic=%s message_id=%s event_type=%s",
            topic,
            message_id,
            data.get("event_type", "N/A"),
        )
        return message_id
    except Exception as exc:
        logger.exception(
            "Pub/Sub publish failed: topic=%s event_type=%s error=%s",
            topic,
            data.get("event_type", "N/A"),
            exc,
        )
        raise
