"""
OTP cryptographic helpers for US-065.

All Redis key derivation and bcrypt operations are centralised here to
ensure phone numbers and portal tokens are NEVER stored as plaintext
Redis keys (SEC-003, AIR-043).
"""

import hashlib

import bcrypt

from app.core.config import get_settings


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BCRYPT_ROUNDS: int = 10
OTP_TTL_SECONDS: int = 600          # 10 minutes (AIR-043)
RATE_LIMIT_TTL_SECONDS: int = 3600  # 1 hour window (AC Scenario 2)
RATE_LIMIT_MAX: int = 5             # max OTP requests per phone per hour
MAX_FAILED_ATTEMPTS: int = 3        # OTP invalidated after 3 failures (AC Scenario 3)


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def _sha256_hex(value: str, salt: str = "") -> str:
    """Return the lowercase hex SHA-256 digest of ``value + salt``.

    Uses ``hmac.compare_digest``-safe constant-time construction is not
    required here because the output is used only as a Redis key suffix,
    not as a secret comparison target.
    """
    raw = (value + salt).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def otp_redis_key(portal_token: str) -> str:
    """Redis key for the bcrypt OTP hash.  Never contains plaintext token.

    Pattern: ``otp:{SHA-256(portal_token)}``
    """
    return f"otp:{_sha256_hex(portal_token)}"


def rate_limit_redis_key(phone_number: str) -> str:
    """Redis key for the per-phone OTP rate limit counter.

    Pattern: ``otp_rate:{SHA-256(phone_number + OTP_PHONE_SALT)}``
    The salt prevents phone enumeration from a Redis key dump.
    """
    settings = get_settings()
    return f"otp_rate:{_sha256_hex(phone_number, settings.OTP_PHONE_SALT)}"


def failures_redis_key(portal_token: str) -> str:
    """Redis key for the failed-attempt counter tied to an OTP session.

    Pattern: ``otp_failures:{SHA-256(portal_token)}``
    Reuses the same digest as ``otp_redis_key`` for key locality.
    """
    return f"otp_failures:{_sha256_hex(portal_token)}"


# ---------------------------------------------------------------------------
# bcrypt operations
# ---------------------------------------------------------------------------

def hash_otp(otp_code: str) -> str:
    """Return a bcrypt hash of ``otp_code`` (rounds=10).

    The returned string is safe to store in Redis; it is NOT the OTP itself.
    """
    return bcrypt.hashpw(
        otp_code.encode("utf-8"),
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
    ).decode("utf-8")


def verify_otp(otp_code: str, otp_hash: str) -> bool:
    """Return True if ``otp_code`` matches the stored ``otp_hash``.

    Uses ``bcrypt.checkpw`` which is constant-time against the stored hash.
    """
    return bcrypt.checkpw(
        otp_code.encode("utf-8"),
        otp_hash.encode("utf-8"),
    )
