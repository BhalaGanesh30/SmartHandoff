"""Pytest configuration for medication reconciliation tests."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Mock all FHIR dependencies to avoid import errors in unit tests
# This must be done before any app modules are imported
fhir_modules = [
    'fhir',
    'fhir.resources',
    'fhir.resources.allergyintolerance',
    'fhir.resources.bundle',
    'fhir.resources.condition',
    'fhir.resources.encounter',
    'fhir.resources.medicationadministration',
    'fhir.resources.medicationrequest',
    'fhir.resources.medicationstatement',
    'fhir.resources.patient',
    'fhir.resources.medication',
]

for module in fhir_modules:
    sys.modules[module] = MagicMock()

# Mock other problematic dependencies
sys.modules['textstat'] = MagicMock()
sys.modules['agents.documentation'] = MagicMock()
sys.modules['agents.documentation.agent'] = MagicMock()
sys.modules['agents.documentation.reading_level_scorer'] = MagicMock()
