"""Unit tests for SLA configuration loader.

US-021 DoD: Config loading validated.
US-021 Scenario 4: Per-agent thresholds correctly parsed and accessible.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.config.sla_loader import SLAConfig, load_sla_config


@pytest.fixture
def valid_yaml(tmp_path: Path) -> Path:
    content = textwrap.dedent("""\
        sla_thresholds:
          DOCUMENTATION: 30
          MEDICATION_RECONCILIATION: 60
          BED_MANAGEMENT: 15
          FOLLOW_UP_CARE: 120
          PATIENT_COMMUNICATION: 30
        monitor_interval_seconds: 300
        escalation_dedup_window_minutes: 30
    """)
    p = tmp_path / "sla_config.yaml"
    p.write_text(content)
    return p


def test_load_returns_sla_config(valid_yaml: Path) -> None:
    load_sla_config.cache_clear()
    config = load_sla_config(valid_yaml)
    assert isinstance(config, SLAConfig)


def test_bed_management_threshold_is_15(valid_yaml: Path) -> None:
    """US-021 Scenario 4: BED_MANAGEMENT SLA = 15 minutes."""
    load_sla_config.cache_clear()
    config = load_sla_config(valid_yaml)
    assert config.threshold_for("BED_MANAGEMENT") == 15


def test_documentation_threshold_is_30(valid_yaml: Path) -> None:
    """US-021 Scenario 4: DOCUMENTATION SLA = 30 minutes."""
    load_sla_config.cache_clear()
    config = load_sla_config(valid_yaml)
    assert config.threshold_for("DOCUMENTATION") == 30


def test_missing_agent_type_raises(tmp_path: Path) -> None:
    """Fail-fast if a known agent type is absent from the YAML."""
    content = textwrap.dedent("""\
        sla_thresholds:
          DOCUMENTATION: 30
        monitor_interval_seconds: 300
        escalation_dedup_window_minutes: 30
    """)
    p = tmp_path / "sla_config.yaml"
    p.write_text(content)
    load_sla_config.cache_clear()
    with pytest.raises(ValueError, match="missing thresholds"):
        load_sla_config(p)


def test_zero_threshold_raises(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        sla_thresholds:
          DOCUMENTATION: 0
          MEDICATION_RECONCILIATION: 60
          BED_MANAGEMENT: 15
          FOLLOW_UP_CARE: 120
          PATIENT_COMMUNICATION: 30
        monitor_interval_seconds: 300
        escalation_dedup_window_minutes: 30
    """)
    p = tmp_path / "sla_config.yaml"
    p.write_text(content)
    load_sla_config.cache_clear()
    with pytest.raises(ValueError, match="must be > 0"):
        load_sla_config(p)


def test_missing_file_raises(tmp_path: Path) -> None:
    load_sla_config.cache_clear()
    with pytest.raises(FileNotFoundError):
        load_sla_config(tmp_path / "nonexistent.yaml")
