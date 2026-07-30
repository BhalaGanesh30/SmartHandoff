"""Unit tests for BoardingAlertPublisher — Pub/Sub dispatch and idempotency.

Covers:
    dispatch_alerts — skips already_alerted candidates (in-memory idempotency)
    _publish_single — builds correct payload; publishes to Pub/Sub with IMMEDIATE priority
    _publish_single — does NOT write boarding_alert_sent_at if Pub/Sub fails
    _publish_single — DB UPDATE WHERE boarding_alert_sent_at IS NULL (DB-level idempotency)
    _publish_single — no PHI in payload

Design refs:
    US-038 TASK-005 — Unit test coverage for boarding alert workflow
    US-038 AC Scenario 1 — priority=IMMEDIATE, all required fields
    US-038 AC Scenario 4 — idempotency enforcement
"""
from __future__ import annotations

import json
from concurrent.futures import Future
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.agents.bed_management.boarding_publisher import BoardingAlertPublisher
from app.agents.bed_management.boarding_schemas import BoardingCandidate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(
    *,
    encounter_id: str | None = None,
    patient_id: str | None = None,
    minutes_elapsed: int = 125,
    already_alerted: bool = False,
) -> BoardingCandidate:
    """Create BoardingCandidate for testing."""
    now = datetime.now(UTC)
    sent_at = now - timedelta(minutes=5) if already_alerted else None
    return BoardingCandidate(
        encounter_id=str(encounter_id or uuid4()),
        patient_id=str(patient_id or uuid4()),
        ed_arrival_time=now - timedelta(minutes=minutes_elapsed),
        minutes_elapsed=minutes_elapsed,
        target_unit="3-WEST",
        boarding_alert_sent_at=sent_at,
        current_location="ED",
    )


def _make_publisher(pubsub_client=None, session=None):
    """Create BoardingAlertPublisher with mocked dependencies."""
    if session is None:
        session = AsyncMock()
        session.execute.return_value.rowcount = 1

    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    if pubsub_client is None:
        pubsub_client = MagicMock()
        future = Future()
        future.set_result("msg-id-123")
        pubsub_client.publish.return_value = future

    return BoardingAlertPublisher(
        pubsub_client=pubsub_client,
        db_session_factory=session_factory,
        project_id="test-project",
        topic_path="projects/test-project/topics/notification-requests",
    ), session, pubsub_client


# ---------------------------------------------------------------------------
# dispatch_alerts() — in-memory idempotency
# ---------------------------------------------------------------------------

class TestBoardingAlertPublisherIdempotency:
    @pytest.mark.asyncio
    async def test_dispatch_skips_already_alerted_candidate(self):
        """Candidate with already_alerted=True must not be published."""
        publisher, _, client = _make_publisher()
        candidate = _make_candidate(already_alerted=True)

        await publisher.dispatch_alerts([candidate])

        client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_publishes_unalerted_candidate(self):
        """Candidate with already_alerted=False triggers publish."""
        publisher, _, client = _make_publisher()
        candidate = _make_candidate(already_alerted=False)

        await publisher.dispatch_alerts([candidate])

        client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_update_not_called_when_pubsub_fails(self):
        """If Pub/Sub raises, boarding_alert_sent_at must NOT be written."""
        mock_client = MagicMock()
        failing_future = Future()
        failing_future.set_exception(Exception("Pub/Sub unavailable"))
        mock_client.publish.return_value = failing_future

        mock_session = AsyncMock()
        publisher, _, _ = _make_publisher(pubsub_client=mock_client, session=mock_session)
        candidate = _make_candidate(already_alerted=False)

        await publisher.dispatch_alerts([candidate])

        # commit() must not be called — no DB write on Pub/Sub failure
        mock_session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# _publish_single() — payload structure
# ---------------------------------------------------------------------------

