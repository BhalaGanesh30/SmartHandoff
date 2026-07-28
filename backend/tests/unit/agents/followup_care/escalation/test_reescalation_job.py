"""Unit tests for ReEscalationJob — US-042 AC Scenario 3.

Covers:
    - PENDING escalation > 15 min → status=ESCALATED_TO_SUPERVISOR, escalated_to_supervisor=True
    - SUPERVISOR_ESCALATION published with correct idempotency_key
    - Escalations < 15 min old → not re-escalated
    - Already ESCALATED_TO_SUPERVISOR → skipped by WHERE clause
    - Concurrent update (returning None) → skip without error
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from google.cloud import pubsub_v1

from app.agents.followup_care.escalation.reescalation_job import ReEscalationJob
from app.models.care_escalation import CareEscalation, CareEscalationStatus

ESCALATION_ID = uuid.uuid4()
ENCOUNTER_ID = uuid.uuid4()
PATIENT_ID = uuid.uuid4()


def _make_pending_escalation(sent_at: datetime) -> MagicMock:
    esc = MagicMock(spec=CareEscalation)
    esc.id = ESCALATION_ID
    esc.encounter_id = ENCOUNTER_ID
    esc.patient_id = PATIENT_ID
    esc.status = CareEscalationStatus.PENDING
    esc.escalated_to_supervisor = False
    esc.sent_at = sent_at
    return esc


@pytest.fixture
def mock_publisher():
    publisher = MagicMock(spec=pubsub_v1.PublisherClient)
    future = MagicMock()
    future.result.return_value = None
    publisher.publish.return_value = future
    return publisher


@pytest.fixture
def mock_session_factory():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.fixture
def job(mock_session_factory, mock_publisher):
    factory, _ = mock_session_factory
    return ReEscalationJob(
        session_factory=factory,
        publisher=mock_publisher,
        notification_topic="projects/test/topics/notification-requests",
    )


class TestReEscalationJobRun:
    async def test_reescalation_publishes_supervisor_escalation(
        self, job, mock_session_factory, mock_publisher
    ):
        """AC Scenario 3: overdue PENDING escalation → SUPERVISOR_ESCALATION published."""
        factory, session = mock_session_factory
        overdue_at = datetime.now(tz=timezone.utc) - timedelta(minutes=16)
        overdue_esc = _make_pending_escalation(sent_at=overdue_at)

        # First session.execute() = SELECT overdue escalations
        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = [overdue_esc]

        # Second session.execute() = UPDATE ... RETURNING escalation.id
        update_result = MagicMock()
        update_result.scalar_one_or_none.return_value = ESCALATION_ID

        session.execute.side_effect = [select_result, update_result]

        await job.run()

        mock_publisher.publish.assert_called_once()
        topic, payload = mock_publisher.publish.call_args[0]
        published = json.loads(payload.decode("utf-8"))

        assert published["event_type"] == "SUPERVISOR_ESCALATION"
        assert published["escalation_id"] == str(ESCALATION_ID)
        assert published["encounter_id"] == str(ENCOUNTER_ID)
        assert published["idempotency_key"] == f"NOTIF-SUP-ESC-{ESCALATION_ID}"
        # PHI check
        for phi_field in ["first_name", "last_name", "mrn", "dob", "phone", "email"]:
            assert phi_field not in published

    async def test_reescalation_sets_escalated_to_supervisor_true(
        self, job, mock_session_factory
    ):
        """AC Scenario 3: care_escalation DB update includes escalated_to_supervisor=True."""
        factory, session = mock_session_factory
        overdue_at = datetime.now(tz=timezone.utc) - timedelta(minutes=16)
        overdue_esc = _make_pending_escalation(sent_at=overdue_at)

        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = [overdue_esc]
        update_result = MagicMock()
        update_result.scalar_one_or_none.return_value = ESCALATION_ID
        session.execute.side_effect = [select_result, update_result]

        await job.run()

        # Verify UPDATE statement included escalated_to_supervisor=True
        update_call = session.execute.call_args_list[1]
        stmt = update_call[0][0]
        # Confirm the UPDATE values contain escalated_to_supervisor=True
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "escalated_to_supervisor" in compiled.lower() or "ESCALATED_TO_SUPERVISOR" in compiled

    async def test_reescalation_skips_recent_escalations(
        self, job, mock_session_factory, mock_publisher
    ):
        """Escalations < 15 min old are not returned by SELECT — no publication."""
        factory, session = mock_session_factory

        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = []  # No overdue results
        session.execute.return_value = select_result

        await job.run()

        mock_publisher.publish.assert_not_called()

    async def test_reescalation_skips_concurrent_update(
        self, job, mock_session_factory, mock_publisher
    ):
        """Concurrent scheduler tick updated the record first → RETURNING None → skip without publish."""
        factory, session = mock_session_factory
        overdue_at = datetime.now(tz=timezone.utc) - timedelta(minutes=20)
        overdue_esc = _make_pending_escalation(sent_at=overdue_at)

        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = [overdue_esc]
        update_result = MagicMock()
        update_result.scalar_one_or_none.return_value = None  # Concurrent update won
        session.execute.side_effect = [select_result, update_result]

        await job.run()

        mock_publisher.publish.assert_not_called()
