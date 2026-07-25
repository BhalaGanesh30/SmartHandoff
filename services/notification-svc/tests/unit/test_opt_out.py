"""Unit tests: patient opt-out suppresses notification dispatch.

US-064 DoD:
    Opt-out flag: patient.notification_opt_out=True → skip send + log

Tests:
    - test_opted_out_patient_sets_opted_out_status: no Twilio/SendGrid call
    - test_urgency_override_bypasses_opt_out: urgency_override=True → still sends
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dispatchers.sms import TwilioSMSDispatcher
from app.models.notification import Notification, NotificationStatus
from app.schemas import NotificationRequest, NotificationTypeEnum
from app.consumer import _upsert_notification
from sqlalchemy import select


@pytest.mark.asyncio
async def test_opted_out_patient_sets_opted_out_status(
    async_session, sample_sms_request, mock_twilio_client
):
    """patient.notification_opt_out=True → status=OPTED_OUT, Twilio not called."""
    notif_id = uuid.uuid4()
    await _upsert_notification(async_session, notif_id, sample_sms_request)

    dispatcher = TwilioSMSDispatcher.__new__(TwilioSMSDispatcher)
    dispatcher._from_number = "+15005550001"

    with patch(
        "app.dispatchers.sms.TwilioSMSDispatcher._check_opt_out",
        AsyncMock(return_value=True),
    ):
        await dispatcher.dispatch(async_session, notif_id, sample_sms_request)

    row = (await async_session.execute(
        select(Notification).where(Notification.id == notif_id)
    )).scalar_one()

    assert row.delivery_status == NotificationStatus.OPTED_OUT
    mock_twilio_client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_urgency_override_bypasses_opt_out(
    async_session, mock_twilio_client
):
    """urgency_override=True bypasses opt-out check and sends SMS."""
    request = NotificationRequest(
        idempotency_key=f"NOTIF-URGENT-{uuid.uuid4()}",
        type=NotificationTypeEnum.SMS,
        phone="+15005550006",
        template="emergency_alert",
        substitutions={},
        recipient_id=str(uuid.uuid4()),
        urgency_override=True,
    )

    notif_id = uuid.uuid4()
    await _upsert_notification(async_session, notif_id, request)

    dispatcher = TwilioSMSDispatcher.__new__(TwilioSMSDispatcher)
    dispatcher._from_number = "+15005550001"

    with (
        patch(
            "app.dispatchers.sms.TwilioSMSDispatcher._check_opt_out",
            AsyncMock(return_value=True),  # Opted out, but urgency_override=True
        ),
        patch("app.dispatchers.sms._build_twilio_client", return_value=mock_twilio_client),
    ):
        await dispatcher.dispatch(async_session, notif_id, request)

    # urgency_override=True → opt-out bypassed → Twilio called
    mock_twilio_client.messages.create.assert_called_once()
