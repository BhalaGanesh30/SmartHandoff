"""Email dispatch for 48-hour post-discharge check-in notifications.

Uses a SendGrid Dynamic Template (AIR-042). Template substitutions:
    {{first_name}}         — patient's first name (only PHI in substitutions)
    {{care_team_number}}   — care team phone number from config

Design refs:
    US-041 AC Scenario 3 — "48-hour check-in" SendGrid template
    AIR-042 — SendGrid Dynamic Templates versioned in source control
"""
from __future__ import annotations

import os

from app.core.secrets import get_secret


async def send_checkin_email(
    *,
    to_email: str,
    first_name: str,
    care_team_number: str,
) -> None:
    """Send the 48-hour check-in email via SendGrid Dynamic Template.

    Args:
        to_email: Patient's decrypted email address (PHI — not logged).
        first_name: Patient's decrypted first name (included in template substitution).
        care_team_number: Care team contact number from app config.

    Raises:
        Exception: On SendGrid API error (caller handles status update to FAILED).
    """
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, To, DynamicTemplateData
    
    # Load credentials from Secret Manager
    api_key = get_secret("sendgrid-api-key")
    from_email = get_secret("sendgrid-from-email")
    template_id = os.environ.get(
        "SENDGRID_CHECKIN_48H_TEMPLATE_ID",
        get_secret("sendgrid-checkin-48h-template-id")
    )
    
    message = Mail(
        from_email=from_email,
        to_emails=To(to_email),
    )
    message.template_id = template_id
    message.dynamic_template_data = DynamicTemplateData({
        "first_name": first_name,
        "care_team_number": care_team_number,
    })

    sg = SendGridAPIClient(api_key)
    response = sg.send(message)
    
    # Raise exception if SendGrid returns error status
    if response.status_code not in (200, 202):
        raise Exception(f"SendGrid API error: status={response.status_code}")
