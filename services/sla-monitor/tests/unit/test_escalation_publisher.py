"""Unit tests for EscalationPublisher idempotency.

US-021 Technical Notes: only one escalation per (encounter_id, agent_type, breach_window).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock, patch

import pytest

from app.config.sla_loader import load_sla_config
from app.publisher.escalation_publisher import EscalationPublisher


@pytest.fixture
def valid_config_yaml(tmp_path: Path) -> Path:
    content = dedent("""\
        sla_thresholds:
          DOCUMENTATION: 30
          MEDICATION_RECONCILIATION: 60
          BED_MANAGEMENT: 15
          FOLLOW_UP_CARE: 120
          PATIENT_COMMUNICATION: 30
        monitor_interval_seconds: 300
        escalation_dedup_window_minutes: 30
    """)
    p = tmp_path / "sla_config.yaml"
    p.write_text(content)
    return p


@pytest.fixture
def publisher(valid_config_yaml: Path) -> EscalationPublisher:
    load_sla_config.cache_clear()
    with patch("app.publisher.escalation_publisher.pubsub_v1.PublisherClient"):
        with patch("app.publisher.escalation_publisher.load_sla_config") as mock_load:
            mock_load.return_value = load_sla_config(valid_config_yaml)
            return EscalationPublisher(project_id="test-project")


@pytest.mark.asyncio
async def test_publish_sends_message(publisher: EscalationPublisher) -> None:
    """First publish call sends a message."""
    publisher._publisher.publish = MagicMock(
        return_value=MagicMock(result=MagicMock(return_value="msg-001"))
    )
    await publisher.publish(
        encounter_id=uuid.uuid4(),
        agent_type="DOCUMENTATION",
        minutes_elapsed=31,
        supervisor_id=uuid.uuid4(),
    )
    publisher._publisher.publish.assert_called_once()


@pytest.mark.asyncio
async def test_duplicate_publish_suppressed_within_window(publisher: EscalationPublisher) -> None:
    """Second publish call for same key within dedup window is suppressed."""
    enc_id = uuid.uuid4()
    sup_id = uuid.uuid4()

    publisher._publisher.publish = MagicMock(
        return_value=MagicMock(result=MagicMock(return_value="msg-001"))
    )

    await publisher.publish(enc_id, "DOCUMENTATION", 31, sup_id)
    await publisher.publish(enc_id, "DOCUMENTATION", 32, sup_id)  # duplicate

    assert publisher._publisher.publish.call_count == 1


@pytest.mark.asyncio
async def test_different_agent_types_not_deduplicated(publisher: EscalationPublisher) -> None:
    """Different agent types for the same encounter are not deduplicated."""
    enc_id = uuid.uuid4()
    sup_id = uuid.uuid4()

    publisher._publisher.publish = MagicMock(
        return_value=MagicMock(result=MagicMock(return_value="msg-001"))
    )

    await publisher.publish(enc_id, "DOCUMENTATION", 31, sup_id)
    await publisher.publish(enc_id, "BED_MANAGEMENT", 16, sup_id)

    assert publisher._publisher.publish.call_count == 2


@pytest.mark.asyncio
async def test_breach_window_bucket_calculation(publisher: EscalationPublisher) -> None:
    """Breach window bucket groups timestamps into dedup windows."""
    # dedup_window = 30 minutes
    # Bucket boundaries: [10:30-10:59], [11:00-11:29], [11:30-11:59]
    ts1 = datetime(2024, 1, 1, 10, 47, tzinfo=timezone.utc)  # bucket [10:30-10:59]
    ts2 = datetime(2024, 1, 1, 10, 55, tzinfo=timezone.utc)  # same bucket [10:30-10:59]
    ts3 = datetime(2024, 1, 1, 11, 5, tzinfo=timezone.utc)   # different bucket [11:00-11:29]

    bucket1 = publisher._breach_window_bucket(ts1)
    bucket2 = publisher._breach_window_bucket(ts2)
    bucket3 = publisher._breach_window_bucket(ts3)

    assert bucket1 == bucket2  # within same 30-minute window
    assert bucket1 != bucket3  # different 30-minute window


@pytest.mark.asyncio
async def test_failed_publish_does_not_mark_as_sent(publisher: EscalationPublisher) -> None:
    """Failed publish does not add key to _published_keys, allowing retry."""
    enc_id = uuid.uuid4()
    sup_id = uuid.uuid4()

    publisher._publisher.publish = MagicMock(
        return_value=MagicMock(result=MagicMock(side_effect=Exception("Pub/Sub error")))
    )

    with pytest.raises(Exception):
        await publisher.publish(enc_id, "DOCUMENTATION", 31, sup_id)

    # Second attempt should NOT be suppressed (first publish didn't mark key as sent)
    publisher._publisher.publish = MagicMock(
        return_value=MagicMock(result=MagicMock(return_value="msg-002"))
    )
    await publisher.publish(enc_id, "DOCUMENTATION", 32, sup_id)

    # Should have called publish on the retry since first failed
    assert publisher._publisher.publish.call_count == 1
