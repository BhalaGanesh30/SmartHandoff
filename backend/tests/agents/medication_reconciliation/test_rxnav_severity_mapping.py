"""Unit tests for RxNav severity string → InteractionSeverity mapping."""
from __future__ import annotations

import pytest

from app.agents.medication_reconciliation.drug_interaction.rxnav_client import (
    InteractionSeverity,
    _map_severity,
)


@pytest.mark.parametrize(
    "rxnav_label, expected",
    [
        ("major", InteractionSeverity.HIGH),
        ("Major", InteractionSeverity.HIGH),
        ("MAJOR", InteractionSeverity.HIGH),
        ("contraindicated", InteractionSeverity.HIGH),
        ("Contraindicated", InteractionSeverity.HIGH),
        ("moderate", InteractionSeverity.MEDIUM),
        ("Moderate", InteractionSeverity.MEDIUM),
        ("minor", InteractionSeverity.LOW),
        ("Minor", InteractionSeverity.LOW),
        ("unknown_label", InteractionSeverity.LOW),
    ],
)
def test_severity_mapping(rxnav_label: str, expected: InteractionSeverity) -> None:
    assert _map_severity(rxnav_label) == expected
