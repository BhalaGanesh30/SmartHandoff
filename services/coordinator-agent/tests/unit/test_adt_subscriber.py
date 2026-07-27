"""Unit tests for ADTSubscriber — shutdown_event and _deserialise_message."""
import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from app.pubsub.adt_subscriber import _deserialise_message


class TestDeserialiseMessage:
    """_deserialise_message must convert valid Pub/Sub bytes to ADTEvent."""

    def test_raises_on_invalid_json(self):
        msg = MagicMock()
        msg.data = b"not-json"
        with pytest.raises(ValueError, match="Cannot deserialise"):
            _deserialise_message(msg)

    def test_raises_on_non_utf8(self):
        msg = MagicMock()
        msg.data = bytes([0xFF, 0xFE])  # invalid UTF-8
        with pytest.raises(ValueError, match="Cannot deserialise"):
            _deserialise_message(msg)


class TestShutdownEvent:
    """shutdown_event must be an asyncio.Event."""

    def test_shutdown_event_is_asyncio_event(self):
        from unittest.mock import AsyncMock
        from app.pubsub.adt_subscriber import ADTSubscriber

        # Mock environment variables
        with patch.dict(os.environ, {"PUBSUB_PROJECT_ID": "test-project", "COORDINATOR_SUB_ID": "test-sub"}):
            sub = ADTSubscriber(callback=AsyncMock())
            assert isinstance(sub.shutdown_event, asyncio.Event)
            assert not sub.shutdown_event.is_set()

    def test_setting_shutdown_event(self):
        from unittest.mock import AsyncMock
        from app.pubsub.adt_subscriber import ADTSubscriber

        # Mock environment variables
        with patch.dict(os.environ, {"PUBSUB_PROJECT_ID": "test-project", "COORDINATOR_SUB_ID": "test-sub"}):
            sub = ADTSubscriber(callback=AsyncMock())
            sub.shutdown_event.set()
            assert sub.shutdown_event.is_set()
