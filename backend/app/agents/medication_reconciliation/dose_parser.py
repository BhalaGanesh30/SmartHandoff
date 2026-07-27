"""Utility for parsing dose strings into numeric value + unit.

US-030 TASK-003: Extracts structured dose information from free-text dose
strings in FHIR medication resources.

Design refs:
    - US-030 TASK-003 — RxNorm Normalisation Service (dose parsing component)
    - US-030 TASK-001 — dose_value and dose_unit ORM fields
"""
from __future__ import annotations

import re

# Regex pattern for common dose formats
# Matches:
#   - "500 mg" → value=500, unit=mg
#   - "2.5mg" → value=2.5, unit=mg
#   - "1000 MG" → value=1000, unit=mg (case-insensitive)
#   - "10 units" → value=10, unit=units
#   - "5.5 IU" → value=5.5, unit=iu
_DOSE_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mg|g|mcg|ml|units?|iu|meq)",
    re.IGNORECASE,
)


def parse_dose(dose_string: str | None) -> tuple[float | None, str | None]:
    """Parse a dose string into (value, unit).

    Args:
        dose_string: Raw dose string from FHIR (e.g. "500 mg", "2.5mg", "as directed").

    Returns:
        Tuple of (numeric_value, unit_string) or (None, None) if unparseable.

    Examples::

        >>> parse_dose("500 mg")
        (500.0, "mg")

        >>> parse_dose("2.5mg")
        (2.5, "mg")

        >>> parse_dose("1000 MG")
        (1000.0, "mg")

        >>> parse_dose("10 units")
        (10.0, "units")

        >>> parse_dose("as directed")
        (None, None)

        >>> parse_dose(None)
        (None, None)

    Notes:
        - Supported units: mg, g, mcg, ml, units/unit, iu, meq
        - Unit is normalized to lowercase
        - First match is returned if multiple dose values present
        - Returns (None, None) for unparseable strings (e.g. "as directed", "PRN")

    Design refs:
        US-030 TASK-003 — DoseParser utility
        US-030 TASK-001 — dose_value, dose_unit ORM columns
    """
    if not dose_string:
        return None, None
    
    match = _DOSE_PATTERN.search(dose_string)
    if match:
        value = float(match.group("value"))
        unit = match.group("unit").lower()
        return value, unit
    
    return None, None
