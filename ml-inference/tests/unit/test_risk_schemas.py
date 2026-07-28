"""Unit tests for assign_risk_tier() boundary conditions.

US-039 AC Scenario 2:
    probability=0.25 → LOW
    probability=0.55 → MEDIUM
    probability=0.72 → HIGH
    Boundary LOW/MEDIUM: 0.30
    Boundary MEDIUM/HIGH: 0.70
"""
import pytest

from app.schemas import RiskTier, assign_risk_tier


class TestAssignRiskTier:
    def test_low_tier_below_threshold(self):
        assert assign_risk_tier(0.25) == RiskTier.LOW

    def test_low_tier_at_zero(self):
        assert assign_risk_tier(0.0) == RiskTier.LOW

    def test_low_tier_just_below_medium_boundary(self):
        assert assign_risk_tier(0.2999) == RiskTier.LOW

    def test_medium_tier_at_low_boundary(self):
        """0.30 is inclusive of MEDIUM."""
        assert assign_risk_tier(0.30) == RiskTier.MEDIUM

    def test_medium_tier_midpoint(self):
        assert assign_risk_tier(0.55) == RiskTier.MEDIUM

    def test_medium_tier_just_below_high_boundary(self):
        assert assign_risk_tier(0.6999) == RiskTier.MEDIUM

    def test_high_tier_at_medium_high_boundary(self):
        """0.70 is inclusive of HIGH."""
        assert assign_risk_tier(0.70) == RiskTier.HIGH

    def test_high_tier_above_boundary(self):
        assert assign_risk_tier(0.72) == RiskTier.HIGH

    def test_high_tier_at_one(self):
        assert assign_risk_tier(1.0) == RiskTier.HIGH
