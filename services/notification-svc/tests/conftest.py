"""Shared pytest fixtures for notification-service tests.

Provides:
    - async_session: In-memory SQLite async session with notification schema
    - mock_twilio_client: Pre-configured AsyncMock for twilio.rest.Client
    - mock_sendgrid_client: Pre-configured Mock for sendgrid.SendGridAPIClient
    - mock_get_secret: Monkeypatches get_secret() to return test credentials
"""
from __future__ import annotations

import os
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.notification import Notification, NotificationStatus, NotificationType


# Mock environment variables before any module imports
os.environ.setdefault("TWILIO_FROM_NUMBER", "+15005550001")
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("SENDGRID_FROM_EMAIL", "noreply@test.com")


@pytest.fixture(scope="session")
def engine():
    """Create an in-memory SQLite async engine for tests."""
    return create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)


@pytest_asyncio.fixture(scope="function")
async def async_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create tables and yield a fresh session for each test."""
    async with engine.begin() as conn:
        # Create notification table without FK constraints for testing
        await conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS notification (
                id TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                recipient_id TEXT,
                phone_or_email TEXT,
                template TEXT NOT NULL,
                substitutions TEXT DEFAULT '{}',
                delivery_status TEXT NOT NULL DEFAULT 'PENDING',
                urgency_override INTEGER NOT NULL DEFAULT 0,
                retry_count INTEGER NOT NULL DEFAULT 0,
                twilio_message_sid TEXT,
                sendgrid_message_id TEXT,
                sent_at TEXT,
                delivered_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.execute(sa.text("DROP TABLE IF EXISTS notification"))


@pytest.fixture
def mock_twilio_client():
    """Mock Twilio REST client — messages.create returns a fake message."""
    mock = MagicMock()
    mock.messages.create.return_value = MagicMock(sid="SM_TEST_SID_001")
    with patch("app.dispatchers.sms._build_twilio_client", return_value=mock):
        yield mock


@pytest.fixture
def mock_sendgrid_client():
    """Mock SendGrid client — send returns 202 with X-Message-Id header."""
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.headers = {"X-Message-Id": "SG_TEST_MSG_001"}
    mock_client = MagicMock()
    mock_client.send.return_value = mock_response
    with patch("app.dispatchers.email._build_sendgrid_client", return_value=mock_client):
        yield mock_client


@pytest.fixture(autouse=True)
def mock_get_secret():
    """Prevent Secret Manager calls in tests."""
    with patch(
        "app.core.secrets.get_secret",
        side_effect=lambda secret_id: {
            "twilio-account-sid": "AC_TEST_SID",
            "twilio-auth-token": "TEST_AUTH_TOKEN",
            "sendgrid-api-key": "SG_TEST_KEY",
        }.get(secret_id, "TEST_SECRET"),
    ):
        yield


@pytest.fixture
def sample_sms_request():
    from app.schemas import NotificationRequest, NotificationTypeEnum
    return NotificationRequest(
        idempotency_key=f"NOTIF-{uuid.uuid4()}",
        type=NotificationTypeEnum.SMS,
        phone="+15005550006",
        template="medication_reminder",
        substitutions={"patient_name": "Jane Doe"},
        recipient_id=str(uuid.uuid4()),
    )


@pytest.fixture
def sample_email_request():
    from app.schemas import NotificationRequest, NotificationTypeEnum
    return NotificationRequest(
        idempotency_key=f"NOTIF-{uuid.uuid4()}",
        type=NotificationTypeEnum.EMAIL,
        email="patient@example.com",
        template="d-test_dynamic_template_id",
        substitutions={"first_name": "Jane"},
        recipient_id=str(uuid.uuid4()),
    )
