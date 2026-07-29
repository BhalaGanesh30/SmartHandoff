"""Unit tests for HighRiskDrugClassDetector.

Design refs:
    US-032 AC Scenario 1 — detection per drug class
    US-032 Technical Notes — case-insensitive; dose-stripped matching
"""
from __future__ import annotations

import pytest

from app.agents.medication_reconciliation.drug_interaction.checker import (
    DischargedMedication,
)
from app.agents.medication_reconciliation.high_risk.detector import (
    HighRiskDrugClassDetector,
)
from app.agents.medication_reconciliation.high_risk.config_loader import (
    HighRiskDrugConfig,
)
from pathlib import Path

# Use the real YAML config for integration-style unit tests
_REAL_CONFIG = HighRiskDrugConfig(
    Path(__file__).parents[3] / "config" / "high_risk_drugs.yaml"
)


@pytest.fixture
def detector() -> HighRiskDrugClassDetector:
    return HighRiskDrugClassDetector(config=_REAL_CONFIG)


@pytest.mark.parametrize(
    "drug_name, expected_class",
    [
        # ANTICOAGULANT
        ("Warfarin 5mg", "ANTICOAGULANT"),
        ("Heparin 5000 Units/mL", "ANTICOAGULANT"),
        ("Enoxaparin 40mg", "ANTICOAGULANT"),
        ("Rivaroxaban 20mg", "ANTICOAGULANT"),
        # INSULIN
        ("Insulin Glargine 100 Units/mL", "INSULIN"),
        ("Insulin Aspart 10 Units", "INSULIN"),
        ("Insulin NPH 70/30", "INSULIN"),
        # OPIOID
        ("Oxycodone 10mg ER", "OPIOID"),
        ("Hydrocodone 5mg", "OPIOID"),
        ("Morphine Sulfate 15mg", "OPIOID"),
        ("Fentanyl 25mcg patch", "OPIOID"),
        # CHEMOTHERAPY
        ("Methotrexate 2.5mg", "CHEMOTHERAPY"),
        ("Cyclophosphamide 50mg", "CHEMOTHERAPY"),
    ],
)
def test_detects_high_risk_drug_class(
    detector: HighRiskDrugClassDetector, drug_name: str, expected_class: str
) -> None:
    """Each high-risk drug name must match the correct ISMP class."""
    meds = [DischargedMedication(rxcui="00000", drug_name=drug_name)]
    matches = detector.detect(meds)
    assert len(matches) == 1
    assert matches[0].drug_class == expected_class
    assert matches[0].severity == "HIGH"


def test_non_high_risk_drug_returns_no_match(
    detector: HighRiskDrugClassDetector,
) -> None:
    """Non-high-risk drugs must not trigger a detection."""
    meds = [DischargedMedication(rxcui="00001", drug_name="Amoxicillin 500mg")]
    assert detector.detect(meds) == []


def test_detection_is_case_insensitive(detector: HighRiskDrugClassDetector) -> None:
    """Drug name matching must be case-insensitive."""
    meds = [DischargedMedication(rxcui="00002", drug_name="WARFARIN 5MG")]
    matches = detector.detect(meds)
    assert len(matches) == 1
    assert matches[0].drug_class == "ANTICOAGULANT"


def test_multiple_high_risk_drugs_returns_multiple_matches(
    detector: HighRiskDrugClassDetector,
) -> None:
    """A list with multiple high-risk drugs must return one match per drug."""
    meds = [
        DischargedMedication(rxcui="11289", drug_name="Warfarin 5mg"),
        DischargedMedication(rxcui="7804", drug_name="Oxycodone 10mg"),
    ]
    matches = detector.detect(meds)
    assert len(matches) == 2
    classes = {m.drug_class for m in matches}
    assert classes == {"ANTICOAGULANT", "OPIOID"}


def test_dose_stripped_before_matching(detector: HighRiskDrugClassDetector) -> None:
    """Dose tokens must be stripped before lookup."""
    # "morphine 15 mg" after stripping → "morphine"
    meds = [DischargedMedication(rxcui="7052", drug_name="morphine 15 mg")]
    matches = detector.detect(meds)
    assert len(matches) == 1
    assert matches[0].normalised_name == "morphine"


def test_empty_medication_list_returns_empty(
    detector: HighRiskDrugClassDetector,
) -> None:
    """Empty input list must return an empty result."""
    assert detector.detect([]) == []
