"""SMS dispatch for 48-hour post-discharge check-in notifications.

Message template (US-041 Technical Notes):
    "Hi {first_name}, it's been 48 hours since your discharge. How are you feeling?
     Reply to let us know or call {care_team_number} with any concerns."

PHI minimisation: only first_name is included in the message body.
MRN, last name, DOB, and phone number are NOT included (AIR-021).

Design refs:
    US-041 AC Scenario 3 (SMS variant)
    AIR-040 — dispatch via Twilio
"""
from __future__ import annotations

from app.core.secrets import get_secret


async def send_checkin_sms(
    *,
    to_phone: str,
    first_name: str,
    care_team_number: str,
) -> None:
    """Send the 48-hour check-in SMS via Twilio.

    Args:
        to_phone: Patient's decrypted phone number (E.164 format).
        first_name: Patient's decrypted first name (PHI — not logged).
        care_team_number: Care team contact number from app config.

    Raises:
        TwilioRestException: On Twilio API error (caller handles retry).
    """
    from twilio.rest import Client as TwilioClient
    
    # Load credentials from Secret Manager
    account_sid = get_secret("twilio-account-sid")
    auth_token = get_secret("twilio-auth-token")
    from_number = get_secret("twilio-from-number")
    
    client = TwilioClient(account_sid, auth_token)
    body = (
        f"Hi {first_name}, it's been 48 hours since your discharge. "
        f"How are you feeling? Reply to let us know or call "
        f"{care_team_number} with any concerns."
    )
    
    client.messages.create(
        body=body,
        from_=from_number,
        to=to_phone,
    )
