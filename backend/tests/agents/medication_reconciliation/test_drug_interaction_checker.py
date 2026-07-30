"""Unit tests for DrugInteractionChecker — US-031 AC Scenarios 1–4.

Test matrix:
    - HIGH interaction path (Warfarin + Aspirin from RxNav)
    - Cache hit path (RxNav not called on second lookup)
    - OpenFDA fallback (RxNav HTTP 503)
    - Offline degradation (both APIs fail)
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agents.medication_reconciliation.drug_interaction.cache import (
    DrugInteractionCache,
)
from app.agents.medication_reconciliation.drug_interaction.checker import (
    DischargedMedication,
    DrugInteractionChecker,
)
from app.agents.medication_reconciliation.drug_interaction.rxnav_client import (
    RxNavUnavailableError,
)
from app.agents.medication_reconciliation.drug_interaction.openfda_client import (
    OpenFDAUnavailableError,
)

WARFARIN = DischargedMedication(rxcui="11289", drug_name="Warfarin")
ASPIRIN = DischargedMedication(rxcui="1191", drug_name="Aspirin")
METFORMIN = DischargedMedication(rxcui="6809", drug_name="Metformin")

_RXNAV_HIGH_INTERACTION = {
    "rxcui1": "11289",
    "rxcui2": "1191",
    "drug1": "Warfarin",
    "drug2": "Aspirin",
    "severity": "HIGH",
    "description": "Concurrent use increases bleeding risk.",
    "source": "RXNAV",
}


@pytest.fixture
def mock_cache() -> AsyncMock:
    cache = AsyncMock(spec=DrugInteractionCache)
    cache.get.return_value = None  # default: cache miss
    return cache


@pytest.fixture
def mock_rxnav() -> AsyncMock:
    rxnav = AsyncMock()
    rxnav.get_interactions.return_value = [_RXNAV_HIGH_INTERACTION]
    return rxnav


@pytest.fixture
def mock_openfda() -> AsyncMock:
    openfda = AsyncMock()
    openfda.get_interactions.return_value = [
        {
            "drug1": "Warfarin",
            "drug2": None,
            "description": "May interact with antiplatelet agents.",
            "severity": "UNKNOWN",
            "source": "OPENFDA",
        }
    ]
    return openfda


# ---------------------------------------------------------------------------
# Scenario 1: HIGH interaction — Warfarin + Aspirin → RxNav → severity=HIGH
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_high_severity_interaction_returned_from_rxnav(
    mock_cache: AsyncMock,
    mock_rxnav: AsyncMock,
    mock_openfda: AsyncMock,
) -> None:
    """AC Scenario 1 — RxNav returns HIGH severity for Warfarin + Aspirin."""
    checker = DrugInteractionChecker(
        cache=mock_cache, rxnav_client=mock_rxnav, openfda_client=mock_openfda
    )

    result = await checker.check([WARFARIN, ASPIRIN])

    assert result.interaction_check_status == "COMPLETE"
    assert len(result.interactions) == 1
    interaction = result.interactions[0]
    assert interaction["severity"] == "HIGH"
    assert interaction["source"] == "RXNAV"
    assert set(interaction[k] for k in ["drug1", "drug2"]) == {"Warfarin", "Aspirin"}
    mock_rxnav.get_interactions.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario 2: Cache hit — RxNav NOT called on second lookup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_suppresses_rxnav_call(
    mock_cache: AsyncMock,
    mock_rxnav: AsyncMock,
    mock_openfda: AsyncMock,
) -> None:
    """AC Scenario 2 — Cache hit: RxNav API must not be called."""
    mock_cache.get.return_value = {"interactions": [_RXNAV_HIGH_INTERACTION]}

    checker = DrugInteractionChecker(
        cache=mock_cache, rxnav_client=mock_rxnav, openfda_client=mock_openfda
    )

    result = await checker.check([WARFARIN, ASPIRIN])

    assert result.interaction_check_status == "COMPLETE"
    assert len(result.interactions) == 1
    mock_rxnav.get_interactions.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 3: OpenFDA fallback — RxNav HTTP 503 → OpenFDA → source=OPENFDA
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openfda_fallback_on_rxnav_503(
    mock_cache: AsyncMock,
    mock_rxnav: AsyncMock,
    mock_openfda: AsyncMock,
) -> None:
    """AC Scenario 3 — RxNav 503 triggers OpenFDA fallback; source=OPENFDA."""
    mock_rxnav.get_interactions.side_effect = RxNavUnavailableError(status_code=503)

    checker = DrugInteractionChecker(
        cache=mock_cache, rxnav_client=mock_rxnav, openfda_client=mock_openfda
    )

    result = await checker.check([WARFARIN, ASPIRIN])

    assert result.interaction_check_status == "COMPLETE"
    mock_openfda.get_interactions.assert_called()
    sources = {i["source"] for i in result.interactions}
    assert sources == {"OPENFDA"}


# ---------------------------------------------------------------------------
# Scenario 4: Offline degradation — both APIs fail → INCOMPLETE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_offline_degradation_when_both_apis_unavailable(
    mock_cache: AsyncMock,
    mock_rxnav: AsyncMock,
    mock_openfda: AsyncMock,
) -> None:
    """AC Scenario 4 — Both RxNav and OpenFDA fail → INCOMPLETE status."""
    mock_rxnav.get_interactions.side_effect = RxNavUnavailableError(status_code=503)
    mock_openfda.get_interactions.side_effect = OpenFDAUnavailableError(status_code=500)

    checker = DrugInteractionChecker(
        cache=mock_cache, rxnav_client=mock_rxnav, openfda_client=mock_openfda
    )

    result = await checker.check([WARFARIN, ASPIRIN])

    assert result.interaction_check_status == "INCOMPLETE"
    assert result.degradation_notice is not None
    assert "manual review" in result.degradation_notice.lower()
