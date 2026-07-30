"""Unit tests for maybe_schedule_48h_checkin().

Coverage: US-041 AC Scenarios 1, 2, 3 — schedule creation, risk threshold,
channel resolution, send_at accuracy, idempotency guard.

Design refs:
    US-041 AC Scenario 1 — CHECK_IN_48H scheduled for risk_score=0.6
    US-041 AC Scenario 2 — NOT scheduled for risk_score=0.2
    US-041 Technical Notes — CHECKIN_RISK_THRESHOLD=0.5; send_at from discharge_time
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.agents.followup_care.checkin_scheduler import (
    CHECKIN_DELAY_HOURS,
    CHECKIN_RISK_THRESHOLD,
    maybe_schedule_48h_checkin,
)
from app.models.scheduled_notification import (
    DeliveryStatus,
    NotificationChannel,
    NotificationType,
)


@pytest.fixture()
def discharge_time() -> datetime:
    return datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def mock_encounter(discharge_time):
    enc = MagicMock()
    enc.id = uuid.uuid4()
    enc.discharge_time = discharge_time
    return enc


@pytest.fixture()
def mock_patient_sms():
    """Patient with preferred_contact=sms and opt_out=False."""
    p = MagicMock()
    p.id = uuid.uuid4()
    p.preferred_contact = "sms"
    p.notification_opt_out = False
    return p


@pytest.fixture()
def mock_patient_email():
    """Patient with preferred_contact=email and opt_out=False."""
    p = MagicMock()
    p.id = uuid.uuid4()
    p.preferred_contact = "email"
    p.notification_opt_out = False
    return p


@pytest.fixture()
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


# ─── Risk Threshold Tests ──────────────────────────────────────────────────────

class TestRiskThreshold:
    @pytest.mark.asyncio
    async def test_checkin_created_for_medium_risk(self, mock_session, mock_encounter, mock_patient_sms):
        """risk_score=0.6 (MEDIUM) → ScheduledNotification created (AC Scenario 1)."""
        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=mock_patient_sms,
            risk_score=0.6,
        )
        assert result is not None
        assert result.type == NotificationType.CHECK_IN_48H
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkin_created_for_high_risk(self, mock_session, mock_encounter, mock_patient_sms):
        """risk_score=0.8 (HIGH) → ScheduledNotification created."""
        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=mock_patient_sms,
            risk_score=0.8,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_checkin_not_created_for_low_risk(self, mock_session, mock_encounter, mock_patient_sms):
        """risk_score=0.2 (LOW) → no ScheduledNotification (AC Scenario 2)."""
        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=mock_patient_sms,
            risk_score=0.2,
        )
        assert result is None
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_checkin_not_created_just_below_threshold(self, mock_session, mock_encounter, mock_patient_sms):
        """risk_score=0.499 (just below threshold) → no ScheduledNotification."""
        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=mock_patient_sms,
            risk_score=0.499,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_checkin_created_at_exact_threshold(self, mock_session, mock_encounter, mock_patient_sms):
        """risk_score=0.5 (exactly at threshold) → ScheduledNotification created."""
        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=mock_patient_sms,
            risk_score=0.5,
        )
        assert result is not None


# ─── send_at Accuracy Tests ────────────────────────────────────────────────────

class TestSendAtComputation:
    @pytest.mark.asyncio
    async def test_send_at_is_48h_after_discharge(self, mock_session, mock_encounter, mock_patient_sms, discharge_time):
        """send_at = encounter.discharge_time + 48h (not datetime.now() + 48h)."""
        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=mock_patient_sms,
            risk_score=0.7,
        )
        expected_send_at = discharge_time + timedelta(hours=CHECKIN_DELAY_HOURS)
        assert result.send_at == expected_send_at

    @pytest.mark.asyncio
    async def test_no_record_when_discharge_time_is_none(self, mock_session, mock_patient_sms):
        """If encounter.discharge_time is None, no notification is created."""
        enc = MagicMock()
        enc.id = uuid.uuid4()
        enc.discharge_time = None

        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=enc,
            patient=mock_patient_sms,
            risk_score=0.8,
        )
        assert result is None
        mock_session.add.assert_not_called()


# ─── Channel Resolution Tests ──────────────────────────────────────────────────

class TestChannelResolution:
    @pytest.mark.asyncio
    async def test_channel_email_for_email_preference(self, mock_session, mock_encounter, mock_patient_email):
        """patient.preferred_contact=email → channel=EMAIL (AC Scenario 3)."""
        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=mock_patient_email,
            risk_score=0.6,
        )
        assert result.channel == NotificationChannel.EMAIL

    @pytest.mark.asyncio
    async def test_channel_sms_for_sms_preference(self, mock_session, mock_encounter, mock_patient_sms):
        """patient.preferred_contact=sms → channel=SMS."""
        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=mock_patient_sms,
            risk_score=0.6,
        )
        assert result.channel == NotificationChannel.SMS

    @pytest.mark.asyncio
    async def test_channel_sms_when_preferred_contact_is_none(self, mock_session, mock_encounter):
        """patient.preferred_contact=None → default to SMS."""
        patient = MagicMock()
        patient.id = uuid.uuid4()
        patient.preferred_contact = None
        patient.notification_opt_out = False

        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=patient,
            risk_score=0.6,
        )
        assert result.channel == NotificationChannel.SMS


# ─── Idempotency Tests ─────────────────────────────────────────────────────────

class TestIdempotency:
    @pytest.mark.asyncio
    async def test_idempotency_key_format(self, mock_session, mock_encounter, mock_patient_sms):
        """idempotency_key = CHK48-{encounter.id}."""
        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=mock_patient_sms,
            risk_score=0.6,
        )
        assert result.idempotency_key == f"CHK48-{mock_encounter.id}"

    @pytest.mark.asyncio
    async def test_returns_none_on_unique_constraint_violation(self, mock_session, mock_encounter, mock_patient_sms):
        """Flush raising IntegrityError (unique constraint) → returns None (already scheduled)."""
        mock_session.flush.side_effect = IntegrityError("unique constraint", None, None)

        result = await maybe_schedule_48h_checkin(
            session=mock_session,
            encounter=mock_encounter,
            patient=mock_patient_sms,
            risk_score=0.6,
        )
        assert result is None
        mock_session.rollback.assert_called_once()
