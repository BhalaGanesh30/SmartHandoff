"""Hot-reloadable YAML weight loader for BedScoringAlgorithm.

Reads ``config/bed_scoring_weights.yaml`` on each call to ``load_weights()``.
No caching — caller may wrap with an LRU cache if performance requires it
(not needed at <5,000 ADT events/day; US-037 Technical Notes).

Design refs:
    US-037 Technical Notes — hot-reloadable without deployment
    US-037 AC Scenario 3   — configurable weights; sum must equal 1.0
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_WEIGHTS_PATH = Path(__file__).parents[4] / "config" / "bed_scoring_weights.yaml"


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    """Immutable weight container for a single scoring run."""

    acuity: float
    care_type: float
    isolation: float
    gender: float

    def validate(self) -> None:
        """Raise ``ValueError`` if weights do not sum to 1.0 (±0.001 tolerance)."""
        total = self.acuity + self.care_type + self.isolation + self.gender
        if not (0.999 <= total <= 1.001):
            raise ValueError(
                f"Scoring weights must sum to 1.0; got {total:.4f}. "
                "Check config/bed_scoring_weights.yaml."
            )


def load_weights(path: Path | None = None) -> ScoringWeights:
    """Load and validate scoring weights from the YAML config file.

    Args:
        path: Override path for testing. Defaults to
              ``backend/config/bed_scoring_weights.yaml``.

    Returns:
        Validated :class:`ScoringWeights` instance.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        ValueError: If weights do not sum to 1.0.
        KeyError: If expected weight keys are missing from the YAML.
    """
    config_path = path or Path(
        os.environ.get("BED_SCORING_WEIGHTS_PATH", str(_DEFAULT_WEIGHTS_PATH))
    )
    logger.debug("Loading bed scoring weights from %s", config_path)
    with config_path.open() as fh:
        raw = yaml.safe_load(fh)

    w = raw["weights"]
    weights = ScoringWeights(
        acuity=float(w["acuity"]),
        care_type=float(w["care_type"]),
        isolation=float(w["isolation"]),
        gender=float(w["gender"]),
    )
    weights.validate()
    return weights
