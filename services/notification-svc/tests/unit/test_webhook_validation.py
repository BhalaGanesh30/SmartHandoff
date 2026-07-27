"""Unit tests: Twilio delivery webhook signature validation.

US-064 AC Scenario 3:
    Given: Twilio sends POST /webhooks/twilio/status with MessageSid and MessageStatus=delivered
    When: webhook is processed
    Then: notification.delivery_status updates to DELIVERED; invalid signature → 403

Tests:
    - test_missing_signature_returns_403: no X-Twilio-Signature → 403
    - test_invalid_signature_returns_403: tampered sig → 403
    - test_valid_signature_updates_status_delivered: valid sig → DELIVERED
    - test_intermediate_status_no_db_change: 'sent' status → no DB update
"""
from __future__ import annotations

import uuid
from unittest.mock import patch
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.notification import Notification, NotificationStatus
from sqlalchemy import select


def _generate_valid_signature(url: str, params: dict, auth_token: str) -> str:
    """Generate a valid Twilio signature for testing."""
    from twilio.request_validator import RequestValidator
    validator = RequestValidator(auth_token)
    return validator.compute_signature(url, params)


TEST_AUTH_TOKEN = "TEST_AUTH_TOKEN"
WEBHOOK_URL = "http://testserver/webhooks/twilio/status"


@pytest.mark.asyncio
async def test_missing_signature_returns_403():
    """Request without X-Twilio-Signature header returns HTTP 403."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/webhooks/twilio/status",
            data={"MessageSid": "SM_TEST_001", "MessageStatus": "delivered"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_invalid_signature_returns_403():
    """Tampered or wrong X-Twilio-Signature header returns HTTP 403."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/webhooks/twilio/status",
            data={"MessageSid": "SM_TEST_001", "MessageStatus": "delivered"},
            headers={"X-Twilio-Signature": "INVALID_SIGNATURE"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_valid_signature_updates_status_delivered(async_session):
    """Valid Twilio signature with MessageStatus=delivered → status=DELIVERED."""
    # Insert a pre-existing notification with delivery_status=SENT
    notif = Notification(
        id=uuid.uuid4(),
        idempotency_key=f"NOTIF-WEBHOOK-{uuid.uuid4()}",
        type="SMS",
        template="medication_reminder",
        delivery_status=NotificationStatus.SENT,
        twilio_message_sid="SM_TEST_WEBHOOK_001",
        phone_or_email="+15005550006",
        retry_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    async_session.add(notif)
    await async_session.commit()

    # Compute valid signature
    params = {"MessageSid": "SM_TEST_WEBHOOK_001", "MessageStatus": "delivered"}
    signature = _generate_valid_signature(WEBHOOK_URL, params, TEST_AUTH_TOKEN)

    with (
        patch("app.webhooks.twilio.get_secret", return_value=TEST_AUTH_TOKEN),
        patch("app.webhooks.twilio.get_db_session", return_value=async_session),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/webhooks/twilio/status",
                data=params,
                headers={"X-Twilio-Signature": signature},
            )

    assert response.status_code == 204

    # Verify status updated to DELIVERED
    row = (await async_session.execute(
        select(Notification).where(Notification.id == notif.id)
    )).scalar_one()
    assert row.delivery_status == NotificationStatus.DELIVERED
    assert row.delivered_at is not None


@pytest.mark.asyncio
async def test_intermediate_status_no_db_change(async_session):
    """MessageStatus='sent' (intermediate) does not change notification status."""
    notif = Notification(
        id=uuid.uuid4(),
        idempotency_key=f"NOTIF-WEBHOOK-{uuid.uuid4()}",
        type="SMS",
        template="medication_reminder",
        delivery_status=NotificationStatus.SENT,
        twilio_message_sid="SM_TEST_002",
        phone_or_email="+15005550006",
        retry_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    async_session.add(notif)
    await async_session.commit()

    params = {"MessageSid": "SM_TEST_002", "MessageStatus": "sent"}
    signature = _generate_valid_signature(WEBHOOK_URL, params, TEST_AUTH_TOKEN)

    with (
        patch("app.webhooks.twilio.get_secret", return_value=TEST_AUTH_TOKEN),
        patch("app.webhooks.twilio.get_db_session", return_value=async_session),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/webhooks/twilio/status",
                data=params,
                headers={"X-Twilio-Signature": signature},
            )

    # 204 with no DB change for intermediate status
    assert response.status_code == 204

    # Status should remain SENT
    row = (await async_session.execute(
        select(Notification).where(Notification.id == notif.id)
    )).scalar_one()
    assert row.delivery_status == NotificationStatus.SENT
