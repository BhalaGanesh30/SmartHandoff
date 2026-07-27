"""Unit tests for SignalRBroadcaster.

Tests mock httpx.AsyncClient — no live Azure SignalR calls.
Coverage targets:
  - Correct group names constructed (US-022 DoD naming convention)
  - HTTP error logged as WARNING; no exception raised to caller
  - Connection string parse errors raise ValueError
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from app.signalr.broadcaster import SignalRBroadcaster, _parse_connection_string
from app.signalr.schemas import TaskUpdatedPayload


VALID_CONN_STR = (
    "Endpoint=https://test.service.signalr.net;"
    "AccessKey=dGVzdGtleQ==;"
    "Version=1.0"
)


def _make_payload(**kwargs) -> TaskUpdatedPayload:
    defaults = dict(
        task_id=uuid4(),
        encounter_id=uuid4(),
        unit_id="3A",
        role_name="pharmacist",
        agent_type="MEDICATION_RECONCILIATION",
        previous_status="IN_PROGRESS",
        new_status="COMPLETED",
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return TaskUpdatedPayload(**defaults)


class TestParseConnectionString:
    def test_valid_connection_string_returns_endpoint_and_key(self):
        endpoint, key = _parse_connection_string(VALID_CONN_STR)
        assert endpoint == "https://test.service.signalr.net"
        assert key == "dGVzdGtleQ=="

    def test_missing_access_key_raises_value_error(self):
        with pytest.raises(ValueError, match="AccessKey"):
            _parse_connection_string("Endpoint=https://test.service.signalr.net;Version=1.0")

    def test_missing_endpoint_raises_value_error(self):
        with pytest.raises(ValueError, match="Endpoint"):
            _parse_connection_string("AccessKey=abc;Version=1.0")


class TestSignalRBroadcaster:
    @pytest.mark.asyncio
    async def test_broadcast_calls_three_groups(self):
        """Verifies encounter-, unit-, and role- groups all receive a POST."""
        broadcaster = SignalRBroadcaster(VALID_CONN_STR)
        payload = _make_payload()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(broadcaster._client, "post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await broadcaster.broadcast_task_updated(payload)

        assert mock_post.call_count == 3
        urls = [call.args[0] for call in mock_post.call_args_list]
        assert any(f"encounter-{payload.encounter_id}" in u for u in urls)
        assert any("unit-3A" in u for u in urls)
        assert any("role-pharmacist" in u for u in urls)
        await broadcaster.aclose()

    @pytest.mark.asyncio
    async def test_http_error_logged_not_raised(self, caplog):
        """HTTP 500 from Azure SignalR is logged as WARNING — caller is not interrupted."""
        import httpx
        broadcaster = SignalRBroadcaster(VALID_CONN_STR)
        payload = _make_payload()

        error_response = MagicMock(status_code=500)
        http_error = httpx.HTTPStatusError("500", request=MagicMock(), response=error_response)

        with patch.object(broadcaster._client, "post", new=AsyncMock(side_effect=http_error)):
            with caplog.at_level("WARNING", logger="app.signalr.broadcaster"):
                await broadcaster.broadcast_task_updated(payload)  # must not raise

        assert "SignalR broadcast HTTP error" in caplog.text
        await broadcaster.aclose()

    @pytest.mark.asyncio
    async def test_request_error_logged_not_raised(self, caplog):
        """Network errors are logged as WARNING — caller is not interrupted."""
        import httpx
        broadcaster = SignalRBroadcaster(VALID_CONN_STR)
        payload = _make_payload()

        request_error = httpx.RequestError("Connection timeout")

        with patch.object(broadcaster._client, "post", new=AsyncMock(side_effect=request_error)):
            with caplog.at_level("WARNING", logger="app.signalr.broadcaster"):
                await broadcaster.broadcast_task_updated(payload)  # must not raise

        assert "SignalR broadcast request error" in caplog.text
        await broadcaster.aclose()
