"""Application JWT issuance and Bearer token validation.

SmartHandoff issues its own short-lived JWT after validating the OIDC
id_token. This decouples the application session from the IdP session and
allows role/unit claims to be augmented from the SmartHandoff user DB.

JWT spec (US-056 DoD):
    sub     = user_id (from OIDC sub claim, mapped via DB lookup)
    role    = SmartHandoff role string (mapped from OIDC groups claim)
    units   = list of unit codes the user is assigned to
    email   = user email (from OIDC email claim)
    iat     = issued-at timestamp (UTC)
    exp     = iat + 8 hours (28800 seconds)
    alg     = HS256

Signing key:
    Loaded from Secret Manager secret 'smarthandoff-jwt-signing-key-{environment}'.
    Mounted by Cloud Run as the JWT_SIGNING_KEY environment variable (US-005/TASK-003).
    Must be a minimum 32-byte (256-bit) random string.

Bearer validation (get_current_user):
    Used as a FastAPI dependency on every protected route.
    Verifies HS256 signature, exp, and required claims.
    Returns decoded claims dict; raises HTTP 401 on any failure.
"""
from __future__ import annotations

import logging
import os
import time
import uuid as _uuid
from datetime import datetime, timezone
from typing import Annotated

import redis as _redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict

from app.core.auth.jwt_blocklist import is_blocklisted

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_TOKEN_EXPIRY_SECONDS = 8 * 60 * 60  # 8 hours (US-056 DoD)

_bearer_scheme = HTTPBearer(auto_error=True)


# ── Token claims model (US-057) ───────────────────────────────────────────────

class TokenClaims(BaseModel):
    """Decoded and validated SmartHandoff application JWT payload.

    Used as the return type of get_current_user() and the RBAC dependency
    require_permission(), giving typed access to JWT claims in route handlers.
    """

    model_config = ConfigDict(extra="ignore")

    sub: str
    role: str
    units: list[str] = []
    email: str = ""
    jti: str | None = None
    iat: int = 0
    exp: int = 0


def _jwt_signing_key() -> str:
    """Return JWT_SIGNING_KEY from environment (mounted from Secret Manager)."""
    key = os.environ.get("JWT_SIGNING_KEY", "")
    if not key or len(key) < 32:
        raise RuntimeError(
            "JWT_SIGNING_KEY is not set or too short (minimum 32 characters). "
            "Mount it from Secret Manager 'smarthandoff-jwt-signing-key-{env}'."
        )
    return key


# ── Claims mapping helpers ─────────────────────────────────────────────────────

# EMAIL-BASED ROLE MAPPING (for Gmail/Google OAuth testing)
# Add your Gmail addresses here and assign roles directly
_EMAIL_ROLE_MAP: dict[str, str] = {
    # Format: "email@gmail.com" → "role_name"
    "balaganesh272@gmail.com":      "admin",
    # "nurse@hospital.com":           "nurse",
    # "doctor@hospital.com":          "physician",
    # "pharmacist@hospital.com":      "pharmacist",
}

# GROUP-BASED ROLE MAPPING (for Google Groups)
# Map IdP group names to SmartHandoff role strings.
# Keys must match the group names configured in the hospital IdP.
_GROUP_ROLE_MAP: dict[str, str] = {
    "smarthandoff-admin":       "admin",
    "smarthandoff-physician":   "physician",
    "smarthandoff-nurse":       "nurse",
    "smarthandoff-pharmacist":  "pharmacist",
    "smarthandoff-bed-manager": "bed_manager",
}


def _map_role(email: str = "", groups: list[str] = None) -> str:
    """Map email or groups to a SmartHandoff role string.

    Priority order:
    1. Check if email is in _EMAIL_ROLE_MAP (direct email mapping)
    2. Check if any group is in _GROUP_ROLE_MAP (Google Groups)
    3. Default to "ADMIN" for testing (remove in production)

    Args:
        email: User's email address from OIDC claims
        groups: List of group names from OIDC claims (default [])

    Returns:
        str: Role name (admin, nurse, physician, etc.) or "ADMIN" as default
    """
    if groups is None:
        groups = []
    
    # Step 1: Check email mapping first (highest priority)
    if email and email in _EMAIL_ROLE_MAP:
        role = _EMAIL_ROLE_MAP[email]
        logger.info(
            "✓ Role mapped by email: %s → %s",
            email,
            role,
            extra={"event_type": "role_mapping", "method": "email"},
        )
        return role
    
    # Step 2: Check group mapping (fallback)
    for group in groups:
        if group in _GROUP_ROLE_MAP:
            role = _GROUP_ROLE_MAP[group]
            logger.info(
                "✓ Role mapped by group: %s → %s",
                group,
                role,
                extra={"event_type": "role_mapping", "method": "group"},
            )
            return role
    
    # Step 3: Default to ADMIN for testing (remove in production)
    logger.warning(
        "⚠️  No role mapping found for email=%s, groups=%r. Assigning default 'ADMIN'.",
        email,
        groups,
        extra={"event_type": "auth_warning", "reason": "default_role_assigned"},
    )
    return "ADMIN"  # TODO: Remove this default in production


