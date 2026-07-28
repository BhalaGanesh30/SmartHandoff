"""Unit tests for BoardingAlertResolver and PATCH beds/{id}/status resolution hook.

Covers:
    resolve_boarding_alert — sets boarding_alert_resolved_at when alert is active
    resolve_boarding_alert — no-op (returns False) when boarding_alert_sent_at IS NULL
    resolve_boarding_alert — idempotent: second call returns False
    resolve_boarding_alert — handles invalid encounter_id format

Design refs:
    US-038 TASK-005 — Unit test coverage for boarding alert workflow
    US-038 AC Scenario 2 — no-op when no alert sent
    US-038 AC Scenario 3 — resolution on RESERVED bed assignment
"""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agents.bed_management.boarding_resolver import resolve_boarding_alert


# ---------------------------------------------------------------------------
# resolve_boarding_alert()
# ---------------------------------------------------------------------------

class TestBoardingAlertResolver:
    @pytest.mark.asyncio
    async def test_resolve_returns_true_when_alert_active(self):
        """When boarding_alert_sent_at IS NOT NULL and resolved_at IS NULL → sets resolved_at."""
        session = AsyncMock()
        session.execute.return_value.rowcount = 1  # one row updated

        result = await resolve_boarding_alert(encounter_id=str(uuid4()), session=session)

        assert result is True
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_returns_false_when_no_alert_sent(self):
        """When boarding_alert_sent_at IS NULL → no-op; returns False."""
        session = AsyncMock()
        session.execute.return_value.rowcount = 0  # WHERE clause excluded the row

        result = await resolve_boarding_alert(encounter_id=str(uuid4()), session=session)

        assert result is False

    @pytest.mark.asyncio
    async def test_resolve_idempotent_on_double_call(self):
        """Calling resolver twice: first returns True, second returns False."""
        session = AsyncMock()
        encounter_id = str(uuid4())
        
        # First call: rowcount=1 (alert resolved)
        session.execute.return_value.rowcount = 1
        first = await resolve_boarding_alert(encounter_id=encounter_id, session=session)

        # Second call: rowcount=0 (already resolved)
        session.execute.return_value.rowcount = 0
        second = await resolve_boarding_alert(encounter_id=encounter_id, session=session)

        assert first is True
        assert second is False

    @pytest.mark.asyncio
    async def test_resolve_handles_invalid_encounter_id_format(self):
        """Invalid encounter_id format returns False with error log."""
        session = AsyncMock()

        result = await resolve_boarding_alert(encounter_id="invalid-uuid", session=session)

        assert result is False
        session.execute.assert_not_called()  # No DB query on invalid UUID

    @pytest.mark.asyncio
    async def test_resolve_update_where_clause_filters(self):
        """UPDATE WHERE clause must include boarding_alert_sent_at IS NOT NULL AND resolved_at IS NULL."""
        session = AsyncMock()
        session.execute.return_value.rowcount = 1
        encounter_id = str(uuid4())

        await resolve_boarding_alert(encounter_id=encounter_id, session=session)

        # Verify UPDATE statement was called
        session.execute.assert_called_once()
        update_stmt = session.execute.call_args.args[0]
        compiled = str(update_stmt.compile(compile_kwargs={"literal_binds": True}))
        
        # Check WHERE clause includes both filters
        assert "boarding_alert_sent_at IS NOT NULL" in compiled or "is_not(None)" in str(update_stmt)
        assert "boarding_alert_resolved_at IS NULL" in compiled or "is_(None)" in str(update_stmt)

    @pytest.mark.asyncio
    async def test_resolve_sets_resolved_at_timestamp(self):
        """Verify boarding_alert_resolved_at is set to current UTC timestamp."""
        session = AsyncMock()
        session.execute.return_value.rowcount = 1

        await resolve_boarding_alert(encounter_id=str(uuid4()), session=session)

        update_stmt = session.execute.call_args.args[0]
        # Verify values() includes boarding_alert_resolved_at
        assert "boarding_alert_resolved_at" in str(update_stmt)


# ---------------------------------------------------------------------------
# Integration with PATCH endpoint (simulated)
# ---------------------------------------------------------------------------

class TestBoardingResolverIntegration:
    @pytest.mark.asyncio
    async def test_resolver_called_with_correct_parameters(self):
        """Verify resolve_boarding_alert is called with encounter_id as string and session."""
        session = AsyncMock()
        session.execute.return_value.rowcount = 1
        encounter_id = uuid4()

        # Simulate PATCH endpoint logic
        result = await resolve_boarding_alert(
            encounter_id=str(encounter_id),
            session=session,
        )

        assert result is True
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolver_no_op_preserves_transaction(self):
        """When resolver returns False (no-op), transaction continues normally."""
        session = AsyncMock()
        session.execute.return_value.rowcount = 0  # No alert to resolve

        result = await resolve_boarding_alert(encounter_id=str(uuid4()), session=session)

        assert result is False
        # Session is still valid; can continue with other operations
        session.execute.assert_called_once()
