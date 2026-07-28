"""Loader and validator for high_risk_drugs.yaml configuration.

Reads the YAML config at startup and exposes a pre-built reverse lookup dict
for O(1) drug-name → class resolution.

Design refs:
    US-032 Technical Notes — case-insensitive name match; YAML config
    US-032 DoD             — extensible list; config/high_risk_drugs.yaml
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH: Final[Path] = (
    Path(__file__).parents[4] / "config" / "high_risk_drugs.yaml"
)


class HighRiskDrugConfig:
    """Parsed and validated high-risk drug class configuration.

    Attributes:
        class_to_drugs: Mapping of drug-class name → set of lower-cased drug names.
        drug_to_class: Reverse mapping of lower-cased drug name → drug-class name.
    """

    def __init__(self, config_path: Path = _DEFAULT_CONFIG_PATH) -> None:
        self._path = config_path
        self.class_to_drugs: dict[str, set[str]] = {}
        self.drug_to_class: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """Parse YAML, build reverse lookup, and validate no duplicate drug names."""
        if not self._path.exists():
            raise FileNotFoundError(
                f"High-risk drug config not found: {self._path}. "
                "Ensure config/high_risk_drugs.yaml is present in the container."
            )

        with self._path.open("r", encoding="utf-8") as fh:
            raw: dict = yaml.safe_load(fh)

        classes: dict[str, list[str]] = raw.get("high_risk_drug_classes", {})
        if not classes:
            raise ValueError(
                "high_risk_drugs.yaml: 'high_risk_drug_classes' key is empty or missing."
            )

        seen: dict[str, str] = {}
        for drug_class, drug_names in classes.items():
            normalised = {name.strip().lower() for name in drug_names}
            duplicates = normalised & set(seen)
            if duplicates:
                raise ValueError(
                    f"Duplicate drug names across classes: {duplicates}. "
                    f"Each drug must map to exactly one class."
                )
            for drug_name in normalised:
                seen[drug_name] = drug_class
            self.class_to_drugs[drug_class] = normalised

        self.drug_to_class = seen
        logger.info(
            "HighRiskDrugConfig loaded: %d classes, %d drugs",
            len(self.class_to_drugs),
            len(self.drug_to_class),
        )


# Module-level singleton loaded once at import time.
# Override in tests by patching `high_risk_drug_config` in this module.
high_risk_drug_config = HighRiskDrugConfig()
