"""Post-reconciliation drug interaction pipeline for the Medication Reconciliation Agent.

Invoked after US-030 normalisation is complete. Runs DrugInteractionChecker,
maps results to alert payloads, and posts to the encounters alerts endpoint.

Design refs:
    US-031 AC Scenarios 1, 3, 4
    design.md §3.2   — Agent container pattern
    ADR-004          — LangChain structured output; Pydantic schema enforcement
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import httpx

from app.agents.medication_reconciliation.drug_interaction.checker import (
    DischargedMedication,
    DrugInteractionChecker,
    DrugInteractionResult,
)
from app.agents.medication_reconciliation.high_risk.detector import (
    HighRiskDrugClassDetector,
    HighRiskDrugMatch,
)
from app.schemas.pharmacist_alert import HighRiskDrugClassAlertCreate

logger = logging.getLogger(__name__)

_ALERTS_ENDPOINT_TEMPLATE = "/api/v1/encounters/{encounter_id}/pharmacist-alerts"


class InteractionPipeline:
    """Orchestrates post-reconciliation drug interaction checking and alerting.

    Args:
        checker: Configured ``DrugInteractionChecker`` instance.
        api_client: Async HTTP client pre-configured with the API base URL and
            a service-account JWT (internal service-to-service call).
    """

    def __init__(
        self,
        checker: DrugInteractionChecker,
        api_client: httpx.AsyncClient,
    ) -> None:
        self._checker = checker
        self._api = api_client

    async def run(
        self,
        encounter_id: uuid.UUID,
        medications: list[DischargedMedication],
    ) -> dict[str, Any]:
        """Run interaction check and high-risk detection concurrently.

        Args:
            encounter_id: UUID of the discharge encounter.
            medications: Active discharge medication list (with RxCUIs).

        Returns:
            Summary dict:
                ``interaction_check_status``, ``interaction_alerts_created``,
                ``high_severity_count``, ``high_risk_alerts_created``.
        """
        logger.info(
            "Starting interaction pipeline encounter_id=%s med_count=%d",
            encounter_id,
            len(medications),
        )

        # Run interaction check and high-risk detection in parallel
        interaction_task = asyncio.create_task(
            self._run_interaction_check(encounter_id, medications)
        )
        high_risk_task = asyncio.create_task(
            self._run_high_risk_detection(encounter_id, medications)
        )

        results = await asyncio.gather(
            interaction_task,
            high_risk_task,
            return_exceptions=True,
        )

        interaction_result = results[0]
        high_risk_matches = results[1]

        # High-risk detection failure must not block the interaction result
        if isinstance(high_risk_matches, Exception):
            logger.error(
                "High-risk detection failed for encounter=%s: %s",
                encounter_id,
                high_risk_matches,
            )
            high_risk_matches = []

        # Interaction check failure should also be handled gracefully
        if isinstance(interaction_result, Exception):
            logger.error(
                "Interaction check failed for encounter=%s: %s",
                encounter_id,
                interaction_result,
            )
            interaction_result = {
                "interaction_check_status": "INCOMPLETE",
                "alerts_created": 0,
                "high_severity_count": 0,
            }

        logger.info(
            "Interaction pipeline complete encounter_id=%s interaction_alerts=%d high_risk_alerts=%d",
            encounter_id,
            interaction_result["alerts_created"],
            len(high_risk_matches),
        )

        return {
            "interaction_check_status": interaction_result["interaction_check_status"],
            "interaction_alerts_created": interaction_result["alerts_created"],
            "high_severity_count": interaction_result["high_severity_count"],
            "high_risk_alerts_created": len(high_risk_matches),
            "high_risk_matches": high_risk_matches,
        }

    async def _run_interaction_check(
        self,
        encounter_id: uuid.UUID,
        medications: list[DischargedMedication],
    ) -> dict[str, Any]:
        """Execute drug interaction check and post alerts.

        Args:
            encounter_id: UUID of the discharge encounter.
            medications: Active discharge medication list (with RxCUIs).

        Returns:
            Dict with interaction_check_status, alerts_created, high_severity_count.
        """
        result: DrugInteractionResult = await self._checker.check(medications)

        alerts_created = 0
        high_count = 0

        if result.interaction_check_status == "INCOMPLETE":
            await self._post_alert(
                encounter_id=encounter_id,
                severity="MEDIUM",
                drug_pair=None,
                description=result.degradation_notice,
                source="SYSTEM",
                check_status="INCOMPLETE",
            )
            alerts_created += 1
        else:
            for interaction in result.interactions:
                severity = interaction.get("severity", "LOW")
                if severity not in {"HIGH", "MEDIUM", "LOW"}:
                    severity = "LOW"

                await self._post_alert(
                    encounter_id=encounter_id,
                    severity=severity,
                    drug_pair=[interaction.get("drug1"), interaction.get("drug2")],
                    description=interaction.get("description"),
                    source=interaction.get("source", "RXNAV"),
                    check_status="COMPLETE",
                    metadata={
                        "rxcui1": interaction.get("rxcui1"),
                        "rxcui2": interaction.get("rxcui2"),
                    },
                )
                alerts_created += 1
                if severity == "HIGH":
                    high_count += 1

        return {
            "interaction_check_status": result.interaction_check_status,
            "alerts_created": alerts_created,
            "high_severity_count": high_count,
        }

    async def _run_high_risk_detection(
        self,
        encounter_id: uuid.UUID,
        medications: list[DischargedMedication],
    ) -> list[HighRiskDrugMatch]:
        """Detect ISMP high-alert medications and post alerts for each match.

        Runs unconditionally and in parallel with the interaction check.
        Alert creation is ADDITIVE: a drug flagged by interaction check AND
        high-risk detection will produce two separate alert records.

        Args:
            encounter_id: UUID of the discharge encounter.
            medications: Discharge medication list from US-030 normalisation.

        Returns:
            List of :class:`HighRiskDrugMatch` for audit/logging.

        Design refs:
            US-032 AC Scenario 1   — unconditional; ADDITIVE
            US-032 Technical Notes — case-insensitive name match
        """
        detector = HighRiskDrugClassDetector()
        matches = detector.detect(medications)

        for match in matches:
            payload = HighRiskDrugClassAlertCreate(
                alert_type="HIGH_RISK_DRUG_CLASS",
                drug_class=match.drug_class,
                drug_name=match.drug_name,
                severity="HIGH",
            )
            await self._post_high_risk_alert(
                encounter_id=encounter_id,
                payload=payload.model_dump(),
            )
            logger.info(
                "HIGH_RISK_DRUG_CLASS alert posted: encounter=%s drug=%r class=%s",
                encounter_id,
                match.drug_name,
                match.drug_class,
            )

        return matches

    async def _post_alert(
        self,
        encounter_id: uuid.UUID,
        severity: str,
        drug_pair: list[str | None] | None,
        description: str | None,
        source: str,
        check_status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """POST a single pharmacist alert to the encounters alerts endpoint.

        Args:
            encounter_id: Target encounter UUID.
            severity: ``HIGH``, ``MEDIUM``, or ``LOW``.
            drug_pair: Two-element list of drug names (or ``None``).
            description: Interaction description text.
            source: ``RXNAV``, ``OPENFDA``, or ``SYSTEM``.
            check_status: ``COMPLETE`` or ``INCOMPLETE``.
            metadata: Additional key-value metadata.

        Raises:
            httpx.HTTPStatusError: If the alerts endpoint returns a non-2xx response.
        """
        endpoint = _ALERTS_ENDPOINT_TEMPLATE.format(encounter_id=encounter_id)
        payload: dict[str, Any] = {
            "alert_type": "PHARMACIST_ALERT",
            "severity": severity,
            "drug_pair": [d for d in (drug_pair or []) if d is not None] or None,
            "interaction_description": description,
            "source": source,
            "interaction_check_status": check_status,
            "metadata": metadata,
        }
        response = await self._api.post(endpoint, json=payload)
        response.raise_for_status()
        logger.debug(
            "Alert posted encounter_id=%s severity=%s alert_id=%s",
            encounter_id,
            severity,
            response.json().get("id"),
        )

    async def _post_high_risk_alert(
        self,
        encounter_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> None:
        """POST a HIGH_RISK_DRUG_CLASS alert to the encounters alerts endpoint.

        Args:
            encounter_id: Target encounter UUID.
            payload: Alert payload dict from HighRiskDrugClassAlertCreate.

        Raises:
            httpx.HTTPStatusError: If the alerts endpoint returns a non-2xx response.
        """
        endpoint = _ALERTS_ENDPOINT_TEMPLATE.format(encounter_id=encounter_id)
        response = await self._api.post(endpoint, json=payload)
        response.raise_for_status()
        logger.debug(
            "HIGH_RISK_DRUG_CLASS alert posted encounter_id=%s drug=%s class=%s alert_id=%s",
            encounter_id,
            payload.get("drug_name"),
            payload.get("drug_class"),
            response.json().get("id"),
        )
