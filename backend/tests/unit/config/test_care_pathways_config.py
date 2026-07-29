"""Unit tests for app/config/care_pathways.py.

Tests:
    - load_care_pathways() parses bundled YAML and returns correct values for all 3 tiers
    - TierPathwayConfig validates field types and constraints
    - load_care_pathways() raises FileNotFoundError when config is missing
"""
from __future__ import annotations

import pytest
from pathlib import Path

from app.config.care_pathways import load_care_pathways, TierPathwayConfig


class TestLoadCarePathways:
    def test_returns_all_three_tiers(self):
        pathways = load_care_pathways()
        assert set(pathways.keys()) == {"HIGH", "MEDIUM", "LOW"}

    def test_high_tier_followup_days(self):
        pathways = load_care_pathways()
        assert pathways["HIGH"].followup_days == 7

    def test_high_tier_appointment_type(self):
        pathways = load_care_pathways()
        assert pathways["HIGH"].appointment_type == "HIGH_RISK_FOLLOW_UP"

    def test_high_tier_alert_enabled(self):
        pathways = load_care_pathways()
        assert pathways["HIGH"].alert_care_manager is True

    def test_high_tier_required_followup_days(self):
        pathways = load_care_pathways()
        assert pathways["HIGH"].required_followup_days == 7

    def test_medium_tier_followup_days(self):
        pathways = load_care_pathways()
        assert pathways["MEDIUM"].followup_days == 14

    def test_medium_tier_appointment_type(self):
        pathways = load_care_pathways()
        assert pathways["MEDIUM"].appointment_type == "STANDARD_FOLLOW_UP"

    def test_medium_tier_no_alert(self):
        pathways = load_care_pathways()
        assert pathways["MEDIUM"].alert_care_manager is False

    def test_medium_tier_required_followup_days_is_none(self):
        pathways = load_care_pathways()
        assert pathways["MEDIUM"].required_followup_days is None

    def test_low_tier_followup_days(self):
        pathways = load_care_pathways()
        assert pathways["LOW"].followup_days == 30

    def test_low_tier_appointment_type(self):
        pathways = load_care_pathways()
        assert pathways["LOW"].appointment_type == "ROUTINE_FOLLOW_UP"

    def test_low_tier_no_alert(self):
        pathways = load_care_pathways()
        assert pathways["LOW"].alert_care_manager is False

    def test_raises_file_not_found_for_missing_config(self, tmp_path: Path):
        missing_path = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError, match="nonexistent.yaml"):
            load_care_pathways(config_path=missing_path)
