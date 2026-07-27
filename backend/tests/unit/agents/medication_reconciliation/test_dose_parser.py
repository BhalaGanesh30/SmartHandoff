"""Unit tests for DoseParser utility.

US-030 TASK-006: Validates dose string parsing for common formats.
"""
from __future__ import annotations

import pytest

from app.agents.medication_reconciliation.dose_parser import parse_dose


@pytest.mark.parametrize(
    "dose_string,expected_value,expected_unit",
    [
        ("500 mg", 500.0, "mg"),
        ("2.5mg", 2.5, "mg"),
        ("1000 MG", 1000.0, "mg"),
        ("5000 units", 5000.0, "units"),
        ("50 mcg", 50.0, "mcg"),
        ("100 unit", 100.0, "unit"),
        ("2.5 IU", 2.5, "iu"),
        ("75 meq", 75.0, "meq"),
    ],
    ids=[
        "standard-mg-with-space",
        "decimal-mg-no-space",
        "uppercase-mg",
        "units-plural",
        "mcg-microgram",
        "unit-singular",
        "iu-case-insensitive",
        "meq-milliequivalent",
    ],
)
@pytest.mark.unit
def test_parse_dose_valid(dose_string: str, expected_value: float, expected_unit: str):
    """Test parsing of valid dose strings."""
    value, unit = parse_dose(dose_string)
    assert value == expected_value, f"Expected value {expected_value}, got {value}"
    assert unit == expected_unit, f"Expected unit {expected_unit}, got {unit}"


@pytest.mark.parametrize(
    "dose_string",
    [
        "as directed",
        "one tablet",
        "PRN",
        "take with food",
        "",
        None,
    ],
    ids=[
        "as-directed-text",
        "written-out-number",
        "prn-abbreviation",
        "instruction-text",
        "empty-string",
        "none-value",
    ],
)
@pytest.mark.unit
def test_parse_dose_invalid_returns_none(dose_string: str | None):
    """Test that unparseable dose strings return (None, None)."""
    value, unit = parse_dose(dose_string)
    assert value is None, f"Expected None value, got {value}"
    assert unit is None, f"Expected None unit, got {unit}"


@pytest.mark.unit
def test_parse_dose_first_match_wins():
    """Test that when multiple doses appear, first match is returned."""
    dose_string = "500 mg twice daily"
    value, unit = parse_dose(dose_string)
    assert value == 500.0
    assert unit == "mg"


@pytest.mark.unit
def test_parse_dose_unit_normalized_to_lowercase():
    """Test that unit is normalized to lowercase regardless of input case."""
    value, unit = parse_dose("100 MG")
    assert unit == "mg", "Unit should be lowercase"
    
    value, unit = parse_dose("50 McG")
    assert unit == "mcg", "Unit should be lowercase"