class TestBoardingAlertPayload:
    @pytest.mark.asyncio
    async def test_payload_includes_priority_immediate(self):
        """Pub/Sub attributes must include priority=IMMEDIATE."""
        publisher, _, client = _make_publisher()
        candidate = _make_candidate()

        await publisher.dispatch_alerts([candidate])

        call_kwargs = client.publish.call_args.kwargs
        assert call_kwargs.get("priority") == "IMMEDIATE"

    @pytest.mark.asyncio
    async def test_payload_contains_no_phi_fields(self):
        """Payload must not contain PHI fields (name, DOB, MRN, phone, email)."""
        publisher, _, client = _make_publisher()
        candidate = _make_candidate()

        await publisher.dispatch_alerts([candidate])

        data_bytes = client.publish.call_args.args[1]
        payload = json.loads(data_bytes.decode())
        phi_fields = {"first_name", "last_name", "dob", "mrn", "phone", "email", "ssn"}
        assert not phi_fields.intersection(payload.keys()), (
            f"PHI fields found in boarding alert payload: {phi_fields.intersection(payload.keys())}"
        )

    @pytest.mark.asyncio
    async def test_payload_minutes_elapsed_at_least_120(self):
        """Payload minutes_elapsed must be ≥120 per Pydantic validation."""
        publisher, _, client = _make_publisher()
        candidate = _make_candidate(minutes_elapsed=122)

        await publisher.dispatch_alerts([candidate])

        data_bytes = client.publish.call_args.args[1]
        payload = json.loads(data_bytes.decode())
        assert payload["minutes_elapsed"] >= 120

    @pytest.mark.asyncio
    async def test_idempotency_key_in_message_attributes(self):
        """Pub/Sub attributes must include idempotency_key for downstream dedup."""
        publisher, _, client = _make_publisher()
        candidate = _make_candidate(encounter_id="enc-special-001")

        await publisher.dispatch_alerts([candidate])

        call_kwargs = client.publish.call_args.kwargs
        assert "idempotency_key" in call_kwargs
        assert call_kwargs["idempotency_key"].startswith("boarding:enc-special-001:")

    @pytest.mark.asyncio
    async def test_payload_includes_all_required_fields(self):
        """Payload must include all 7 required fields from AC Scenario 1."""
        publisher, _, client = _make_publisher()
        candidate = _make_candidate()

        await publisher.dispatch_alerts([candidate])

        data_bytes = client.publish.call_args.args[1]
        payload = json.loads(data_bytes.decode())
        
        required_fields = [
            "notification_type",
            "priority",
            "patient_id",
            "encounter_id",
            "ed_arrival_time",
            "minutes_elapsed",
            "idempotency_key",
        ]
        for field in required_fields:
            assert field in payload, f"Missing required field: {field}"


# ---------------------------------------------------------------------------
# _publish_single() — DB-level idempotency
# ---------------------------------------------------------------------------

class TestDBLevelIdempotency:
    @pytest.mark.asyncio
    async def test_db_update_uses_where_sent_at_is_null(self):
        """DB UPDATE must include WHERE boarding_alert_sent_at IS NULL."""
        mock_session = AsyncMock()
        mock_session.execute.return_value.rowcount = 1
        
        publisher, _, _ = _make_publisher(session=mock_session)
        candidate = _make_candidate()

        await publisher.dispatch_alerts([candidate])

        # Verify session.execute was called with UPDATE statement
        mock_session.execute.assert_called_once()
        update_stmt = mock_session.execute.call_args.args[0]
        # Check WHERE clause contains boarding_alert_sent_at IS NULL check
        compiled = str(update_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "boarding_alert_sent_at IS NULL" in compiled or "is_(None)" in str(update_stmt)

    @pytest.mark.asyncio
    async def test_concurrent_write_detection(self):
        """If rowcount=0, log that another instance already wrote timestamp."""
        mock_session = AsyncMock()
        mock_session.execute.return_value.rowcount = 0  # Concurrent write
        
        publisher, _, _ = _make_publisher(session=mock_session)
        candidate = _make_candidate()

        # Should not raise; logs "already set by concurrent instance"
        await publisher.dispatch_alerts([candidate])

        mock_session.commit.assert_called_once()  # Still commits (no-op)
