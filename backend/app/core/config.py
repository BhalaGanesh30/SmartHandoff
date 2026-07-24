"""Application settings — loaded from environment variables (mounted from GCP Secret Manager).

SmartHandoff follows TR-021: zero hardcoded credentials. All secrets are injected
as environment variables by Cloud Run via Secret Manager volume mounts.

Usage::
    from app.core.config import get_settings
    settings = get_settings()
    secret = settings.SCIM_CLIENT_SECRET
"""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    """Application settings resolved from environment variables at access time.

    Each property reads from ``os.environ`` so tests can monkeypatch the env
    without needing to reload the module.
    """

    @property
    def SCIM_CLIENT_SECRET(self) -> str:
        """Long-lived bearer token issued to the hospital IdP for SCIM provisioning.

        90-day rotation. Stored in GCP Secret Manager as 'scim-client-secret'.
        Mounted as SCIM_CLIENT_SECRET environment variable in Cloud Run (TR-021).

        Raises:
            RuntimeError: If SCIM_CLIENT_SECRET is not set.
        """
        value = os.environ.get("SCIM_CLIENT_SECRET", "")
        if not value:
            raise RuntimeError(
                "SCIM_CLIENT_SECRET environment variable is not set. "
                "Mount it from GCP Secret Manager 'scim-client-secret-{env}'."
            )
        return value

    # --- FHIR / SMART on FHIR OAuth 2.0 (US-016) ---

    @property
    def FHIR_BASE_URL(self) -> str:
        """FHIR R4 server base URL (e.g., 'https://ehr.example.com/fhir').

        Loaded from GCP Secret Manager secret: 'fhir_base_url'.

        Raises:
            RuntimeError: If FHIR_BASE_URL is not set.
        """
        value = os.environ.get("FHIR_BASE_URL", "")
        if not value:
            raise RuntimeError(
                "FHIR_BASE_URL environment variable is not set. "
                "Mount it from GCP Secret Manager 'fhir_base_url'."
            )
        return value

    @property
    def FHIR_CLIENT_ID(self) -> str:
        """SMART on FHIR OAuth 2.0 client ID for client_credentials grant.

        Loaded from GCP Secret Manager secret: 'fhir_client_id'.

        Raises:
            RuntimeError: If FHIR_CLIENT_ID is not set.
        """
        value = os.environ.get("FHIR_CLIENT_ID", "")
        if not value:
            raise RuntimeError(
                "FHIR_CLIENT_ID environment variable is not set. "
                "Mount it from GCP Secret Manager 'fhir_client_id'."
            )
        return value

    @property
    def FHIR_CLIENT_SECRET(self) -> str:
        """SMART on FHIR OAuth 2.0 client secret for client_credentials grant.

        Loaded from GCP Secret Manager secret: 'fhir_client_secret'.

        Raises:
            RuntimeError: If FHIR_CLIENT_SECRET is not set.
        """
        value = os.environ.get("FHIR_CLIENT_SECRET", "")
        if not value:
            raise RuntimeError(
                "FHIR_CLIENT_SECRET environment variable is not set. "
                "Mount it from GCP Secret Manager 'fhir_client_secret'."
            )
        return value

    @property
    def FHIR_SCOPE(self) -> str:
        """OAuth 2.0 scope for FHIR access (default: system/*.read for all resources).

        Can be overridden with specific scopes like 'system/Patient.read system/Encounter.read'.
        """
        return os.environ.get("FHIR_SCOPE", "system/*.read")

    @property
    def FHIR_MRN_SYSTEM(self) -> str:
        """FHIR identifier system for Medical Record Number (MRN).

        Used in Patient?identifier={system}|{mrn} searches.
        Default: 'http://hospital.org/mrn'

        Can be overridden via FHIR_MRN_SYSTEM environment variable for
        organization-specific identifier systems.
        """
        return os.environ.get("FHIR_MRN_SYSTEM", "http://hospital.org/mrn")

    # --- GCP Configuration (US-019) ---

    @property
    def GCP_PROJECT_ID(self) -> str:
        """GCP project ID for Pub/Sub topic paths.

        Used for care team alerts and notification requests.
        Loaded from environment variable GCP_PROJECT_ID.

        Raises:
            RuntimeError: If GCP_PROJECT_ID is not set.
        """
        value = os.environ.get("GCP_PROJECT_ID", "")
        if not value:
            raise RuntimeError(
                "GCP_PROJECT_ID environment variable is not set. "
                "Set it in Cloud Run environment configuration."
            )
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Call ``get_settings.cache_clear()`` in tests to reset after monkeypatching
    environment variables.
    """
    return Settings()
