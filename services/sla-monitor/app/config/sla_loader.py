"""SLA configuration loader — single source of truth for per-agent SLA thresholds.

Loads `sla_config.yaml` from the directory containing this module.
Provides a validated `SLAConfig` dataclass accessible to the SLAMonitor
and task status API endpoint.

US-021 DoD: SLA thresholds stored as application config — not hardcoded.
US-021 Scenario 4: Per-agent SLA threshold applied correctly by monitor.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "sla_config.yaml"

# All agent types defined in the system. Loader validates that the YAML
# provides a threshold for every agent type before the monitor starts.
KNOWN_AGENT_TYPES: frozenset[str] = frozenset(
    {
        "DOCUMENTATION",
        "MEDICATION_RECONCILIATION",
        "BED_MANAGEMENT",
        "FOLLOW_UP_CARE",
        "PATIENT_COMMUNICATION",
    }
)


class AgentSLAEntry(BaseModel):
    """Single agent SLA configuration entry.
    
    US-034: Extended to support reference_field for admission-time SLAs.
    
    Attributes:
        threshold_minutes: SLA window in minutes.
        reference_field: Timestamp field used as SLA start (created_at or admit_time).
        escalation_type: Notification type to send on breach.
        priority: Escalation priority level.
        description: Human-readable description of this SLA.
    """

    threshold_minutes: int
    reference_field: str = "created_at"  # US-034: admit_time for admission SLAs
    escalation_type: str = "SUPERVISOR_ESCALATION"
    priority: str = "NORMAL"
    description: str = ""


class SLAConfig(BaseModel):
    """Validated SLA configuration loaded from sla_config.yaml.

    US-034: Updated to use AgentSLAEntry with reference_field support.

    Attributes:
        agents: Mapping of agent_type → AgentSLAEntry.
        monitor_interval_seconds: Background job polling interval.
        escalation_dedup_window_minutes: Idempotency window for escalations.
    """

    agents: dict[str, AgentSLAEntry] = Field(
        ...,
        description="Per-agent SLA configuration entries.",
    )
    monitor_interval_seconds: int = Field(
        default=300,
        ge=60,
        description="SLA monitor polling interval in seconds.",
    )
    escalation_dedup_window_minutes: int = Field(
        default=30,
        ge=1,
        description="Idempotency window to suppress duplicate escalations.",
    )

    @field_validator("agents")
    @classmethod
    def _all_thresholds_positive(cls, v: dict[str, AgentSLAEntry]) -> dict[str, AgentSLAEntry]:
        """Reject any threshold ≤ 0."""
        for agent_type, entry in v.items():
            if entry.threshold_minutes <= 0:
                raise ValueError(
                    f"SLA threshold for {agent_type!r} must be > 0, got {entry.threshold_minutes}"
                )
        return v

    @model_validator(mode="after")
    def _all_agent_types_covered(self) -> "SLAConfig":
        """Fail-fast if the YAML is missing a threshold for any known agent type."""
        missing = KNOWN_AGENT_TYPES - set(self.agents.keys())
        if missing:
            raise ValueError(
                f"sla_config.yaml is missing thresholds for agent types: {sorted(missing)}"
            )
        return self

    def threshold_for(self, agent_type: str) -> int:
        """Return SLA threshold (minutes) for the given agent type.

        Falls back to a conservative 30-minute default for unknown agent types
        introduced after the YAML was last updated, and logs a warning.
        
        Args:
            agent_type: The agent type to get threshold for.
            
        Returns:
            SLA threshold in minutes.
        """
        if agent_type not in self.agents:
            logger.warning(
                "No SLA threshold configured for agent_type=%r; defaulting to 30 minutes",
                agent_type,
            )
            return 30
        return self.agents[agent_type].threshold_minutes
    
    def med_reconciliation_admission_entry(self) -> AgentSLAEntry:
        """Return the MEDICATION_RECONCILIATION_ADMISSION SLA entry.
        
        US-034: Provides access to admission-time SLA configuration.

        Raises:
            KeyError: If the entry is missing from sla_config.yaml.
            
        Returns:
            AgentSLAEntry for medication reconciliation admission SLA.
        """
        return self.agents["MEDICATION_RECONCILIATION_ADMISSION"]


@lru_cache(maxsize=1)
def load_sla_config(config_path: Path = _CONFIG_PATH) -> SLAConfig:
    """Load and validate SLA configuration from YAML.

    Cached after first call — the YAML file is read once at startup.
    Tests can bypass the cache by calling `load_sla_config.cache_clear()`.

    Args:
        config_path: Path to the YAML config file. Defaults to the bundled
                     ``sla_config.yaml`` next to this module.

    Returns:
        Validated :class:`SLAConfig` instance.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        ValueError: If required agent types are missing or values are invalid.
    """
    if not config_path.exists():
        raise FileNotFoundError(
            f"SLA configuration file not found: {config_path}. "
            "Ensure sla_config.yaml is present in app/config/."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    config = SLAConfig(**raw)
    logger.info(
        "SLA configuration loaded: %d agent types, monitor_interval=%ds",
        len(config.agents),
        config.monitor_interval_seconds,
    )
    return config
