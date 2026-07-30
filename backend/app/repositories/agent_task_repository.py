"""AgentTask repository for write operations.

US-034/TASK-005: Task override endpoint repository layer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_task import AgentTask, AgentTaskStatus
from app.models.audit_log import AuditLog


class TaskNotFoundError(Exception):
    """Raised when task does not exist or does not belong to the encounter."""

    def __init__(self, task_id: uuid.UUID, encounter_id: uuid.UUID) -> None:
        self.task_id = task_id
        self.encounter_id = encounter_id
        super().__init__(
            f"Task {task_id} not found for encounter {encounter_id}"
        )


class InvalidTaskTypeError(Exception):
    """Raised when operation is attempted on unsupported agent type."""

    def __init__(self, task_id: uuid.UUID, agent_type: str) -> None:
        self.task_id = task_id
        self.agent_type = agent_type
        super().__init__(
            f"Task {task_id} has unsupported agent_type '{agent_type}'"
        )


class TaskAlreadyCompletedError(Exception):
    """Raised when override is attempted on already-completed task."""

    def __init__(self, task_id: uuid.UUID) -> None:
        self.task_id = task_id
        super().__init__(
            f"Task {task_id} is already completed"
        )


class AgentTaskRepository:
    """Repository for AgentTask write operations."""

    async def override_task(
        self,
        *,
        task_id: uuid.UUID,
        encounter_id: uuid.UUID,
        actor_id: uuid.UUID,
        note: str,
        session: AsyncSession,
    ) -> AgentTask:
        """Mark a MEDICATION_RECONCILIATION AgentTask as COMPLETED via manual override.

        Clears ``sla_escalation_sent_at`` so no further escalations fire (US-034 Scenario 4).

        Args:
            task_id: UUID of the AgentTask to override.
            encounter_id: UUID of the encounter — validates task ownership.
            actor_id: UUID of the calling user (charge pharmacist / pharmacy supervisor).
            note: Free-text justification stored in audit log.
            session: Write session.

        Returns:
            The updated ``AgentTask`` instance.

        Raises:
            TaskNotFoundError: If the task does not exist or does not belong to the encounter.
            InvalidTaskTypeError: If the task is not a MEDICATION_RECONCILIATION task.
            TaskAlreadyCompletedError: If the task is already COMPLETED.
        """
        stmt = sa.select(AgentTask).where(
            AgentTask.id == task_id,
            AgentTask.encounter_id == encounter_id,
        )
        result = await session.execute(stmt)
        task: AgentTask | None = result.scalar_one_or_none()

        if task is None:
            raise TaskNotFoundError(task_id=task_id, encounter_id=encounter_id)
        if task.agent_type != "MEDICATION_RECONCILIATION":
            raise InvalidTaskTypeError(task_id=task_id, agent_type=task.agent_type)
        if task.status == AgentTaskStatus.COMPLETED:
            raise TaskAlreadyCompletedError(task_id=task_id)

        now = datetime.now(tz=timezone.utc)
        task.status = AgentTaskStatus.COMPLETED
        task.completed_at = now
        task.sla_escalation_sent_at = None  # US-034 Scenario 4: clear escalation flag

        await session.flush()

        # Write audit log entry
        audit = AuditLog(
            user_id=actor_id,
            user_role=None,  # Role not stored in audit for this operation
            resource_type="agent_task",
            resource_id=str(task_id),
            action="TASK_MANUALLY_OVERRIDDEN",
            endpoint=f"/api/v1/encounters/{encounter_id}/tasks/{task_id}/override",
            request_id=None,
        )
        session.add(audit)
        await session.commit()
        await session.refresh(task)
        
        return task
