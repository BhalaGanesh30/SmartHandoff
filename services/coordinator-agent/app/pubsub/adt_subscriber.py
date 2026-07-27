"""Async Pub/Sub pull subscriber for ADT domain events.

Wraps ``google.cloud.pubsub_v1.SubscriberClient`` with:
  - FlowControl(max_messages=10) — back-pressure to prevent OOM
  - ACK-after-success — guarantees at-least-once task creation
  - NACK on exception or shutdown — ensures Pub/Sub redelivers unprocessed
    messages to another coordinator instance (TR-017, TR-015)
  - ACK deadline extension — for tasks that exceed the 60s default ack deadline
  - asyncio.Event-based shutdown — integrates with SIGTERM handler (TASK-003)

Callback contract:
  The caller passes an ``async`` callback with signature:
      async def process(event: ADTEvent) -> None

  The subscriber awaits the callback. If it returns cleanly the message is
  ACK-ed. If it raises any exception the message is NACK-ed (redelivered).

Environment variables:
  PUBSUB_PROJECT_ID       — GCP project ID
  COORDINATOR_SUB_ID      — Subscription ID (typically ``coordinator-sub``)
  ACK_DEADLINE_SECONDS    — ACK deadline extension in seconds (default: 120)

Design refs:
    ADR-001, TR-005, TR-015, TR-017, US-020 SC-1, SC-3, DoD
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.types import FlowControl

if TYPE_CHECKING:
    from google.cloud.pubsub_v1.subscriber.message import Message

    from app.models.adt_event import ADTEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

ProcessCallback = Callable[["ADTEvent"], Awaitable[None]]

# ---------------------------------------------------------------------------
# ADTSubscriber
# ---------------------------------------------------------------------------


class ADTSubscriber:
    """Async pull subscriber for coordinator-sub Pub/Sub subscription.

    Args:
        callback: Async callable ``async def process(event: ADTEvent) -> None``.
            ACK is sent after successful return; NACK on any exception.
        project_id: GCP project ID. Defaults to ``PUBSUB_PROJECT_ID`` env var.
        subscription_id: Pub/Sub subscription ID. Defaults to
            ``COORDINATOR_SUB_ID`` env var.
        ack_deadline_seconds: ACK deadline extension value used when the
            processing callback exceeds 60 seconds. Defaults to
            ``ACK_DEADLINE_SECONDS`` env var or 120.

    Example::

        subscriber = ADTSubscriber(callback=coordinator.process_event)
        await subscriber.start()
        # blocks until shutdown_event is set
        await subscriber.stop()
    """

    def __init__(
        self,
        callback: ProcessCallback,
        project_id: str | None = None,
        subscription_id: str | None = None,
        ack_deadline_seconds: int | None = None,
    ) -> None:
        self._callback = callback
        self._project_id = project_id or os.environ["PUBSUB_PROJECT_ID"]
        self._subscription_id = subscription_id or os.environ["COORDINATOR_SUB_ID"]
        self._subscription_path = (
            f"projects/{self._project_id}/subscriptions/{self._subscription_id}"
        )
        self._ack_deadline = int(
            ack_deadline_seconds
            or os.environ.get("ACK_DEADLINE_SECONDS", 120)
        )
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._client: pubsub_v1.SubscriberClient | None = None
        self._streaming_pull_future: pubsub_v1.futures.StreamingPullFuture | None = None

        # Shutdown coordination
        self.shutdown_event: asyncio.Event = asyncio.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the streaming pull subscription and block until shutdown.

        Opens a streaming pull to ``coordinator-sub`` with
        ``FlowControl(max_messages=10)``. The asyncio event loop remains
        responsive; the synchronous Pub/Sub callback is dispatched from the
        thread-pool executor.

        Blocks until ``shutdown_event`` is set (typically by SIGTERM handler).
        """
        loop = asyncio.get_running_loop()

        self._client = pubsub_v1.SubscriberClient()
        flow_control = FlowControl(max_messages=10)

        def _sync_callback(message: "Message") -> None:
            """Synchronous callback invoked by Pub/Sub client thread."""
            # Schedule the async handler on the event loop
            future = asyncio.run_coroutine_threadsafe(
                self._handle_message(message), loop
            )
            try:
                future.result(timeout=self._ack_deadline)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "pubsub_callback_unhandled_error",
                    extra={"error": str(exc)},
                )
                message.nack()

        self._streaming_pull_future = self._client.subscribe(
            self._subscription_path,
            callback=_sync_callback,
            flow_control=flow_control,
        )

        logger.info(
            "pubsub_subscriber_started",
            extra={"subscription": self._subscription_path},
        )

        # Block until shutdown_event is set
        await self.shutdown_event.wait()
        await self.stop()

    async def stop(self) -> None:
        """Cancel the streaming pull and close the Pub/Sub client.

        Called by the SIGTERM handler (TASK-003). In-flight messages that have
        not yet been ACK-ed will be NACK-ed automatically when the client
        closes (TR-017).
        """
        if self._streaming_pull_future:
            self._streaming_pull_future.cancel()
            try:
                self._streaming_pull_future.result(timeout=5)
            except Exception:  # noqa: BLE001
                pass  # cancellation expected
        if self._client:
            self._client.close()
        self._executor.shutdown(wait=True, cancel_futures=False)
        logger.info("pubsub_subscriber_stopped")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _handle_message(self, message: "Message") -> None:
        """Deserialise, dispatch callback, then ACK or NACK the message.

        On success: ACK the message.
        On exception: NACK the message so Pub/Sub redelivers to DLQ path.

        Args:
            message: Raw Pub/Sub message from the streaming pull.
        """
        encounter_id = message.attributes.get("encounter_id", "unknown")
        event_type = message.attributes.get("event_type", "unknown")

        try:
            adt_event = _deserialise_message(message)
            await self._callback(adt_event)
            message.ack()
            logger.info(
                "pubsub_message_acked",
                extra={
                    "encounter_id": encounter_id,
                    "event_type": event_type,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "pubsub_message_nacked",
                extra={
                    "encounter_id": encounter_id,
                    "event_type": event_type,
                    "error": str(exc),
                },
            )
            message.nack()
            raise


# ---------------------------------------------------------------------------
# Deserialisation helper (module-level pure function — easy to unit test)
# ---------------------------------------------------------------------------


def _deserialise_message(message: "Message") -> "ADTEvent":
    """Deserialise a raw Pub/Sub message into an ``ADTEvent`` domain object.

    The message data is UTF-8-encoded JSON produced by
    ``ADTEvent.model_dump_json()`` in the HL7 Listener service.

    Args:
        message: Raw Pub/Sub message.

    Returns:
        Validated ``ADTEvent`` Pydantic model.

    Raises:
        ValueError: If the message body cannot be deserialised.
        pydantic.ValidationError: If the JSON does not match the ``ADTEvent`` schema.
    """
    # Import here to avoid circular imports at module load time
    from app.models.adt_event import ADTEvent  # noqa: PLC0415

    try:
        payload: dict = json.loads(message.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot deserialise Pub/Sub message body: {exc}") from exc

    return ADTEvent.model_validate(payload)
