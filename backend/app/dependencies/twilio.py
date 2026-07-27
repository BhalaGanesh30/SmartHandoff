"""Twilio client dependency for OTP delivery via Twilio Verify API."""
from __future__ import annotations

import os
from functools import lru_cache

from twilio.rest import Client


def _get_twilio_credentials() -> tuple[str, str]:
    """Return Twilio credentials from environment variables.

    Returns:
        tuple: (account_sid, auth_token)

    Raises:
        RuntimeError: If credentials are not set.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")

    if not account_sid or not auth_token:
        raise RuntimeError(
            "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables "
            "must be set. Mount them from GCP Secret Manager."
        )

    return account_sid, auth_token


@lru_cache(maxsize=1)
def _twilio_client() -> Client:
    """Create and cache a Twilio REST API client.

    Returns:
        Client: Singleton Twilio client instance.
    """
    account_sid, auth_token = _get_twilio_credentials()
    return Client(account_sid, auth_token)


async def get_twilio_client() -> Client:
    """FastAPI dependency that provides a Twilio client.

    Returns:
        Client: Cached Twilio REST API client.
    """
    return _twilio_client()
