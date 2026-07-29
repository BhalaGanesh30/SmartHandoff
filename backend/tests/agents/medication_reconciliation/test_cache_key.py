"""Unit tests for DrugInteractionCache key symmetry."""
from __future__ import annotations

from app.agents.medication_reconciliation.drug_interaction.cache import (
    _build_cache_key,
)


def test_cache_key_is_order_independent() -> None:
    """Reversed CUI pair must produce identical key."""
    assert _build_cache_key("11289", "1191") == _build_cache_key("1191", "11289")


def test_cache_key_format() -> None:
    key = _build_cache_key("11289", "1191")
    assert key.startswith("drug-interaction:")
    parts = key.split(":")
    assert len(parts) == 3
    assert parts[1] < parts[2]  # sorted ascending
