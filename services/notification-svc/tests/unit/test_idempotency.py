"""Unit tests: idempotency guard prevents duplicate notification dispatch.

US-064 AC Scenario 2:
    Given: notification with idempotency_key=NOTIF-001 was already sent
    When: same Pub/Sub message is redelivered
    Then: service detects duplicate; no SMS sent; message ACKed

Tests:
    - test_insert_succeeds_on_first_message: rowcount=1 for new key
    - test_insert_skipped_on_duplicate_key: rowcount=0 for existing key
    - test_consumer_acks_without_dispatch_on_duplicate: dispatcher not called
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.consumer import _upsert_notification


@pytest.mark.asyncio
async def test_insert_succeeds_on_first_message(async_session, sample_sms_request):
    """First message with a new idempotency key inserts 1 row."""
    notification_id = uuid.uuid4()
    rows = await _upsert_notification(async_session, notification_id, sample_sms_request)
    assert rows == 1, "Expected 1 row inserted for new idempotency key"


@pytest.mark.asyncio
async def test_insert_skipped_on_duplicate_key(async_session, sample_sms_request):
    """Second message with the same idempotency key inserts 0 rows."""
    notification_id_1 = uuid.uuid4()
    notification_id_2 = uuid.uuid4()

    rows_first = await _upsert_notification(async_session, notification_id_1, sample_sms_request)
    rows_second = await _upsert_notification(async_session, notification_id_2, sample_sms_request)

    assert rows_first == 1, "First insert should succeed"
    assert rows_second == 0, "Duplicate idempotency_key should be silently skipped"


@pytest.mark.asyncio
async def test_consumer_acks_without_dispatch_on_duplicate(
    async_session, sample_sms_request, mock_twilio_client
):
    """Consumer ACKs the message without calling Twilio on duplicate key."""
    notification_id = uuid.uuid4()
    # Pre-insert the notification row to simulate prior processing
    await _upsert_notification(async_session, notification_id, sample_sms_request)

    mock_subscriber = MagicMock()
    mock_subscriber.acknowledge = MagicMock()

    with patch("app.consumer.AsyncSessionFactory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=async_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.consumer import _process_message
        await _process_message(
            message_data=json.dumps(sample_sms_request.model_dump()).encode(),
            ack_id="test-ack-id",
            subscriber=mock_subscriber,
            subscription_path="projects/test/subscriptions/test-sub",
        )

    # ACK called — message consumed without dispatch
    mock_subscriber.acknowledge.assert_called_once()
    # Twilio not called — no new SMS sent
    mock_twilio_client.messages.create.assert_not_called()
