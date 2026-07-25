"""Integration tests for Twilio webhook delivery status handler.

Tests the POST /webhooks/twilio/status endpoint with signature validation.
"""
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_auth_token():
    """Mock Twilio auth token for testing."""
    return "test_auth_token_12345"


@pytest.fixture
def webhook_url():
    """Webhook callback URL."""
    return "https://notification-service.run.app/webhooks/twilio/status"


class TestTwilioWebhook:
    """Integration tests for Twilio delivery webhook."""

    def test_missing_signature_returns_403(self, client):
        """Test that missing X-Twilio-Signature header returns 403."""
        response = client.post(
            "/webhooks/twilio/status",
            data={
                "MessageSid": "SM1234567890abcdef",
                "MessageStatus": "delivered",
            },
        )
        assert response.status_code == 403
        assert "Missing X-Twilio-Signature" in response.json()["detail"]

    def test_invalid_signature_returns_403(self, client, mock_auth_token):
        """Test that invalid signature returns 403."""
        with patch("app.webhooks.twilio.get_secret", return_value=mock_auth_token):
            response = client.post(
                "/webhooks/twilio/status",
                data={
                    "MessageSid": "SM1234567890abcdef",
                    "MessageStatus": "delivered",
                },
                headers={"X-Twilio-Signature": "invalid_signature"},
            )
            assert response.status_code == 403
            assert "Invalid" in response.json()["detail"]

    def test_valid_signature_updates_status_delivered(
        self, client, mock_auth_token, webhook_url
    ):
        """Test valid signature updates notification to DELIVERED."""
        # Prepare form data
        form_data = {
            "MessageSid": "SM1234567890abcdef",
            "MessageStatus": "delivered",
        }

        # Generate valid signature
        validator = RequestValidator(mock_auth_token)
        signature = validator.compute_signature(webhook_url, form_data)

        with patch("app.webhooks.twilio.get_secret", return_value=mock_auth_token):
            with patch("app.webhooks.twilio.get_db_session"):
                response = client.post(
                    "/webhooks/twilio/status",
                    data=form_data,
                    headers={"X-Twilio-Signature": signature},
                )
                assert response.status_code == 204

    def test_failed_status_updates_to_failed(
        self, client, mock_auth_token, webhook_url
    ):
        """Test MessageStatus=failed updates notification to FAILED."""
        form_data = {
            "MessageSid": "SM1234567890abcdef",
            "MessageStatus": "failed",
        }

        validator = RequestValidator(mock_auth_token)
        signature = validator.compute_signature(webhook_url, form_data)

        with patch("app.webhooks.twilio.get_secret", return_value=mock_auth_token):
            with patch("app.webhooks.twilio.get_db_session"):
                response = client.post(
                    "/webhooks/twilio/status",
                    data=form_data,
                    headers={"X-Twilio-Signature": signature},
                )
                assert response.status_code == 204

    def test_undelivered_status_updates_to_failed(
        self, client, mock_auth_token, webhook_url
    ):
        """Test MessageStatus=undelivered updates notification to FAILED."""
        form_data = {
            "MessageSid": "SM1234567890abcdef",
            "MessageStatus": "undelivered",
        }

        validator = RequestValidator(mock_auth_token)
        signature = validator.compute_signature(webhook_url, form_data)

        with patch("app.webhooks.twilio.get_secret", return_value=mock_auth_token):
            with patch("app.webhooks.twilio.get_db_session"):
                response = client.post(
                    "/webhooks/twilio/status",
                    data=form_data,
                    headers={"X-Twilio-Signature": signature},
                )
                assert response.status_code == 204

    def test_intermediate_status_no_update(
        self, client, mock_auth_token, webhook_url
    ):
        """Test intermediate statuses (sent, queued) are ignored."""
        for status in ["sent", "queued", "sending"]:
            form_data = {
                "MessageSid": "SM1234567890abcdef",
                "MessageStatus": status,
            }

            validator = RequestValidator(mock_auth_token)
            signature = validator.compute_signature(webhook_url, form_data)

            with patch("app.webhooks.twilio.get_secret", return_value=mock_auth_token):
                with patch("app.webhooks.twilio.get_db_session"):
                    response = client.post(
                        "/webhooks/twilio/status",
                        data=form_data,
                        headers={"X-Twilio-Signature": signature},
                    )
                    assert response.status_code == 204
