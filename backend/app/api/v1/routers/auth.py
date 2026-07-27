"""Authentication router — POST /api/v1/auth/token, POST /api/v1/auth/logout.

Accepts an OIDC id_token from the Angular callback component, validates it,
enforces MFA, and issues a SmartHandoff application JWT.

Routes:
    POST /api/v1/auth/token   — exchange OIDC id_token for app JWT (US-056)
    POST /api/v1/auth/logout  — revoke current JWT via Redis blocklist (US-059)

Design refs:
    design.md §3.3 API Layer / Routers
    design.md §8.2 Authentication & Authorization Flow
    AIR-032, SEC-009, US-059
"""
from __future__ import annotations

import logging
import os
from typing import Annotated

import httpx
import redis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.jwt import TokenClaims, get_current_user, issue_app_jwt
from app.core.auth.jwt_blocklist import add_to_blocklist
from app.core.auth.tokens import validate_id_token
from app.db.deps import get_write_db
from app.models.app_user import AppUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    id_token: str = Field(..., description="OIDC id_token from the identity provider")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="SmartHandoff application JWT")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(default=28800, description="Token validity in seconds (8h)")


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Exchange OIDC id_token for SmartHandoff application JWT",
    description=(
        "Validates the OIDC id_token signature against the IdP JWKS, "
        "enforces MFA (amr claim), maps claims to SmartHandoff roles, "
        "and issues a HS256-signed application JWT."
    ),
)
async def exchange_token(
    body: TokenRequest,
    db: Annotated[AsyncSession, Depends(get_write_db)],
) -> TokenResponse:
    """Exchange an OIDC id_token for a SmartHandoff application JWT."""

    oidc_claims = await validate_id_token(body.id_token)
    app_token, jti = issue_app_jwt(oidc_claims)

    # Persist the issued jti so deprovisioning can blocklist it (US-059/TASK-004)
    try:
        await db.execute(
            sa_update(AppUser)
            .where(AppUser.idp_subject == oidc_claims["sub"])
            .values(current_jti=jti)
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to persist current_jti for sub=%s: %s",
            oidc_claims.get("sub"),
            exc,
            extra={"event_type": "jti_persist_failure"},
        )
        await db.rollback()

    return TokenResponse(access_token=app_token)


# ── POST /api/v1/auth/logout ──────────────────────────────────────────────────

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Revoke the current JWT and end the session",
    response_description="Session terminated; JWT blocklisted",
)
async def logout(
    current_user: Annotated[TokenClaims, Depends(get_current_user)],
) -> dict:
    """Blocklist the current JWT and instruct the client to clear its session.

    The ``get_current_user`` dependency validates the Bearer token before
    this handler runs. A valid (non-expired, non-blocklisted) token is
    required — you cannot log out with an already-invalid token.

    After successful logout the client MUST discard its in-memory JWT.
    Any subsequent request with the same JWT returns 401 Unauthorized.

    Returns:
        JSON body ``{"message": "Logged out successfully"}``

    Raises:
        HTTP 401: Token invalid or already expired (raised by get_current_user).
        HTTP 503: Redis unavailable.
    """
    jti: str | None = current_user.jti
    exp: int | None = current_user.exp

    if not jti or not exp:
        # Token predates jti claim — cannot blocklist, but still respond 200
        # so the client can clear its local JWT and redirect to login.
        logger.warning(
            "Logout requested for token without jti claim: sub=%s",
            current_user.sub,
            extra={"event_type": "logout_no_jti", "sub": current_user.sub},
        )
        return {"message": "Logged out successfully"}

    try:
        add_to_blocklist(jti, exp)
    except redis.RedisError as exc:
        logger.error(
            "Redis error during logout blocklist write: jti=%s error=%s",
            jti,
            exc,
            extra={"event_type": "redis_error", "context": "logout", "jti": jti},
        )
        # Do NOT raise 503 here — the user's intent to log out must succeed
        # even if Redis is momentarily unavailable. Log the failure for ops.
        # The token will expire naturally within its 8-hour window.

    logger.info(
        "User logged out: sub=%s jti=%s",
        current_user.sub,
        jti,
        extra={
            "event_type": "user_logout",
            "sub": current_user.sub,
            "jti": jti,
        },
    )
    return {"message": "Logged out successfully"}


# ── POST /api/v1/auth/exchange-code ───────────────────────────────────────────

class CodeExchangeRequest(BaseModel):
    code: str = Field(..., description="Authorization code from OAuth callback")
    code_verifier: str = Field(..., description="PKCE code verifier")
    redirect_uri: str = Field(..., description="Redirect URI used in the authorization request")


def _get_client_secret() -> str:
    """Get OAuth client secret from environment."""
    secret = os.environ.get("OAUTH_CLIENT_SECRET", "")
    if not secret:
        # For testing without client_secret (development only)
        logger.warning("OAUTH_CLIENT_SECRET not set - using empty string")
        return ""
    return secret


def _get_client_id() -> str:
    """Get OAuth client ID from environment."""
    client_id = os.environ.get("OIDC_CLIENT_ID", "")
    if not client_id:
        raise RuntimeError("OIDC_CLIENT_ID environment variable is not set.")
    return client_id


@router.post(
    "/exchange-code",
    response_model=TokenResponse,
    summary="Exchange authorization code for SmartHandoff JWT",
    description=(
        "Accepts an OAuth authorization code from the frontend, exchanges it "
        "with Google for an id_token (using client_secret), validates the "
        "id_token, and issues a SmartHandoff application JWT."
    ),
)
async def exchange_code(
    body: CodeExchangeRequest,
    db: Annotated[AsyncSession, Depends(get_write_db)],
) -> TokenResponse:
    """Exchange OAuth authorization code for SmartHandoff application JWT.
    
    This endpoint securely handles the code-to-token exchange with Google OAuth,
    keeping the client_secret on the backend.
    """
    
    # Step 1: Exchange authorization code for id_token with Google
    token_url = "https://oauth2.googleapis.com/token"
    
    token_request_data = {
        "grant_type": "authorization_code",
        "code": body.code,
        "redirect_uri": body.redirect_uri,
        "client_id": _get_client_id(),
        "code_verifier": body.code_verifier,
    }
    
    # Only add client_secret if it's set (Google allows PKCE without secret for public clients)
    client_secret = _get_client_secret()
    if client_secret:
        token_request_data["client_secret"] = client_secret
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data=token_request_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            response.raise_for_status()
            token_data = response.json()
    except httpx.HTTPError as exc:
        logger.error(
            "Failed to exchange authorization code: %s - Response: %s",
            exc,
            exc.response.text if hasattr(exc, 'response') else 'No response',
            extra={"event_type": "auth_failure", "reason": "code_exchange_failed"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to exchange authorization code: {str(exc)}",
        ) from exc
    
    id_token = token_data.get("id_token")
    if not id_token:
        logger.error("No id_token in Google OAuth response")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OAuth response - no id_token",
        )
    
    # Step 2: Validate the id_token
    oidc_claims = await validate_id_token(id_token)
    
    # Step 3: Issue SmartHandoff application JWT
    app_token, jti = issue_app_jwt(oidc_claims)
    
    # Step 4: Persist the issued jti for deprovisioning
    try:
        await db.execute(
            sa_update(AppUser)
            .where(AppUser.idp_subject == oidc_claims["sub"])
            .values(current_jti=jti)
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to persist current_jti for sub=%s: %s",
            oidc_claims.get("sub"),
            exc,
            extra={"event_type": "jti_persist_failure"},
        )
        await db.rollback()
    
    return TokenResponse(access_token=app_token)