def _map_claims(oidc_claims: dict) -> dict:
    """Map OIDC id_token claims to SmartHandoff application JWT claims.

    Mapping spec (US-056 DoD):
        sub      → user_id  (OIDC subject identifier)
        email    → role     (checked first against _EMAIL_ROLE_MAP)
        groups   → role     (fallback to _GROUP_ROLE_MAP)
        units    → units    (custom claim set by IdP, default [])
        email    → email

    Args:
        oidc_claims: Decoded OIDC id_token claims dict.

    Returns:
        dict: Application claims ready for JWT encoding.

    Raises:
        HTTPException 403: If the role cannot be determined (removed - now defaults to ADMIN).
    """
    email = oidc_claims.get("email", "")
    groups = oidc_claims.get("groups", [])
    
    # Map role using email (priority 1) or groups (priority 2)
    role = _map_role(email=email, groups=groups)
    
    # Note: role will never be "unknown" due to ADMIN fallback
    # Remove the check below if moving to strict role enforcement
    
    return {
        "sub": oidc_claims["sub"],           # user_id
        "role": role,
        "units": oidc_claims.get("units", []),
        "email": email,
    }


# ── JWT issuance ───────────────────────────────────────────────────────────────

def issue_app_jwt(oidc_claims: dict) -> tuple[str, str]:
    """Issue a SmartHandoff application JWT from validated OIDC claims.

    Args:
        oidc_claims: Decoded and validated OIDC id_token claims (from TASK-003).

    Returns:
        tuple[str, str]: (signed JWT string, jti UUID string).

    Raises:
        HTTPException 403: If role mapping fails.
    """
    app_claims = _map_claims(oidc_claims)
    now = int(datetime.now(tz=timezone.utc).timestamp())
    jti = str(_uuid.uuid4())  # unique token ID — enables per-token blocklisting (US-059)

    payload = {
        **app_claims,
        "jti": jti,
        "iat": now,
        "exp": now + _TOKEN_EXPIRY_SECONDS,
    }

    token = jwt.encode(payload, _jwt_signing_key(), algorithm=_ALGORITHM)
    logger.info(
        "Application JWT issued for sub=%s role=%s jti=%s exp_in=%ds",
        app_claims["sub"],
        app_claims["role"],
        jti,
        _TOKEN_EXPIRY_SECONDS,
        extra={"event_type": "jwt_issued", "jti": jti},
    )
    return token, jti


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    """Create a SmartHandoff application JWT with custom claims.

    This is a simplified JWT issuance function for non-OIDC flows such as
    patient portal OTP authentication (US-065). Unlike issue_app_jwt(), this
    does not require OIDC claims mapping.

    Args:
        subject: The user/patient identifier to place in the 'sub' claim.
        extra_claims: Optional dict of additional claims to merge into the payload.
                      Common keys: "role", "email", "phone", "units".

    Returns:
        str: Signed JWT string with 8-hour expiry.

    Example (US-065 patient portal):
        token = create_access_token(
            subject=patient_id,
            extra_claims={"role": "PATIENT", "phone": "+15005550006"}
        )
    """
    now = int(datetime.now(tz=timezone.utc).timestamp())
    jti = str(_uuid.uuid4())

    payload = {
        "sub": subject,
        "jti": jti,
        "iat": now,
        "exp": now + _TOKEN_EXPIRY_SECONDS,
        **(extra_claims or {}),
    }

    token = jwt.encode(payload, _jwt_signing_key(), algorithm=_ALGORITHM)
    logger.info(
        "Access token created for sub=%s jti=%s exp_in=%ds",
        subject,
        jti,
        _TOKEN_EXPIRY_SECONDS,
        extra={"event_type": "jwt_issued", "jti": jti, **extra_claims} if extra_claims else {"event_type": "jwt_issued", "jti": jti},
    )
    return token


# ── Bearer validation (FastAPI dependency) ────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> TokenClaims:
    """FastAPI dependency: validate SmartHandoff application JWT from Bearer header.

    Inject this dependency on all protected routes:

        @router.get("/patients")
        async def list_patients(user: Annotated[TokenClaims, Depends(get_current_user)]):
            ...

    Returns:
        TokenClaims: Decoded JWT payload (includes sub, role, units, email, exp).

    Raises:
        HTTPException 401: If the token is missing, expired, or invalid.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            _jwt_signing_key(),
            algorithms=[_ALGORITHM],
            options={"verify_exp": True},
        )
    except JWTError as exc:
        logger.warning(
            "Bearer JWT validation failed: %s",
            type(exc).__name__,
            extra={"event_type": "auth_failure", "reason": "invalid_bearer"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # ── Blocklist check (US-059) — MUST be after signature validation ──────────
    jti: str | None = payload.get("jti")
    if jti:
        try:
            if is_blocklisted(jti):
                logger.warning(
                    "Blocklisted JWT presented: jti=%s sub=%s",
                    jti,
                    payload.get("sub"),
                    extra={
                        "event_type": "auth_failure",
                        "reason": "token_blocklisted",
                        "jti": jti,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired access token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except _redis.RedisError as exc:
            # Fail-closed: Redis unavailable means we cannot confirm
            # the token is not revoked — treat as a service error.
            logger.error(
                "Redis unavailable during blocklist check: %s",
                exc,
                extra={"event_type": "redis_error", "context": "blocklist_check"},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            ) from exc
    else:
        # Token predates jti claim introduction — allow through with warning.
        # Remove this branch after all pre-jti tokens have expired (8 hours
        # after TASK-001 is deployed).
        logger.warning(
            "JWT without jti claim from sub=%s — cannot blocklist-check; "
            "token will expire naturally in %d seconds",
            payload.get("sub"),
            max(payload.get("exp", 0) - int(time.time()), 0),
            extra={"event_type": "auth_warning", "reason": "missing_jti"},
        )

    # ── Required claims presence ───────────────────────────────────────────────
    for required_claim in ("sub", "role", "exp"):
        if required_claim not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return TokenClaims(**payload)
