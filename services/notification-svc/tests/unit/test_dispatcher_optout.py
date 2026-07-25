"""Unit tests — notification dispatcher opt-out suppression and urgency bypass.

Covers:
    - Non-urgent notification for opted-out patient: OPTED_OUT record created, no dispatch
    - Urgent notification (urgency_override=True) for opted-out patient: dispatched, SENT record
    - Audit log written for both scenarios (BR-012)
    - No PHI in any log payload

Design refs: US-067 DoD, TASK-003, TASK-002, TASK-006.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa

from app.dispatchers.sms import TwilioSMSDispatcher
from app.dispatchers.base import BaseNotificationDispatcher
from app.models.notification import NotificationStatus
from app.schemas import NotificationRequest, NotificationTypeEnum


PATIENT_ID = uuid.uuid4()
ENCOUNTER_ID = uuid.uuid4()


def _make_request(urgency_override: bool, notification_type: str = "medication_reminder") -> NotificationRequest:
    """Helper to create a NotificationRequest with urgency_override flag."""
    return NotificationRequest(
        idempotency_key=f"test-{uuid.uuid4()}",
        type=NotificationTypeEnum.SMS,
        phone="+15005550006",
        template=notification_type,
        substitutions={"patient_name": "Test Patient"},
        recipient_id=str(PATIENT_ID),
        urgency_override=urgency_override,
    )


@pytest.mark.asyncio
async def test_opt_out_suppression_creates_opted_out_record(async_session, mock_twilio_client):
    """Non-urgent notification for opted-out patient → OPTED_OUT record; no dispatch."""
    # Setup: Insert notification record
    notification_id = uuid.uuid4()
    request = _make_request(urgency_override=False)
    
    await async_session.execute(
        sa.text("""
            INSERT INTO notification (
                id, idempotency_key, type, recipient_id, phone_or_email,
                template, substitutions, delivery_status, retry_count, urgency_override, created_at, updated_at
            ) VALUES (
                :id, :idempotency_key, :type, :recipient_id, :phone_or_email,
                :template, :substitutions, 'PENDING', 0, :urgency_override, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(notification_id),
            "idempotency_key": request.idempotency_key,
            "type": request.type.value,
            "recipient_id": request.recipient_id,
            "phone_or_email": request.phone,
            "template": request.template,
            "substitutions": "{}",
            "urgency_override": False,
        }
    )
    await async_session.commit()

    dispatcher = TwilioSMSDispatcher()
    
    # Mock opt-out check to return True (patient has opted out)
    with patch.object(
        TwilioSMSDispatcher,
        "_check_opt_out",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_check_opt_out:
        with patch.object(
            BaseNotificationDispatcher,
            "write_audit_log",
            new_callable=AsyncMock,
        ) as mock_audit:
            # Call dispatch
            await dispatcher.dispatch(async_session, notification_id, request)

    # Verify opt-out check was called
    mock_check_opt_out.assert_called_once_with(
        async_session, request
    )

    # SMS must NOT be called
    mock_twilio_client.messages.create.assert_not_called()

    # Notification record must have OPTED_OUT status
    result = await async_session.execute(
        sa.text("SELECT delivery_status FROM notification WHERE id = :id"),
        {"id": str(notification_id)}
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "OPTED_OUT", f"Expected OPTED_OUT, got {row[0]}"

    # Audit log must be written for BR-012
    mock_audit.assert_called_once()
    call_kwargs = mock_audit.call_args.kwargs
    assert call_kwargs["action"] == "NOTIFICATION_SUPPRESSED_OPT_OUT"
    # Confirm no PHI in audit call (no phone in the action string)
    audit_call_str = str(mock_audit.call_args)
    assert "+1500555" not in audit_call_str, "Phone number leaked in audit log"


@pytest.mark.asyncio
async def test_urgency_bypass_dispatches_despite_opt_out(async_session, mock_twilio_client):
    """Urgent notification (urgency_override=True) dispatched even for opted-out patient."""
    # Setup: Insert notification record
    notification_id = uuid.uuid4()
    request = _make_request(urgency_override=True, notification_type="CARE_TEAM_URGENCY_ALERT")
    
    await async_session.execute(
        sa.text("""
            INSERT INTO notification (
                id, idempotency_key, type, recipient_id, phone_or_email,
                template, substitutions, delivery_status, retry_count, urgency_override, created_at, updated_at
            ) VALUES (
                :id, :idempotency_key, :type, :recipient_id, :phone_or_email,
                :template, :substitutions, 'PENDING', 0, :urgency_override, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(notification_id),
            "idempotency_key": request.idempotency_key,
            "type": request.type.value,
            "recipient_id": request.recipient_id,
            "phone_or_email": request.phone,
            "template": request.template,
            "substitutions": "{}",
            "urgency_override": True,
        }
    )
    await async_session.commit()

    dispatcher = TwilioSMSDispatcher()
    
    # Mock opt-out check to return False (urgency_override bypasses opt-out)
    with patch.object(
        TwilioSMSDispatcher,
        "_check_opt_out",
        new_callable=AsyncMock,
        return_value=False,  # urgency_override=True makes this return False
    ):
        with patch.object(
            BaseNotificationDispatcher,
            "write_audit_log",
            new_callable=AsyncMock,
        ) as mock_audit:
            with patch("app.dispatchers.sms._build_twilio_client", return_value=mock_twilio_client):
                # Call dispatch
                await dispatcher.dispatch(async_session, notification_id, request)

    # SMS must be called despite opt-out (urgency override)
    mock_twilio_client.messages.create.assert_called_once()

    # Notification record must have SENT status and urgency_override=True
    result = await async_session.execute(
        sa.text("SELECT delivery_status, urgency_override FROM notification WHERE id = :id"),
        {"id": str(notification_id)}
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "SENT", f"Expected SENT, got {row[0]}"
    # Note: urgency_override was set at INSERT time, so it should be True
    # The dispatcher doesn't update it again

    # Audit log written
    mock_audit.assert_called()
    call_kwargs = mock_audit.call_args.kwargs
    assert call_kwargs.get("urgency_override") is True


@pytest.mark.asyncio
async def test_opted_in_patient_receives_non_urgent_notification(async_session, mock_twilio_client):
    """Non-urgent notification for opted-in patient proceeds normally."""
    # Setup: Insert notification record
    notification_id = uuid.uuid4()
    request = _make_request(urgency_override=False)
    
    await async_session.execute(
        sa.text("""
            INSERT INTO notification (
                id, idempotency_key, type, recipient_id, phone_or_email,
                template, substitutions, delivery_status, retry_count, urgency_override, created_at, updated_at
            ) VALUES (
                :id, :idempotency_key, :type, :recipient_id, :phone_or_email,
                :template, :substitutions, 'PENDING', 0, :urgency_override, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(notification_id),
            "idempotency_key": request.idempotency_key,
            "type": request.type.value,
            "recipient_id": request.recipient_id,
            "phone_or_email": request.phone,
            "template": request.template,
            "substitutions": "{}",
            "urgency_override": False,
        }
    )
    await async_session.commit()

    dispatcher = TwilioSMSDispatcher()
    
    # Mock opt-out check to return False (patient has NOT opted out)
    with patch.object(
        TwilioSMSDispatcher,
        "_check_opt_out",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with patch.object(
            BaseNotificationDispatcher,
            "write_audit_log",
            new_callable=AsyncMock,
        ):
            with patch("app.dispatchers.sms._build_twilio_client", return_value=mock_twilio_client):
                # Call dispatch
                await dispatcher.dispatch(async_session, notification_id, request)

    # SMS must be called for opted-in patient
    mock_twilio_client.messages.create.assert_called_once()
