"""Unit tests for GroupResolver — US-022 DoD: group routing logic tests.

Covers:
  - Nurse in unit 3A joins role-nurse, unit-3A, and per-encounter groups.
  - Pharmacist (no unit) joins role-pharmacist and per-encounter groups only.
  - Nurse in unit 4B does NOT appear in unit-3A groups (isolation test).
  - User with no encounter_ids joins only role and unit groups.
  - Group name format matches US-022 DoD naming convention exactly.
"""
from __future__ import annotations

import pytest

from app.signalr.group_resolver import GroupResolver, UserClaims


@pytest.fixture
def resolver() -> GroupResolver:
    return GroupResolver()


class TestGroupResolverNurseUnit3A:
    def test_nurse_3a_joins_role_group(self, resolver):
        claims = UserClaims(user_id="u1", role="nurse", unit_id="3A", encounter_ids=["enc-abc"])
        groups = resolver.resolve(claims)
        assert "role-nurse" in groups

    def test_nurse_3a_joins_unit_group(self, resolver):
        claims = UserClaims(user_id="u1", role="nurse", unit_id="3A", encounter_ids=[])
        groups = resolver.resolve(claims)
        assert "unit-3A" in groups

    def test_nurse_3a_joins_encounter_group(self, resolver):
        claims = UserClaims(user_id="u1", role="nurse", unit_id="3A", encounter_ids=["enc-abc"])
        groups = resolver.resolve(claims)
        assert "encounter-enc-abc" in groups

    def test_nurse_3a_does_not_join_unit_4b(self, resolver):
        """US-022 Scenario 2: nurse in unit 3A must NOT be in unit-4B group."""
        claims = UserClaims(user_id="u1", role="nurse", unit_id="3A", encounter_ids=[])
        groups = resolver.resolve(claims)
        assert "unit-4B" not in groups


class TestGroupResolverPharmacist:
    def test_pharmacist_joins_role_group(self, resolver):
        claims = UserClaims(user_id="u2", role="pharmacist", unit_id=None, encounter_ids=["enc-xyz"])
        groups = resolver.resolve(claims)
        assert "role-pharmacist" in groups

    def test_pharmacist_without_unit_has_no_unit_group(self, resolver):
        claims = UserClaims(user_id="u2", role="pharmacist", unit_id=None, encounter_ids=[])
        groups = resolver.resolve(claims)
        unit_groups = [g for g in groups if g.startswith("unit-")]
        assert len(unit_groups) == 0

    def test_pharmacist_joins_encounter_group(self, resolver):
        """US-022 Scenario 2: pharmacist receives medication reconciliation event via role group."""
        claims = UserClaims(user_id="u2", role="pharmacist", unit_id=None, encounter_ids=["enc-xyz"])
        groups = resolver.resolve(claims)
        assert "encounter-enc-xyz" in groups


class TestGroupResolverNamingConvention:
    """US-022 DoD: group naming convention must be encounter-{id}, unit-{unitId}, role-{roleName}."""

    def test_group_names_use_correct_prefix_format(self, resolver):
        claims = UserClaims(user_id="u3", role="physician", unit_id="ICU", encounter_ids=["enc-001", "enc-002"])
        groups = resolver.resolve(claims)
        for g in groups:
            assert g.startswith(("role-", "unit-", "encounter-")), f"Unexpected group prefix: {g}"

    def test_multiple_encounters_all_resolved(self, resolver):
        enc_ids = ["enc-001", "enc-002", "enc-003"]
        claims = UserClaims(user_id="u4", role="nurse", unit_id="2B", encounter_ids=enc_ids)
        groups = resolver.resolve(claims)
        for enc_id in enc_ids:
            assert f"encounter-{enc_id}" in groups


class TestGroupResolverEdgeCases:
    def test_user_with_no_encounters_no_unit(self, resolver):
        """User with only role claim (e.g., admin)."""
        claims = UserClaims(user_id="u5", role="admin", unit_id=None, encounter_ids=[])
        groups = resolver.resolve(claims)
        assert groups == ["role-admin"]

    def test_empty_encounter_list_does_not_add_empty_groups(self, resolver):
        """Empty encounter_ids should not produce encounter- groups."""
        claims = UserClaims(user_id="u6", role="nurse", unit_id="2A", encounter_ids=[])
        groups = resolver.resolve(claims)
        encounter_groups = [g for g in groups if g.startswith("encounter-")]
        assert len(encounter_groups) == 0

    def test_deterministic_order_for_multiple_encounters(self, resolver):
        """Ensure encounter groups are sorted for predictable output."""
        claims = UserClaims(
            user_id="u7",
            role="physician",
            unit_id="ICU",
            encounter_ids=["enc-zzz", "enc-aaa", "enc-mmm"]
        )
        groups = resolver.resolve(claims)
        encounter_groups = [g for g in groups if g.startswith("encounter-")]
        # Should be sorted alphabetically by encounter_id
        assert encounter_groups == ["encounter-enc-aaa", "encounter-enc-mmm", "encounter-enc-zzz"]
