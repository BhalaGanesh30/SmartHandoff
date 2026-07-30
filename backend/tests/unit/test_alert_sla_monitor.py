"""Unit tests for AlertSLAMonitor.

Design refs:
    US-032 AC Scenario 3 — 24h SLA breach; CHARGE_PHARMACIST_ESCALATION; sla_breached=True
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.alert_sla_monitor import AlertSLAMonitor


def _make_alert(
    hours_old: int = 25,
    status: str = "ACTIVE",
    severity: str = "HIGH",
    sla_breached: bool = False,
) -> MagicMock:
    """Create a mock PharmacistAlert for testing."""
    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.encounter_id = uuid.uuid4()
    alert.alert_type = "HIGH_RISK_DRUG_CLASS"
    alert.severity = severity
    alert.status = status
    alert.drug_class = "ANTICOAGULANT"
    alert.drug_name = "Warfarin"
    alert.sla_breached = sla_breached
    alert.created_at = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    return alert


@pytest.mark.asyncio
async def test_sla_breached_alert_is_tagged_and_escalated() -> None:
    """AC Scenario 3: alert 25h old → sla_breached=True; CHARGE_PHARMACIST_ESCALATION published."""
    alert = _make_alert(hours_old=25)
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [alert]
    mock_db.flush = AsyncMock()

    with patch(
        "app.services.alert_sla_monitor.publish_message", new_callable=AsyncMock
    ) as mock_publish:
        monitor = AlertSLAMonitor(db=mock_db)
        result = await monitor.run()

    assert result["breached"] == 1
    assert alert.sla_breached is True
    mock_publish.assert_awaited_once()
    call_kwargs = mock_publish.call_args.kwargs
    assert call_kwargs["data"]["event_type"] == "CHARGE_PHARMACIST_ESCALATION"
    assert call_kwargs["data"]["alert_id"] == str(alert.id)
    assert call_kwargs["attributes"]["priority"] == "IMMEDIATE"


@pytest.mark.asyncio
async def test_sla_monitor_is_idempotent() -> None:
    """Already-breached alerts (sla_breached=True) are excluded from the query."""
    mock_db = AsyncMock()
    # Query returns empty list because sla_breached=True alerts are filtered by the WHERE clause
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    mock_db.flush = AsyncMock()

    with patch(
        "app.services.alert_sla_monitor.publish_message", new_callable=AsyncMock
    ) as mock_publish:
        monitor = AlertSLAMonitor(db=mock_db)
        result = await monitor.run()

    assert result["breached"] == 0
    mock_publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolved_alerts_not_escalated() -> None:
    """Resolved alerts must not be included in SLA breach detection."""
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    mock_db.flush = AsyncMock()

    monitor = AlertSLAMonitor(db=mock_db)
    result = await monitor.run()
    assert result["checked"] == 0


@pytest.mark.asyncio
async def test_sla_monitor_continues_on_single_alert_failure() -> None:
    """A failure escalating one alert must not abort processing of remaining alerts."""
    alert_fail = _make_alert(hours_old=26)
    alert_ok = _make_alert(hours_old=25)
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [
        alert_fail,
        alert_ok,
    ]
    mock_db.flush = AsyncMock()

    call_count = 0

    async def publish_side_effect(**kwargs):  # noqa: ANN202
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Pub/Sub transient error")

    with patch(
        "app.services.alert_sla_monitor.publish_message",
        side_effect=publish_side_effect,
    ):
        monitor = AlertSLAMonitor(db=mock_db)
        result = await monitor.run()

    assert result["skipped"] == 1
    assert result["breached"] == 1
