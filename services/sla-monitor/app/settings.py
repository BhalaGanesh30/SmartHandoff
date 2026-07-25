"""SLA Monitor service configuration settings.

Loads configuration from environment variables for database connections,
GCP project settings, and service-specific parameters.

US-021: Read replica routing via separate database_read_url (TR-010).
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database connections (TR-010 read/write split)
    database_write_url: str = os.getenv(
        "DATABASE_WRITE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/smarthandoff",
    )
    database_read_url: str = os.getenv(
        "DATABASE_READ_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/smarthandoff",
    )

    # GCP configuration
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "smarthandoff-dev")
    gcp_region: str = os.getenv("GCP_REGION", "us-central1")

    # Service configuration
    service_name: str = "sla-monitor"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


settings = get_settings()
