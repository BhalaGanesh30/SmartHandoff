"""Sample notification payloads for testing."""
from __future__ import annotations

import uuid


def sample_sms_payload():
    """Generate a sample SMS notification payload."""
    return {
        "idempotency_key": f"NOTIF-{uuid.uuid4()}",
        "type": "SMS",
        "phone": "+15005550006",
        "template": "medication_reminder",
        "substitutions": {"patient_name": "Jane Doe"},
        "recipient_id": str(uuid.uuid4()),
    }


def sample_email_payload():
    """Generate a sample email notification payload."""
    return {
        "idempotency_key": f"NOTIF-{uuid.uuid4()}",
        "type": "EMAIL",
        "email": "patient@example.com",
        "template": "d-test_dynamic_template_id",
        "substitutions": {"first_name": "Jane"},
        "recipient_id": str(uuid.uuid4()),
    }
