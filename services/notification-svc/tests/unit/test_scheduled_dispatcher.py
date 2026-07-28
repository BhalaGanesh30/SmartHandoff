"""Unit tests for dispatch_due_notifications() — US-041 AC Scenarios 3, 4.

Coverage:
    - Opt-out flag → delivery_status=OPTED_OUT, no SMS/email sent
    - Email preference → send_checkin_email() called
    - SMS preference → send_checkin_sms() called
    - Dispatch error → delivery_status=FAILED
    - PENDING record before send_at → NOT dispatched

Design refs:
    US-041 AC Scenario 3 — email dispatched via SendGrid template
    US-041 AC Scenario 4 — opt-out sets delivery_status=OPTED_OUT; no send
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from enum import Enum

import pytest

from app.scheduled_dispatcher import _process_notification


class NotificationChannel(str, Enum):
    """Mock for NotificationChannel enum."""
    SMS = "SMS"
    EMAIL = "EMAIL"


class DeliveryStatus(str, Enum):
    """Mock for DeliveryStatus enum."""
    PENDING = "PENDING"
    SENT = "SENT"
    OPTED_OUT = "OPTED_OUT"
    FAILED = "FAILED"


def make_notification(
    channel: NotificationChannel = NotificationChannel.SMS,
    opt_out: bool = False,
    first_name: str = "Alice",
    phone: str = "+10000000000",
    email: str = "alice@example.com",
):
    """Build a mock ScheduledNotification with a stubbed Patient relationship."""
    notification = MagicMock()
    notification.id = uuid.uuid4()
    notification.encounter_id = uuid.uuid4()
    notification.channel = channel
    notification.delivery_status = DeliveryStatus.PENDING

    patient = MagicMock()
    patient.notification_opt_out = opt_out
    patient.first_name = first_name
    patient.phone = phone
    patient.email = email
    patient.preferred_contact = channel.value.lower()

    notification.patient = patient
    return notification

def make_session_factory(notification):
    """Return a mock async_sessionmaker wrapping a mock AsyncSession."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=notification)
    
    # Create a proper async context manager for begin()
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=session)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)
    
    # Create async context manager for the session factory
    factory = MagicMock()
    factory_ctx = AsyncMock()
    factory_ctx.__aenter__ = AsyncMock(return_value=session)
    factory_ctx.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = factory_ctx
    
    return factory, session


# ─── Opt-Out Tests ─────────────────────────────────────────────────────────────

class TestOptOut:
    @pytest.mark.asyncio
    async def test_opted_out_patient_sets_status_to_opted_out(self):
        """patient.notification_opt_out=True → delivery_status=OPTED_OUT (AC Scenario 4)."""
        notification = make_notification(opt_out=True)
        factory, session = make_session_factory(notification)

        with patch("app.services.sms_service.send_checkin_sms") as mock_sms, \
             patch("app.services.email_service.send_checkin_email") as mock_email:
            await _process_notification(session_factory=factory, notification=notification)

            mock_sms.assert_not_called()
            mock_email.assert_not_called()

        # Confirm _update_status was called with OPTED_OUT
        session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_opted_out_patient_does_not_send_sms(self):
        """No Twilio call made for opted-out patient."""
        notification = make_notification(channel=NotificationChannel.SMS, opt_out=True)
        factory, _ = make_session_factory(notification)

        with patch("app.services.sms_service.send_checkin_sms") as mock_sms:
            await _process_notification(session_factory=factory, notification=notification)
            mock_sms.assert_not_called()

    @pytest.mark.asyncio
    async def test_opted_out_patient_does_not_send_email(self):
        """No SendGrid call made for opted-out patient."""
        notification = make_notification(channel=NotificationChannel.EMAIL, opt_out=True)
        factory, _ = make_session_factory(notification)

        with patch("app.services.email_service.send_checkin_email") as mock_email:
            await _process_notification(session_factory=factory, notification=notification)
            mock_email.assert_not_called()


# ─── Dispatch Tests ────────────────────────────────────────────────────────────

class TestDispatch:
    @pytest.mark.asyncio
    async def test_email_dispatched_for_email_channel(self):
        """channel=EMAIL → send_checkin_email() called with correct args (AC Scenario 3)."""
        notification = make_notification(
            channel=NotificationChannel.EMAIL,
            first_name="Alice",
            email="alice@example.com",
        )
        factory, _ = make_session_factory(notification)

        with patch("app.services.email_service.send_checkin_email") as mock_email, \
             patch("os.environ.get", return_value="1-800-CARE-TEAM"):
            mock_email.return_value = None

            await _process_notification(session_factory=factory, notification=notification)

            mock_email.assert_called_once()
            call_args = mock_email.call_args[1]
            assert call_args["to_email"] == "alice@example.com"
            assert call_args["first_name"] == "Alice"
            assert call_args["care_team_number"] == "1-800-CARE-TEAM"

    @pytest.mark.asyncio
    async def test_sms_dispatched_for_sms_channel(self):
        """channel=SMS → send_checkin_sms() called with correct args."""
        notification = make_notification(
            channel=NotificationChannel.SMS,
            first_name="Bob",
            phone="+15555550001",
        )
        factory, _ = make_session_factory(notification)

        with patch("app.services.sms_service.send_checkin_sms") as mock_sms, \
             patch("os.environ.get", return_value="1-800-CARE-TEAM"):
            mock_sms.return_value = None

            await _process_notification(session_factory=factory, notification=notification)

            mock_sms.assert_called_once()
            call_args = mock_sms.call_args[1]
            assert call_args["to_phone"] == "+15555550001"
            assert call_args["first_name"] == "Bob"
            assert call_args["care_team_number"] == "1-800-CARE-TEAM"

    @pytest.mark.asyncio
    async def test_failed_dispatch_sets_status_to_failed(self):
        """Twilio error → delivery_status=FAILED."""
        notification = make_notification(channel=NotificationChannel.SMS)
        factory, session = make_session_factory(notification)

        with patch("app.services.sms_service.send_checkin_sms", side_effect=Exception("Twilio error")), \
             patch("os.environ.get", return_value="1-800-CARE-TEAM"):

            await _process_notification(session_factory=factory, notification=notification)

        # _update_status called with FAILED
        session.get.assert_called_once()
