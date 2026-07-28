"""Unit tests for HousekeepingNotifier (notifier.py).

Coverage:
  Payload structure (deterministic idempotency key with SHA-256)
  Idempotency key determinism (same input → same key)
  Pub/Sub publish with 5-second timeout
  Exception-safe (failures logged but not raised)
  Read replica for bed coordinates

Design refs:
    US-035 TASK-006 — Unit test coverage for notifier.py
    US-035 TASK-004 — HousekeepingNotifier implementation
"""
from __future__ import annotations

import hashlib
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from app.agents.bed_management.notifier import HousekeepingNotifier
from app.agents.bed_management.schemas import HousekeepingNotificationPayload
from app.models.bed import Bed


@pytest.fixture
def mock_bed():
    """Mock Bed ORM object."""
    bed = MagicMock(spec=Bed)
    bed.id = uuid4()
    bed.unit = "3A"
    bed.room = "301"
    bed.bed_number = "A"
    return bed


@pytest.fixture
def mock_session_factory(mock_bed):
    """Factory returning an AsyncMock session with a bed record."""
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_bed
    session.execute.return_value = execute_result

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


@pytest.fixture
def mock_pubsub_client():
    """Mock Google Cloud Pub/Sub PublisherClient."""
    client = MagicMock()
    future = MagicMock()
    future.result.return_value = "message-id-123"
    client.publish.return_value = future
    return client


@pytest.fixture
def notifier(mock_pubsub_client, mock_session_factory):
    """HousekeepingNotifier with mocked dependencies."""
    return HousekeepingNotifier(
        pubsub_client=mock_pubsub_client,
        project_id="test-project",
        read_session_factory=mock_session_factory,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Payload structure
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notify_publishes_correct_payload_structure(
    notifier, mock_pubsub_client, mock_bed
):
    """Notification payload contains unit, room, bed_number, encounter_id."""
    bed_id = str(mock_bed.id)
    encounter_id = str(uuid4())
    
    await notifier.notify(bed_id=bed_id, encounter_id=encounter_id)
    
    # Verify publish was called
    assert mock_pubsub_client.publish.called
    call_args = mock_pubsub_client.publish.call_args
    
    # Extract published JSON
    published_data = call_args[0][1]  # Second positional arg is data
    payload = json.loads(published_data)
    
    assert payload["unit"] == "3A"
    assert payload["room"] == "301"
    assert payload["bed_number"] == "A"
    assert payload["encounter_id"] == encounter_id


# ──────────────────────────────────────────────────────────────────────────────
# Idempotency key determinism
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idempotency_key_is_deterministic(notifier, mock_pubsub_client, mock_bed):
    """Same bed_id + encounter_id produces the same SHA-256 idempotency key."""
    bed_id = str(mock_bed.id)
    encounter_id = str(uuid4())
    
    # First notification
    await notifier.notify(bed_id=bed_id, encounter_id=encounter_id)
    first_call_attrs = mock_pubsub_client.publish.call_args[1]  # kwargs
    first_key = first_call_attrs["idempotency_key"]
    
    # Reset mock
    mock_pubsub_client.reset_mock()
    
    # Second notification with same inputs
    await notifier.notify(bed_id=bed_id, encounter_id=encounter_id)
    second_call_attrs = mock_pubsub_client.publish.call_args[1]
    second_key = second_call_attrs["idempotency_key"]
    
    assert first_key == second_key
    
    # Verify it's truncated SHA-256 hash (32 hex chars, not 64)
    assert len(first_key) == 32


@pytest.mark.asyncio
async def test_idempotency_key_sha256_format(notifier, mock_pubsub_client, mock_bed):
    """Idempotency key is truncated SHA-256 hash (32 chars) of bed_id + encounter_id."""
    bed_id = str(mock_bed.id)
    encounter_id = str(uuid4())
    
    await notifier.notify(bed_id=bed_id, encounter_id=encounter_id)
    
    call_attrs = mock_pubsub_client.publish.call_args[1]
    idempotency_key = call_attrs["idempotency_key"]
    
    # Manually compute expected hash (truncated to 32 chars)
    expected_hash = hashlib.sha256(f"{bed_id}:{encounter_id}".encode()).hexdigest()[:32]
    assert idempotency_key == expected_hash


# ──────────────────────────────────────────────────────────────────────────────
# Pub/Sub publish with timeout
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_timeout_is_5_seconds(notifier, mock_pubsub_client):
    """Pub/Sub publish future.result() is called with 5-second timeout."""
    bed_id = str(uuid4())
    encounter_id = str(uuid4())
    
    await notifier.notify(bed_id=bed_id, encounter_id=encounter_id)
    
    future = mock_pubsub_client.publish.return_value
    future.result.assert_called_once_with(timeout=5)


# ──────────────────────────────────────────────────────────────────────────────
# Exception safety
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notify_is_exception_safe_on_publish_failure(
    notifier, mock_pubsub_client, mock_bed
):
    """Pub/Sub publish failures are logged but do not raise."""
    bed_id = str(mock_bed.id)
    encounter_id = str(uuid4())
    
    # Simulate publish timeout
    future = mock_pubsub_client.publish.return_value
    future.result.side_effect = TimeoutError("Pub/Sub timeout")
    
    # Should not raise
    await notifier.notify(bed_id=bed_id, encounter_id=encounter_id)


@pytest.mark.asyncio
async def test_notify_is_exception_safe_on_bed_not_found(notifier, mock_session_factory):
    """Bed not found in DB is logged but does not raise."""
    bed_id = str(uuid4())
    encounter_id = str(uuid4())
    
    # Simulate bed not found
    session = mock_session_factory.return_value.__aenter__.return_value
    execute_result = session.execute.return_value
    execute_result.scalar_one_or_none.return_value = None
    
    # Should not raise
    await notifier.notify(bed_id=bed_id, encounter_id=encounter_id)


# ──────────────────────────────────────────────────────────────────────────────
# Read replica usage
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notify_uses_read_replica_for_bed_coordinates(
    notifier, mock_session_factory, mock_bed
):
    """Bed coordinates (unit, room, bed_number) are fetched from read replica."""
    bed_id = str(mock_bed.id)
    encounter_id = str(uuid4())
    
    await notifier.notify(bed_id=bed_id, encounter_id=encounter_id)
    
    # Verify session was used (read replica factory)
    session = mock_session_factory.return_value.__aenter__.return_value
    assert session.execute.called


# ──────────────────────────────────────────────────────────────────────────────
# Message attributes
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_includes_message_attributes(notifier, mock_pubsub_client, mock_bed):
    """Pub/Sub message includes attributes for filtering (notification_type, idempotency_key)."""
    bed_id = str(mock_bed.id)
    encounter_id = str(uuid4())
    
    await notifier.notify(bed_id=bed_id, encounter_id=encounter_id)
    
    call_kwargs = mock_pubsub_client.publish.call_args[1]
    
    # Check attributes dict exists and contains required keys
    assert "notification_type" in call_kwargs
    assert call_kwargs["notification_type"] == "HOUSEKEEPING_REQUIRED"
    assert "idempotency_key" in call_kwargs
