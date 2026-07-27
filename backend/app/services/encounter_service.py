"""Encounter service with patient resolution integration.

This service handles encounter creation with patient identity resolution,
care team alerting, and agent task blocking for unresolved patients.

Design refs:
    US-019 AC1-AC5 — Patient resolution with alert dispatch
    TASK-002       — PatientResolver integration
    TASK-003       — Care team alert dispatch
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.fhir.exceptions import PatientAmbiguousError
from app.models.agent_task import AgentTask, AgentTaskStatus
from app.models.encounter import Encounter
from app.models.patient import PatientResolutionStatus
from app.services.care_team_alerts import CareTeamAlertService
from app.services.patient_resolver import PatientResolver

logger = logging.getLogger(__name__)


class EncounterService:
    """Service for encounter creation with patient resolution.

    Usage:
        service = EncounterService()
        encounter = await service.create_encounter_from_adt(
            mrn="MRN-789",
            name={"family": "Smith", "given": "John"},
            dob="1980-01-15",
            # ... other ADT fields ...
        )
    """

    def __init__(
        self,
        patient_resolver: Optional[PatientResolver] = None,
        alert_service: Optional[CareTeamAlertService] = None,
    ):
        """Initialize service with dependencies.

        Args:
            patient_resolver: Patient resolution service (injected for testing)
            alert_service: Care team alert service (injected for testing)
        """
        self.patient_resolver = patient_resolver or PatientResolver()
        self.alert_service = alert_service or CareTeamAlertService()

    async def create_encounter_from_adt(
        self,
        mrn: str,
        name: dict[str, str],
        dob: str,
        # ... other ADT fields can be added here as needed ...
    ) -> Encounter:
        """Create encounter with patient identity resolution.

        Args:
            mrn: Medical Record Number from ADT
            name: Patient name dict from ADT (e.g., {"family": "Smith", "given": "John"})
            dob: Date of birth from ADT (YYYY-MM-DD format)

        Returns:
            Encounter instance with patient_resolution_status set

        Example:
            >>> service = EncounterService()
            >>> encounter = await service.create_encounter_from_adt(
            ...     mrn="MRN-789",
            ...     name={"family": "Smith", "given": "John"},
            ...     dob="1980-01-15"
            ... )
            >>> print(encounter.patient_resolution_status)
            'RESOLVED'
        """
        encounter = Encounter()  # Initialize encounter record

        try:
            # Attempt patient resolution
            patient = await self.patient_resolver.resolve_patient(
                mrn=mrn, name=name, dob=dob, encounter_id=str(encounter.id)
            )

            if patient:
                # Success: patient resolved
                encounter.patient_id = patient.id
                encounter.patient_resolution_status = PatientResolutionStatus.RESOLVED

                # Create agent tasks with PENDING status
                await self._create_agent_tasks(encounter, blocked=False)

            else:
                # Unresolvable: zero matches
                encounter.patient_resolution_status = PatientResolutionStatus.UNRESOLVED

                # Dispatch care team alert (non-blocking)
                await self.alert_service.send_patient_resolution_alert(
                    encounter=encounter,
                    status=PatientResolutionStatus.UNRESOLVED,
                    metadata={"mrn": mrn, "name": name, "dob": dob},
                )

                # Create blocked agent tasks
                await self._create_agent_tasks(
                    encounter,
                    blocked=True,
                    blocked_reason="Patient not found in EHR",
                )

        except PatientAmbiguousError as e:
            # Ambiguous: multiple matches
            encounter.patient_resolution_status = PatientResolutionStatus.AMBIGUOUS

            # Dispatch care team alert (non-blocking)
            await self.alert_service.send_patient_resolution_alert(
                encounter=encounter,
                status=PatientResolutionStatus.AMBIGUOUS,
                metadata={
                    "mrn": mrn,
                    "name": name,
                    "dob": dob,
                    "match_count": e.match_count,
                },
            )

            # Create blocked agent tasks
            await self._create_agent_tasks(
                encounter,
                blocked=True,
                blocked_reason="Patient identity ambiguous - manual resolution required",
            )

        # Save encounter (regardless of resolution status)
        # Note: Actual database save logic should be implemented here
        # encounter.save()  # Adjust to your ORM pattern

        return encounter

    async def _create_agent_tasks(
        self,
        encounter: Encounter,
        blocked: bool,
        blocked_reason: Optional[str] = None,
    ) -> None:
        """Create agent tasks for encounter, optionally blocked.

        Args:
            encounter: Encounter for which to create tasks
            blocked: Whether to create tasks in BLOCKED status
            blocked_reason: Reason for blocking (if blocked=True)

        Example:
            >>> await service._create_agent_tasks(
            ...     encounter=encounter,
            ...     blocked=True,
            ...     blocked_reason="Patient identity ambiguous"
            ... )
        """
        agent_types = [
            "documentation",
            "medication_reconciliation",
            "bed_management",
            "follow_up_care",
            "patient_communication",
        ]

        for agent_type in agent_types:
            task = AgentTask(
                encounter_id=encounter.id,
                agent_type=agent_type,
                status=(
                    AgentTaskStatus.BLOCKED.value
                    if blocked
                    else AgentTaskStatus.PENDING.value
                ),
                blocked_reason=blocked_reason if blocked else None,
            )
            # Note: Actual database save logic should be implemented here
            # task.save()  # Adjust to your ORM pattern
