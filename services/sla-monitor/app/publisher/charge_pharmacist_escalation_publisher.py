"""ChargePharmacistEscalationPublisher — publishes CHARGE_PHARMACIST_ESCALATION.

Sends a HIGH-priority notification to the ``notification-requests`` Pub/Sub topic
when a MEDICATION_RECONCILIATION AgentTask has exceeded the 24-hour admission SLA.

Design refs:
    US-034 Scenario 1  — required payload fields
    US-034 DoD         — priority=HIGH on notification-requests topic
    US-021/TASK-004    — EscalationPublisher pattern (same topic, same retry logic)
"""
from __future__ import annotations

import logging
from uuid import UUID

from google.cloud import pubsub_v1

from app.publisher.schemas import ChargePharmacistEscalationPayload

logger = logging.getLogger(__name__)


class ChargePharmacistEscalationPublisher:
    """Publishes CHARGE_PHARMACIST_ESCALATION messages to notification-requests.

    Args:
        project_id: GCP project ID.
        topic_id: Pub/Sub topic name (default: ``notification-requests``).
    """

    def __init__(
        self,
        project_id: str,
        topic_id: str = "notification-requests",
    ) -> None:
        self._topic_path = pubsub_v1.PublisherClient.topic_path(project_id, topic_id)
        self._publisher = pubsub_v1.PublisherClient()

    async def publish(
        self,
        *,
        encounter_id: UUID,
        task_id: UUID,
        patient_unit: str,
        hours_elapsed: int,
    ) -> None:
        """Publish a CHARGE_PHARMACIST_ESCALATION message.

        Args:
            encounter_id: UUID of the encounter breaching the SLA.
            task_id: UUID of the MEDICATION_RECONCILIATION AgentTask.
            patient_unit: Ward / unit identifier (e.g. ``"3N"``).
            hours_elapsed: Hours since admission at the time of escalation.

        Raises:
            google.api_core.exceptions.GoogleAPICallError: On non-retryable
                Pub/Sub publish failure after internal retries.
        """
        payload = ChargePharmacistEscalationPayload(
            encounter_id=encounter_id,
            task_id=task_id,
            patient_unit=patient_unit,
            hours_elapsed=hours_elapsed,
        )
        data = payload.model_dump_json().encode("utf-8")

        try:
            future = self._publisher.publish(
                self._topic_path,
                data,
                notification_type="CHARGE_PHARMACIST_ESCALATION",
                priority="HIGH",
            )
            message_id = future.result(timeout=10)
            
            logger.info(
                "ChargePharmacistEscalationPublisher: published",
                extra={
                    "message_id": message_id,
                    "encounter_id": str(encounter_id),
                    "task_id": str(task_id),
                    "patient_unit": patient_unit,
                    "hours_elapsed": hours_elapsed,
                },
            )
        except Exception as e:
            logger.error(
                "ChargePharmacistEscalationPublisher: publish failed",
                extra={
                    "encounter_id": str(encounter_id),
                    "task_id": str(task_id),
                    "error": str(e),
                },
            )
            raise
