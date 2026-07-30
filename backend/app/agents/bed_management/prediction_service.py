"""DischargePredictionService — calls the ML Inference Service and persists the result.

Called by BedManagementAgent after every successful bed status transition to
update encounter.predicted_discharge_time (US-036 AC Scenario 3).

Design refs:
    US-036 AC Scenario 3 — update within 60 s of status change
    AIR-011              — httpx async client; 3-attempt exponential backoff
    TR-007               — <500 ms inference latency (enforced by inference service)
    ADR-007              — no PHI in logs (encounter_id UUID only)
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.encounter import Encounter

logger = logging.getLogger(__name__)

ML_INFERENCE_BASE_URL = os.environ.get("ML_INFERENCE_SERVICE_URL", "http://ml-inference")
ML_INFERENCE_ENDPOINT = "/ml-inference/predict/discharge-time"
_BACKOFF_DELAYS = (1.0, 2.0, 4.0)  # AIR-011: 3-attempt exponential backoff


class DischargePredictionService:
    """Fetches a discharge time prediction and persists it to the encounter record.

    Args:
        http_client: ``httpx.AsyncClient`` configured with service account ID token auth.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def update_prediction(
        self,
        session: AsyncSession,
        encounter_id: str,
        refresh_service: Any,
    ) -> bool:
        """Fetch prediction for ``encounter_id`` and update the encounter row.

        Args:
            session: Active write ``AsyncSession`` (called outside the main transaction).
            encounter_id: UUID of the encounter to update.
            refresh_service: ``BedBoardRefreshService`` to trigger after the DB write.

        Returns:
            ``True`` if prediction was successfully written; ``False`` on non-retryable failure.
        """
        encounter = await self._fetch_encounter(session, encounter_id)
        if encounter is None:
            logger.warning("Encounter not found for prediction: %s", encounter_id)
            return False

        payload = self._build_request_payload(encounter, encounter_id)
        prediction = await self._call_inference_service(payload, encounter_id)
        if prediction is None:
            return False

        await session.execute(
            update(Encounter)
            .where(Encounter.id == UUID(encounter_id))
            .values(
                predicted_discharge_time=prediction["predicted_discharge_time"],
                discharge_prediction_confidence=prediction["confidence_level"],
                discharge_prediction_interval_hours=prediction["confidence_interval_hours"],
            )
        )
        await session.commit()

        # Refresh mv_bed_board so the new prediction appears within 60 s (AC Scenario 3)
        await refresh_service.refresh_async()

        logger.info(
            "Prediction stored: encounter_id=%s predicted=%s confidence=%s",
            encounter_id,
            prediction["predicted_discharge_time"].isoformat(),
            prediction["confidence_level"],
        )
        return True

    def _build_request_payload(self, encounter: Encounter, encounter_id: str) -> dict:
        """Construct the JSON payload for the ML Inference Service request.

        Uses ``encounter`` ORM object fields. ``patient_dob`` is retrieved from
        the related ``patient`` record (must be eagerly loaded or fetched separately).

        Note: PHI fields (patient_dob) are passed only to the inference service
        over the internal VPC; they are NOT logged anywhere (ADR-007 / BR-020).
        """
        return {
            "encounter_id": encounter_id,
            "admit_time": encounter.admit_time.isoformat() if encounter.admit_time else None,
            "patient_dob": encounter.patient.dob.isoformat() if encounter.patient and encounter.patient.dob else None,
            "admit_diagnosis_group": encounter.admitting_diagnosis or "UNKNOWN",
            "unit": encounter.unit or "UNKNOWN",
            "pending_procedures_count": getattr(encounter, "pending_procedures_count", 0) or 0,
        }

    async def _fetch_encounter(self, session: AsyncSession, encounter_id: str) -> Encounter | None:
        """Load encounter with joined patient (for DOB) from the write DB."""
        result = await session.execute(
            select(Encounter)
            .options(selectinload(Encounter.patient))
            .where(Encounter.id == UUID(encounter_id))
            .where(Encounter.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def _call_inference_service(
        self,
        payload: dict,
        encounter_id: str,
    ) -> dict | None:
        """POST to the ML Inference Service with exponential backoff.

        Returns parsed response dict or ``None`` on exhausted retries.
        PHI fields in ``payload`` are not logged.
        """
        url = f"{ML_INFERENCE_BASE_URL}{ML_INFERENCE_ENDPOINT}"

        for attempt, delay in enumerate(_BACKOFF_DELAYS, start=1):
            try:
                resp = await self._http.post(url, json=payload, timeout=5.0)
                resp.raise_for_status()
                data = resp.json()
                return {
                    "predicted_discharge_time": datetime.fromisoformat(
                        data["predicted_discharge_time"]
                    ).replace(tzinfo=timezone.utc),
                    "confidence_level": data["confidence_level"],
                    "confidence_interval_hours": data["confidence_interval_hours"],
                }
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning(
                    "ML Inference call failed (attempt %d/%d) encounter_id=%s: %s",
                    attempt,
                    len(_BACKOFF_DELAYS),
                    encounter_id,
                    type(exc).__name__,
                )
                if attempt < len(_BACKOFF_DELAYS):
                    await asyncio.sleep(delay)

        logger.error(
            "ML Inference Service unreachable after %d attempts for encounter_id=%s. "
            "Prediction will not be updated this cycle.",
            len(_BACKOFF_DELAYS),
            encounter_id,
        )
        return None
