"""Pydantic configuration model for risk tier care pathways.

Parses and validates `backend/config/care_pathways.yaml` at application startup.
Loaded into `app.state.care_pathways` by the FollowUpCareAgent FastAPI lifespan.

Usage:
    from app.config.care_pathways import load_care_pathways, CarePathwayConfig

    pathways = load_care_pathways()
    high_pathway = pathways["HIGH"]
    # high_pathway.followup_days == 7
    # high_pathway.alert_care_manager == True

Design refs:
    US-040 DoD — config/care_pathways.yaml with configurable follow-up days
    US-040 AC Scenarios 2, 3, 4 — tier-specific followup_days, appointment_type, alert flag
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Resolved at import time — works for both local dev and Cloud Run container
_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "care_pathways.yaml"


class TierPathwayConfig(BaseModel):
    """Configuration for a single risk tier pathway.

    Attributes:
        followup_days:         Calendar days from discharge_date to set appointment target_date.
        appointment_type:      AppointmentType enum value for the created appointment record.
        alert_care_manager:    Whether to publish a CARE_MANAGER_ALERT to notification-requests.
        required_followup_days: Days value embedded in the CARE_MANAGER_ALERT payload (HIGH only).
    """

    followup_days: int = Field(..., gt=0, description="Calendar days from discharge for follow-up")
    appointment_type: str = Field(..., description="AppointmentType enum value")
    alert_care_manager: bool = Field(..., description="Whether to publish CARE_MANAGER_ALERT")
    required_followup_days: int | None = Field(
        None,
        description="Days value in alert payload; None for non-alert tiers",
    )


CarePathwayConfig = dict[str, TierPathwayConfig]


@lru_cache(maxsize=1)
def load_care_pathways(config_path: Path = _CONFIG_PATH) -> CarePathwayConfig:
    """Load and validate care pathway configuration from YAML.

    Cached after first call — the YAML file is read once at startup.

    Args:
        config_path: Absolute path to care_pathways.yaml (defaults to bundled config).

    Returns:
        Dict mapping risk tier string (HIGH/MEDIUM/LOW) to TierPathwayConfig.

    Raises:
        FileNotFoundError: If care_pathways.yaml does not exist at config_path.
        pydantic.ValidationError: If the YAML structure does not match TierPathwayConfig.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Care pathway config not found: {config_path}")

    with config_path.open() as f:
        raw = yaml.safe_load(f)

    pathways: CarePathwayConfig = {
        tier: TierPathwayConfig(**values)
        for tier, values in raw["care_pathways"].items()
    }

    logger.info(
        "Care pathway config loaded",
        extra={"tiers": list(pathways.keys()), "config_path": str(config_path)},
    )
    return pathways
