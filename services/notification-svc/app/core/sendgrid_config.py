"""Configuration loader for SendGrid Dynamic Template IDs.

Loads the ``config/sendgrid_templates.yaml`` file which is populated
at deploy time by ``notifications/upload_sendgrid_templates.py``.

Usage::

    from app.core.sendgrid_config import get_template_id

    template_id = get_template_id("patient_portal_link")
    # Returns: "d-abc123..." (SendGrid template ID)

Design refs:
    US-066 TASK-003 — YAML registry updated by CI/CD upload script
    US-064 TASK-004 — Dispatcher reads template IDs at send time
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Path to the YAML registry file (relative to services/notification-svc/)
_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "sendgrid_templates.yaml"


class TemplateConfigError(Exception):
    """Raised when template configuration cannot be loaded or is invalid."""


@lru_cache(maxsize=1)
def _load_template_registry() -> dict[str, str]:
    """Load and cache the SendGrid template ID registry from YAML.

    Returns:
        Mapping of template name → SendGrid template ID.

    Raises:
        TemplateConfigError: If the YAML file cannot be loaded or is empty.
    """
    if not _CONFIG_PATH.exists():
        raise TemplateConfigError(
            f"Template configuration not found: {_CONFIG_PATH}. "
            "Ensure notifications/upload_sendgrid_templates.py has been run "
            "during deployment to populate config/sendgrid_templates.yaml."
        )

    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
            registry = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise TemplateConfigError(
            f"Failed to parse {_CONFIG_PATH}: {exc}"
        ) from exc

    if not registry:
        raise TemplateConfigError(
            f"Template registry is empty: {_CONFIG_PATH}. "
            "Run the upload script to populate template IDs."
        )

    # Validate that no template IDs are empty/null
    missing = [name for name, tid in registry.items() if not tid]
    if missing:
        raise TemplateConfigError(
            f"Template IDs are empty for: {', '.join(missing)}. "
            "Re-run notifications/upload_sendgrid_templates.py to populate all IDs."
        )

    logger.info(
        "sendgrid_config.loaded",
        extra={"template_count": len(registry)},
    )
    return registry


def get_template_id(template_name: str) -> str:
    """Resolve a template name to its SendGrid Dynamic Template ID.

    Args:
        template_name: Key matching an entry in config/sendgrid_templates.yaml
                      (e.g., "patient_portal_link", "appointment_reminder").

    Returns:
        SendGrid template ID (format: ``d-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx``).

    Raises:
        TemplateConfigError: If the template name is not found in the registry.

    Example::

        >>> get_template_id("patient_portal_link")
        "d-abc123def456..."
    """
    registry = _load_template_registry()

    template_id = registry.get(template_name)
    if not template_id:
        raise TemplateConfigError(
            f"Template name '{template_name}' not found in registry. "
            f"Available templates: {', '.join(registry.keys())}"
        )

    return template_id


def get_all_template_ids() -> dict[str, str]:
    """Return the full template registry mapping.

    Returns:
        Dictionary of template name → SendGrid template ID.

    Raises:
        TemplateConfigError: If the registry cannot be loaded.
    """
    return _load_template_registry().copy()


def reload_template_registry() -> None:
    """Clear the cached registry and force a reload from disk.

    Useful for testing or when the YAML file is updated at runtime.
    In production, the registry is loaded once at startup and cached.
    """
    _load_template_registry.cache_clear()
    logger.info("sendgrid_config.registry_reloaded")
