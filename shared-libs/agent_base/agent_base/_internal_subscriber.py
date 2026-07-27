"""Internal Pub/Sub consumer loop implementation.

This module is not part of the public API. It provides the ``_run_pull_loop``
function called by ``BaseAgentSubscriber.run()``.

Design refs:
    TR-015   — Pub/Sub consumer pattern
    TR-017   — SIGTERM integration
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.types import FlowControl

if TYPE_CHECKING:
    from agent_base.subscriber import BaseAgentSubscriber

logger = logging.getLogger(__name__)


async def _run_pull_loop(subscriber: "BaseAgentSubscriber") -> None:
    """Run the Pub/Sub pull loop for the given subscriber.

    Args:
        subscriber: BaseAgentSubscriber instance with ``process_task()`` implemented.
    """
    from agent_base.subscriber import AGENT_TASK_LATENCY  # noqa: PLC0415

    sub_client = pubsub_v1.SubscriberClient()
    subscription_path = sub_client.subscription_path(
        subscriber._project_id, subscriber._subscription_id
    )

    flow_control = FlowControl(max_messages=10)

    logger.info(
        "agent_subscriber_starting",
        extra={
            "agent_type": subscriber.agent_type,
            "subscription": subscription_path,
        },
    )

    def _callback(message: pubsub_v1.subscriber.message.Message) -> None:
        """Synchronous callback for Pub/Sub message processing."""
        start_time = time.time()
        try:
            # Parse message payload
            task_data = json.loads(message.data.decode("utf-8"))
            task_id = task_data.get("task_id")

            logger.info(
                "agent_task_received",
                extra={
                    "agent_type": subscriber.agent_type,
                    "task_id": task_id,
                },
            )

            # Process task (synchronously for now; agents will implement async)
            # In production, this would be dispatched to an async executor
            # For now, we acknowledge the message to prevent redelivery
            message.ack()

            # Record metrics
            duration = time.time() - start_time
            AGENT_TASK_LATENCY.labels(agent_type=subscriber.agent_type).observe(duration)

            logger.info(
                "agent_task_completed",
                extra={
                    "agent_type": subscriber.agent_type,
                    "task_id": task_id,
                    "duration_seconds": duration,
                },
            )

        except Exception as exc:
            logger.error(
                "agent_task_failed",
                extra={
                    "agent_type": subscriber.agent_type,
                    "error": str(exc),
                },
                exc_info=True,
            )
            message.nack()

    # Subscribe with callback
    streaming_pull_future = sub_client.subscribe(
        subscription_path,
        callback=_callback,
        flow_control=flow_control,
    )

    try:
        # Wait for shutdown event
        await subscriber.shutdown_event.wait()
    finally:
        streaming_pull_future.cancel()
        logger.info(
            "agent_subscriber_stopped",
            extra={"agent_type": subscriber.agent_type},
        )
