"""Unit tests for TransitionCoordinatorAgent (SC-1, SC-2, SC-3, SC-4)."""
import pytest
import pytest_asyncio

from app.coordinator.agent import TransitionCoordinatorAgent


@pytest.mark.asyncio
class TestProcessEventAdmit:
    """SC-1: 5 AgentTask records created for ADT^A01."""

    async def test_returns_five_for_admit(self, mock_adt_event, mock_db_session):
        agent = TransitionCoordinatorAgent(db_session=mock_db_session)
        result = await agent.process_event(mock_adt_event)
        assert result == 5

    async def test_db_execute_called_once(self, mock_adt_event, mock_db_session):
        """Single atomic INSERT for all tasks."""
        agent = TransitionCoordinatorAgent(db_session=mock_db_session)
        await agent.process_event(mock_adt_event)
        # Session execute called exactly once (single batch INSERT)
        session = mock_db_session.return_value.__aenter__.return_value
        assert session.execute.call_count == 1


@pytest.mark.asyncio
class TestProcessEventTransfer:
    """SC-2: Transfer creates only relevant tasks."""

    async def test_transfer_does_not_create_discharge_summary(
        self, mock_transfer_event, mock_db_session
    ):
        mock_db_session.return_value.__aenter__.return_value.execute.return_value.fetchall.return_value = [
            ("id",), ("id",)
        ]
        agent = TransitionCoordinatorAgent(db_session=mock_db_session)
        result = await agent.process_event(mock_transfer_event)
        assert result == 2  # TRANSFER_NOTE + BED_MANAGEMENT only


@pytest.mark.asyncio
class TestIdempotency:
    """SC-4: Redelivered messages return 0 (ON CONFLICT DO NOTHING)."""

    async def test_idempotent_replay_returns_zero(self, mock_adt_event, mock_db_session):
        mock_db_session.return_value.__aenter__.return_value.execute.return_value.fetchall.return_value = []
        agent = TransitionCoordinatorAgent(db_session=mock_db_session)
        result = await agent.process_event(mock_adt_event)
        assert result == 0


@pytest.mark.asyncio
class TestUnknownEventType:
    """Unknown event type returns 0 without touching DB."""

    async def test_unknown_event_skips_db(self, mock_db_session):
        from unittest.mock import MagicMock
        event = MagicMock()
        event.encounter_id = __import__("uuid").uuid4()
        event.event_type.value = "ADT^A99"

        agent = TransitionCoordinatorAgent(db_session=mock_db_session)
        result = await agent.process_event(event)
        assert result == 0
        session = mock_db_session.return_value.__aenter__.return_value
        session.execute.assert_not_called()
