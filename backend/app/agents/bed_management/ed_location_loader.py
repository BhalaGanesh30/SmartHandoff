"""Hot-reloadable ED location code loader.

Reads ``config/ed_locations.yaml`` to determine which HL7 PV1-3 location
codes identify the Emergency Department. Loaded on each BoardingMonitor
cycle — no caching required at poll frequency of 5 minutes.

Design refs:
    US-038 Technical Notes — configurable list in config/ed_locations.yaml
    US-038 AC Scenario 1   — encounters with patient_location=ED qualify
    US-038 TASK-001        — hot-reloadable location code loader
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parents[4] / "config" / "ed_locations.yaml"


def load_ed_location_codes(path: Path | None = None) -> frozenset[str]:
    """Return the set of HL7 PV1-3 codes that identify the ED.

    Args:
        path: Optional override path to the YAML file.
              Defaults to ``config/ed_locations.yaml``.

    Returns:
        A frozenset of uppercase location code strings.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If ``ed_location_codes`` key is missing or empty.

    Example:
        >>> codes = load_ed_location_codes()
        >>> "ED" in codes
        True
        >>> "EMERG" in codes
        True
        >>> "3A" in codes
        False
    """
    config_path = path or _DEFAULT_CONFIG_PATH
    with config_path.open("r") as fh:
        data = yaml.safe_load(fh)

    codes = data.get("ed_location_codes")
    if not codes:
        raise ValueError(
            f"ed_locations.yaml at {config_path} has no 'ed_location_codes' entries."
        )

    normalised = frozenset(str(c).upper() for c in codes)
    logger.debug("Loaded %d ED location codes from %s", len(normalised), config_path)
    return normalised
