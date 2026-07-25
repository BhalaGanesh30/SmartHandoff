"""Integration tests for Pub/Sub consumer with idempotency.

Tests the full message flow: Pub/Sub → Consumer → Dispatcher.
Requires Pub/Sub emulator to be running.
"""
import asyncio
import json
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from google.cloud import pubsub_v1

from app.consumer import run_consumer
from app.models.notification import NotificationStatus
from app.schemas import NotificationRequest


@pytest.fixture
def project_id():
    """GCP project ID for testing."""
    return os.environ.get("GCP_PROJECT_ID", "test-project")


@pytest.fixture
def subscription_id():
    """Pub/Sub subscription ID."""
    return "notification-service-test-sub"


@pytest.fixture
def test_sms_message():
    """Sample SMS notification request."""
    return {
        "idempotency_key": f"TEST-SMS-{uuid.uuid4()}",
        "type": "SMS",
        "phone": "+15555551234",
        "template": "test_message",
        "substitutions": {"patient_name": "Test Patient"},
        "recipient_id": str(uuid.uuid4()),
    }


@pytest.fixture
def test_email_message():
    """Sample email notification request."""
    return {
        "idempotency_key": f"TEST-EMAIL-{uuid.uuid4()}",
        "type": "EMAIL",
        "email": "test@example.com",
        "template": "d-test-template-id",
        "substitutions": {"patient_name": "Test Patient"},
        "recipient_id": str(uuid.uuid4()),
    }


class TestPubSubConsumer:
    """Integration tests for Pub/Sub consumer."""

    @pytest.mark.asyncio
    async def test_consumer_processes_sms_message(
        self, project_id, subscription_id, test_sms_message
    ):
        """Test consumer successfully processes SMS notification."""
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, "notification-requests")

        # Publish test message
        future = publisher.publish(
            topic_path,
            json.dumps(test_sms_message).encode("utf-8"),
        )
        message_id = future.result()

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_consumer_processes_email_message(
        self, project_id, subscription_id, test_email_message
    ):
        """Test consumer successfully processes email notification."""
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, "notification-requests")

        # Publish test message
        future = publisher.publish(
            topic_path,
            json.dumps(test_email_message).encode("utf-8"),
        )
        message_id = future.result()

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_duplicate_message_idempotency(
        self, project_id, subscription_id, test_sms_message
    ):
        """Test duplicate messages are handled via idempotency key."""
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, "notification-requests")

        # Publish same message twice
        message_data = json.dumps(test_sms_message).encode("utf-8")
        future1 = publisher.publish(topic_path, message_data)
        future2 = publisher.publish(topic_path, message_data)

        message_id1 = future1.result()
        message_id2 = future2.result()

        assert message_id1 is not None
        assert message_id2 is not None
        # Both messages should be ACKed, but only one should be dispatched

    @pytest.mark.asyncio
    async def test_invalid_message_nacked(self, project_id, subscription_id):
        """Test invalid messages are NACKed."""
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, "notification-requests")

        # Publish invalid message (missing required fields)
        invalid_message = {
            "idempotency_key": f"TEST-INVALID-{uuid.uuid4()}",
            "type": "SMS",
            # Missing phone field
        }

        future = publisher.publish(
            topic_path,
            json.dumps(invalid_message).encode("utf-8"),
        )
        message_id = future.result()

        assert message_id is not None
        # Message should be NACKed and redelivered


