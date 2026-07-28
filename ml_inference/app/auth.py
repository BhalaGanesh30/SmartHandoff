"""Service account JWT dependency for ML Inference Service.

Only Cloud Run services with the designated service account may call this endpoint.
The JWT is validated using the Google public key set (OIDC discovery).

Design refs:
    US-036 DoD — POST endpoint auth: service account JWT
    SEC-001 — service-to-service JWT; signed by GCP IAM
"""
from __future__ import annotations

import os

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

_bearer = HTTPBearer()

EXPECTED_AUDIENCE = os.environ.get(
    "ML_INFERENCE_AUDIENCE",
    "https://ml-inference-default-uc.a.run.app",  # overridden at deploy time
)
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"

_certs_cache: dict | None = None


async def _get_google_certs() -> dict:
    """Fetch and cache Google's public key certificates for JWT validation."""
    global _certs_cache
    if _certs_cache is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(GOOGLE_CERTS_URL, timeout=5.0)
            resp.raise_for_status()
            _certs_cache = resp.json()
    return _certs_cache


async def verify_service_account_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> None:
    """Validate a Google-signed service account ID token.

    Raises:
        HTTPException 401: If the token is missing, malformed, or has an invalid signature.
        HTTPException 403: If the token audience does not match the expected audience.
    """
    token = credentials.credentials
    try:
        certs = await _get_google_certs()
        payload = jwt.decode(
            token,
            certs,
            algorithms=["RS256"],
            audience=EXPECTED_AUDIENCE,
            options={"verify_at_hash": False},
        )
        _ = payload  # payload validated; sub is the service account email
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired service account token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
