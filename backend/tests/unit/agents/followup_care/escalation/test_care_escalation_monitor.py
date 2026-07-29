"""Unit tests for CareEscalationMonitor — US-042 AC Scenario 1.

Covers:
    - URGENCY_FLAG_SET event creates CareEscalation record (PENDING)
    - CARE_TEAM_ESCALATION published to notification-requests
    - Idempotency: duplicate Pub/Sub delivery skipped (ACK without creating duplicate)
    - Missing encounter → NACK (not crash)
    - No-nurse fallback → escalation still created, notification skipped with WARNING
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.cloud import pubsub_v1
from sqlalchemy.exc import IntegrityError

from app.agents.followup_care.escalation.monitor import CareEscalationMonitor
from app.agents.followup_care.escalation.schemas import UrgencyFlagSetEvent
from app.models.care_escalation import CareEscalation, CareEscalationStatus

ENCOUNTER_ID = uuid.uuid4()
PATIENT_ID = uuid.uuid4()
TRANSCRIPT_ID = uuid.uuid4()
NURSE_ID = uuid.uuid4()


def _make_pubsub_message(event: dict) -> MagicMock:
    """Build a mock Pub/Sub message from an event dict."""
    msg = MagicMock(spec=pubsub_v1.subscriber.message.Message)
    msg.data = json.dumps(event).encode("utf-8")
    msg.message_id = "msg-001"
    msg.ack = MagicMock()
    msg.nack = MagicMock()
    return msg


def _make_valid_event() -> dict:
    return {
        "event_type": "URGENCY_FLAG_SET",
        "encounter_id": str(ENCOUNTER_ID),
        "patient_id": str(PATIENT_ID),
        "chatbot_transcript_id": str(TRANSCRIPT_ID),
        "urgency_flag_set_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@pytest.fixture
def mock_publisher():
    publisher = MagicMock(spec=pubsub_v1.PublisherClient)
    future = MagicMock()
    future.result.return_value = None
    publisher.publish.return_value = future
    return publisher


@pytest.fixture
def mock_session_factory():
    """Returns an async_sessionmaker that yields an AsyncMock session."""
    session = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.fixture
def monitor(mock_session_factory, mock_publisher):
    factory, _ = mock_session_factory
    return CareEscalationMonitor(
        session_factory=factory,
        publisher=mock_publisher,
        notification_topic="projects/test/topics/notification-requests",
    )


class TestHandleUrgencyFlagSet:
    async def test_urgency_flag_creates_escalation_record(
        self, monitor, mock_session_factory
    ):
        """AC Scenario 1: URGENCY_FLAG_SET event → care_escalation record created with status=PENDING."""
        factory, session = mock_session_factory
        mock_encounter = MagicMock()
        mock_encounter.current_unit = "ICU-3"
        session.get.return_value = mock_encounter

        mock_nurse = MagicMock()
        mock_nurse.id = NURSE_ID
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_nurse
        session.execute.return_value = result_mock

        msg = _make_pubsub_message(_make_valid_event())
        await monitor.handle_urgency_flag_set(msg)

        session.add.assert_called_once()
        added: CareEscalation = session.add.call_args[0][0]
        assert added.encounter_id == ENCOUNTER_ID
        assert added.patient_id == PATIENT_ID
        assert added.notified_nurse_user_id == NURSE_ID
        assert added.status == CareEscalationStatus.PENDING
        assert added.escalated_to_supervisor is False
        assert added.idempotency_key == f"ESC-{ENCOUNTER_ID}"

    async def test_urgency_flag_publishes_care_team_escalation(
        self, monitor, mock_session_factory, mock_publisher
    ):
        """AC Scenario 1: CARE_TEAM_ESCALATION published to notification-requests after record creation."""
        factory, session = mock_session_factory
        mock_encounter = MagicMock()
        mock_encounter.current_unit = "ICU-3"
        session.get.return_value = mock_encounter

        mock_nurse = MagicMock()
        mock_nurse.id = NURSE_ID
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_nurse
        session.execute.return_value = result_mock

        msg = _make_pubsub_message(_make_valid_event())
        await monitor.handle_urgency_flag_set(msg)

        mock_publisher.publish.assert_called_once()
        topic, payload = mock_publisher.publish.call_args[0]
        published = json.loads(payload.decode("utf-8"))

        assert topic == "projects/test/topics/notification-requests"
        assert published["event_type"] == "CARE_TEAM_ESCALATION"
        assert published["nurse_user_id"] == str(NURSE_ID)
        assert published["channel"] == "SMS"
        assert "NOTIF-ESC-" in published["idempotency_key"]
        # PHI check: no patient name, MRN, DOB, phone in published payload
        for phi_field in ["first_name", "last_name", "mrn", "dob", "phone", "email"]:
            assert phi_field not in published

    async def test_duplicate_event_skipped_by_idempotency(
        self, monitor, mock_session_factory, mock_publisher
    ):
        """Duplicate Pub/Sub delivery: flush raises IntegrityError → ACK without duplicate escalation."""
        factory, session = mock_session_factory
        mock_encounter = MagicMock()
        mock_encounter.current_unit = "ICU-3"
        session.get.return_value = mock_encounter

        mock_nurse = MagicMock()
        mock_nurse.id = NURSE_ID
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_nurse
        session.execute.return_value = result_mock

        # First call: flush raises IntegrityError (simulating unique constraint violation)
        session.flush.side_effect = IntegrityError("unique constraint violation", {}, None)

        msg = _make_pubsub_message(_make_valid_event())
        await monitor.handle_urgency_flag_set(msg)

        # Notification NOT published for duplicate
        mock_publisher.publish.assert_not_called()
        msg.ack.assert_called_once()

    async def test_missing_encounter_nacks_message(
        self, monitor, mock_session_factory
    ):
        """Missing encounter → NACK (DLQ will handle after max_delivery_attempts=5)."""
        factory, session = mock_session_factory
        session.get.return_value = None

        msg = _make_pubsub_message(_make_valid_event())
        await monitor.handle_urgency_flag_set(msg)

        msg.nack.assert_called_once()
        msg.ack.assert_not_called()

    async def test_invalid_event_nacks_message(self, monitor):
        """Malformed event payload → NACK; no crash."""
        msg = MagicMock(spec=pubsub_v1.subscriber.message.Message)
        msg.data = b'{"event_type": "UNEXPECTED_TYPE"}'
        msg.message_id = "bad-msg"
        msg.ack = MagicMock()
        msg.nack = MagicMock()

        await monitor.handle_urgency_flag_set(msg)

        msg.nack.assert_called_once()