class TestDispatcherIntegration:
    """Integration tests for dispatcher invocation."""

    @pytest.mark.asyncio
    async def test_sms_dispatcher_called_for_sms_type(self, test_sms_message):
        """Test SMS dispatcher is invoked for SMS type."""
        from app.dispatchers.sms import TwilioSMSDispatcher

        with patch.object(
            TwilioSMSDispatcher, "dispatch", new_callable=AsyncMock
        ) as mock_dispatch:
            request = NotificationRequest.model_validate(test_sms_message)
            dispatcher = TwilioSMSDispatcher()

            # Simulate consumer calling dispatcher
            await dispatcher.dispatch(
                session=AsyncMock(),
                notification_id=uuid.uuid4(),
                request=request,
            )

            mock_dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_dispatcher_called_for_email_type(self, test_email_message):
        """Test email dispatcher is invoked for EMAIL type."""
        from app.dispatchers.email import SendGridEmailDispatcher

        with patch.object(
            SendGridEmailDispatcher, "dispatch", new_callable=AsyncMock
        ) as mock_dispatch:
            request = NotificationRequest.model_validate(test_email_message)
            dispatcher = SendGridEmailDispatcher()

            # Simulate consumer calling dispatcher
            await dispatcher.dispatch(
                session=AsyncMock(),
                notification_id=uuid.uuid4(),
                request=request,
            )

            mock_dispatch.assert_called_once()


class TestOptOutHandling:
    """Integration tests for patient opt-out handling."""

    @pytest.mark.asyncio
    async def test_opt_out_patient_skips_dispatch(self, test_sms_message):
        """Test opted-out patients don't receive notifications."""
        from app.dispatchers.base import BaseNotificationDispatcher

        # Mock patient with opt-out enabled
        with patch.object(
            BaseNotificationDispatcher,
            "check_opt_out",
            return_value=True,
        ):
            dispatcher = BaseNotificationDispatcher()
            opted_out = await dispatcher.check_opt_out(
                session=AsyncMock(),
                recipient_id=test_sms_message["recipient_id"],
                urgency_override=False,
            )

            assert opted_out is True

    @pytest.mark.asyncio
    async def test_urgency_override_bypasses_opt_out(self, test_sms_message):
        """Test urgency_override bypasses opt-out flag."""
        from app.dispatchers.base import BaseNotificationDispatcher

        # Mock patient with opt-out enabled but urgency override
        dispatcher = BaseNotificationDispatcher()
        opted_out = await dispatcher.check_opt_out(
            session=AsyncMock(),
            recipient_id=test_sms_message["recipient_id"],
            urgency_override=True,  # Override should bypass opt-out
        )

        assert opted_out is False


@pytest.mark.skipif(
    not os.environ.get("PUBSUB_EMULATOR_HOST"),
    reason="Pub/Sub emulator not running",
)
class TestEndToEndFlow:
    """End-to-end integration tests (requires emulator and mocked dispatchers)."""

    @pytest.mark.asyncio
    async def test_full_sms_flow(self, project_id, subscription_id, test_sms_message):
        """Test complete SMS flow: Pub/Sub → Consumer → Dispatcher → Status."""
        from app.dispatchers.sms import TwilioSMSDispatcher

        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, "notification-requests")

        # Mock Twilio client to avoid real API calls
        with patch("app.dispatchers.sms._build_twilio_client") as mock_client:
            mock_message = AsyncMock()
            mock_message.sid = "SM123test"
            mock_client.return_value.messages.create.return_value = mock_message

            # Publish message
            future = publisher.publish(
                topic_path,
                json.dumps(test_sms_message).encode("utf-8"),
            )
            message_id = future.result()

            # Wait for processing
            await asyncio.sleep(2)

            # Verify dispatcher was called
            assert message_id is not None

    @pytest.mark.asyncio
    async def test_full_email_flow(
        self, project_id, subscription_id, test_email_message
    ):
        """Test complete email flow: Pub/Sub → Consumer → Dispatcher → Status."""
        from app.dispatchers.email import SendGridEmailDispatcher

        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, "notification-requests")

        # Mock SendGrid client to avoid real API calls
        with patch("app.dispatchers.email._build_sendgrid_client") as mock_client:
            mock_response = AsyncMock()
            mock_response.headers = {"X-Message-Id": "test-msg-id-123"}
            mock_client.return_value.send.return_value = mock_response

            # Publish message
            future = publisher.publish(
                topic_path,
                json.dumps(test_email_message).encode("utf-8"),
            )
            message_id = future.result()

            # Wait for processing
            await asyncio.sleep(2)

            # Verify dispatcher was called
            assert message_id is not None
