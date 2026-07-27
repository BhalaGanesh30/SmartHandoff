"""Care team alert service for patient resolution issues.

This service dispatches care team alerts for patient resolution issues via GCP Pub/Sub.
Alerts are sent to the 'notification-requests' topic for downstream processing
(SMS, email, dashboard notifications).

Design refs:
    US-019 AC2-AC3 — Care team alerts for ambiguous/unresolved patients
    EP-013         — Pub/Sub notification infrastructure
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from google.cloud import pubsub_v1

from app.core.config import get_settings
from app.models.encounter import Encounter
from app.models.patient import PatientResolutionStatus

logger = logging.getLogger(__name__)


class CareTeamAlertService:
    """Dispatch care team alerts for patient resolution issues via GCP Pub/Sub.

    Alerts are sent to the 'notification-requests' topic for downstream
    processing (SMS, email, dashboard notifications).

    Usage:
        service = CareTeamAlertService()
        await service.send_patient_resolution_alert(
            encounter=encounter,
            status=PatientResolutionStatus.AMBIGUOUS,
            metadata={
                "mrn": "MRN-789",
                "name": {"family": "Smith", "given": "John"},
                "dob": "1980-01-15",
                "match_count": 3
            }
        )
    """

    def __init__(self, publisher: Optional[pubsub_v1.PublisherClient] = None):
        """Initialize service with Pub/Sub publisher.

        Args:
            publisher: GCP Pub/Sub publisher client (injected for testing)
        """
        self.publisher = publisher or pubsub_v1.PublisherClient()
        self._settings = get_settings()
        self.topic_path = (
            f"projects/{self._settings.GCP_PROJECT_ID}/topics/notification-requests"
        )

    async def send_patient_resolution_alert(
        self,
        encounter: Encounter,
        status: PatientResolutionStatus,
        metadata: dict[str, Any],
    ) -> None:
        """Send patient resolution alert to care team via Pub/Sub.

        Args:
            encounter: Encounter with unresolved patient
            status: Resolution status (AMBIGUOUS or UNRESOLVED)
            metadata: Additional context (mrn, name, dob, match_count)

        Raises:
            Exception: Logged but not propagated (non-blocking)

        Example:
            >>> service = CareTeamAlertService()
            >>> await service.send_patient_resolution_alert(
            ...     encounter=encounter,
            ...     status=PatientResolutionStatus.AMBIGUOUS,
            ...     metadata={
            ...         "mrn": "MRN-789",
            ...         "name": {"family": "Smith", "given": "John"},
            ...         "dob": "1980-01-15",
            ...         "match_count": 3
            ...     }
            ... )
        """
        try:
            # Build alert payload
            payload = {
                "type": "PATIENT_RESOLUTION_ALERT",
                "priority": "HIGH",
                "status": status.value,
                "encounter_id": str(encounter.id),
                "mrn": metadata.get("mrn"),
                "name": metadata.get("name"),
                "dob": metadata.get("dob"),
                "match_count": metadata.get("match_count"),
                "message": self._build_alert_message(status, metadata),
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Publish to Pub/Sub (fire-and-forget)
            future = self.publisher.publish(
                self.topic_path,
                data=json.dumps(payload).encode("utf-8"),
                type="PATIENT_RESOLUTION_ALERT",
                priority="HIGH",
                encounter_id=str(encounter.id),
            )

            # Wait for publish to complete (async)
            message_id = future.result(timeout=5.0)

            logger.info(
                f"Care team alert dispatched for encounter {encounter.id}",
                extra={
                    "message_id": message_id,
                    "status": status.value,
                    "encounter_id": str(encounter.id),
                },
            )

        except Exception as e:
            # Log error but don't block encounter creation
            logger.error(
                f"Failed to dispatch care team alert for encounter {encounter.id}: {e}",
                extra={"encounter_id": str(encounter.id), "error": str(e)},
                exc_info=True,
            )

    def _build_alert_message(
        self, status: PatientResolutionStatus, metadata: dict[str, Any]
    ) -> str:
        """Build human-readable alert message.

        Args:
            status: Resolution status (AMBIGUOUS or UNRESOLVED)
            metadata: Additional context

        Returns:
            Human-readable alert message
        """
        if status == PatientResolutionStatus.AMBIGUOUS:
            count = metadata.get("match_count", "multiple")
            mrn = metadata.get("mrn", "unknown")
            return f"Manual resolution required: {count} matching patients found for MRN {mrn}"
        elif status == PatientResolutionStatus.UNRESOLVED:
            mrn = metadata.get("mrn", "unknown")
            return f"Patient not found in EHR for MRN {mrn} - manual lookup required"
        else:
            return f"Patient resolution issue: {status.value}"
