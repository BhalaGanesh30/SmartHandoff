"""Unit tests: SMS dispatcher retry logic and final failure handling.

US-064 AC Scenario 4:
    Given: Twilio returns HTTP 503 on first send attempt
    When: notification service retries
    Then: retry 2 after 30s, retry 3 after 60s; all 3 fail →
          notification.delivery_status=FAILED, CARE_TEAM_ALERT published

Tests:
    - test_successful_send_sets_status_sent: Twilio 2xx → SENT + SID stored
    - test_transient_503_schedules_retry: Twilio 503 → APScheduler job added
    - test_retry_delays_are_correct: retry 1→30s, 2→60s, 3→120s
    - test_all_retries_exhausted_sets_failed: 3 failures → FAILED
    - test_care_team_alert_published_on_final_failure: Pub/Sub publish called
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from twilio.base.exceptions import TwilioRestException

from app.dispatchers.sms import TwilioSMSDispatcher, _RETRY_DELAYS, _MAX_RETRIES
from app.models.notification import Notification, NotificationStatus
from app.consumer import _upsert_notification
from sqlalchemy import select


def _make_twilio_error(status: int) -> TwilioRestException:
    """Helper: create a TwilioRestException with the given HTTP status."""
    exc = TwilioRestException(
        msg=f"HTTP {status} error",
        uri="/Messages",
        method="POST",
        status=status,
        code=20003,
    )
    return exc


@pytest.mark.asyncio
async def test_successful_send_sets_status_sent(
    async_session, sample_sms_request, mock_twilio_client
):
    """Twilio 2xx response sets notification.delivery_status=SENT and stores SID."""
    dispatcher = TwilioSMSDispatcher.__new__(TwilioSMSDispatcher)
    dispatcher._from_number = "+15005550001"

    notif_id = uuid.uuid4()
    # Pre-insert row
    await _upsert_notification(async_session, notif_id, sample_sms_request)

    with (
        patch("app.dispatchers.sms._build_twilio_client", return_value=mock_twilio_client),
        patch("app.dispatchers.sms.TwilioSMSDispatcher._check_opt_out", AsyncMock(return_value=False)),
    ):
        await dispatcher.dispatch(async_session, notif_id, sample_sms_request)

    row = (await async_session.execute(
        select(Notification).where(Notification.id == notif_id)
    )).scalar_one()

    assert row.delivery_status == NotificationStatus.SENT
    assert row.twilio_message_sid == "SM_TEST_SID_001"
    assert row.sent_at is not None


@pytest.mark.asyncio
async def test_transient_503_schedules_retry(async_session, sample_sms_request):
    """Twilio 503 causes APScheduler job to be scheduled for retry 2."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = _make_twilio_error(503)

    mock_scheduler = MagicMock()
    dispatcher = TwilioSMSDispatcher.__new__(TwilioSMSDispatcher)
    dispatcher._from_number = "+15005550001"

    notif_id = uuid.uuid4()
    await _upsert_notification(async_session, notif_id, sample_sms_request)

    with (
        patch("app.dispatchers.sms._build_twilio_client", return_value=mock_client),
        patch("app.dispatchers.sms.get_scheduler", return_value=mock_scheduler),
        patch("app.dispatchers.sms.TwilioSMSDispatcher._check_opt_out", AsyncMock(return_value=False)),
    ):
        await dispatcher._attempt_send(async_session, notif_id, sample_sms_request, attempt=1)

    mock_scheduler.add_job.assert_called_once()
    call_kwargs = mock_scheduler.add_job.call_args.kwargs
    assert call_kwargs["seconds"] == _RETRY_DELAYS[0]  # 30 seconds


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attempt,expected_delay",
    [(1, 30), (2, 60), (3, 120)],
)
async def test_retry_delays_are_correct(attempt, expected_delay):
    """Each retry attempt uses the correct delay from the backoff schedule."""
    assert _RETRY_DELAYS[attempt - 1] == expected_delay


@pytest.mark.asyncio
async def test_all_retries_exhausted_sets_failed(async_session, sample_sms_request):
    """3 Twilio failures exhausted → notification.delivery_status=FAILED."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = _make_twilio_error(503)

    dispatcher = TwilioSMSDispatcher.__new__(TwilioSMSDispatcher)
    dispatcher._from_number = "+15005550001"

    notif_id = uuid.uuid4()
    await _upsert_notification(async_session, notif_id, sample_sms_request)

    with (
        patch("app.dispatchers.sms._build_twilio_client", return_value=mock_client),
        patch("app.dispatchers.sms.get_scheduler", return_value=MagicMock()),
        patch("app.dispatchers.sms.TwilioSMSDispatcher._check_opt_out", AsyncMock(return_value=False)),
        patch("app.dispatchers.sms.TwilioSMSDispatcher._publish_care_team_alert", AsyncMock()),
    ):
        # Simulate all 3 attempts exhausted (attempt > MAX_RETRIES triggers final failure)
        for attempt in range(1, _MAX_RETRIES + 2):
            await dispatcher._attempt_send(
                async_session, notif_id, sample_sms_request, attempt=attempt
            )

    row = (await async_session.execute(
        select(Notification).where(Notification.id == notif_id)
    )).scalar_one()
    assert row.delivery_status == NotificationStatus.FAILED


@pytest.mark.asyncio
async def test_care_team_alert_published_on_final_failure(
    async_session, sample_sms_request
):
    """CARE_TEAM_ALERT is published to Pub/Sub when all retries exhausted."""
    dispatcher = TwilioSMSDispatcher.__new__(TwilioSMSDispatcher)
    notif_id = uuid.uuid4()

    await _upsert_notification(async_session, notif_id, sample_sms_request)

    mock_publisher = MagicMock()
    with (
        patch("app.dispatchers.sms.pubsub_v1.PublisherClient", return_value=mock_publisher),
        patch.dict("os.environ", {"GCP_PROJECT_ID": "test-project"}),
    ):
        await dispatcher._handle_final_failure(
            async_session, notif_id, sample_sms_request, "Twilio 503 error"
        )

    mock_publisher.publish.assert_called_once()
    published_data = mock_publisher.publish.call_args[0][1]
    import json
    payload = json.loads(published_data)
    assert payload["alert_type"] == "CARE_TEAM_ALERT"
    assert payload["idempotency_key"] == sample_sms_request.idempotency_key
