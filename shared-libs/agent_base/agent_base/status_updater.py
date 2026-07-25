"""Agent task status updater — shared utility for all agent Cloud Run containers.

Provides a module-level singleton ``TaskStatusTransitionService`` initialised once
per container instance. Agents call ``update_task_status()`` to transition
``AgentTask`` status + broadcast SignalR events.

US-022 DoD: agent calls SignalR broadcast after each status transition.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.agent_task import AgentTask, AgentTaskStatus

logger = logging.getLogger(__name__)

# Module-level singleton — lazy-initialised on first import.
_transition_service: "TaskStatusTransitionService | None" = None


def get_transition_service() -> "TaskStatusTransitionService":
    """Module-level singleton for agent Cloud Run containers.

    Agents are not FastAPI handlers — they cannot use FastAPI DI.
    This function initialises the broadcaster once at import time.
    
    Lazy-initialised to allow environment variables to be set before first call.
    """
    global _transition_service
    if _transition_service is None:
        import os
        from app.services.task_status_service import TaskStatusTransitionService
        from app.signalr.broadcaster import SignalRBroadcaster

        connection_string = os.environ.get("AZURE_SIGNALR_CONNECTION_STRING", "")
        if not connection_string:
            logger.warning(
                "AZURE_SIGNALR_CONNECTION_STRING not set — SignalR broadcasts will fail. "
                "Set this environment variable in Cloud Run service configuration."
            )
        broadcaster = SignalRBroadcaster(connection_string)
        _transition_service = TaskStatusTransitionService(broadcaster)
        logger.info("TaskStatusTransitionService singleton initialised")
    
    return _transition_service


async def update_task_status(
    db: AsyncSession,
    task: "AgentTask",
    new_status: "AgentTaskStatus",
) -> "AgentTask":
    """Update task status and broadcast SignalR event.
    
    Public function used by all agents — replaces previous direct DB update.
    
    Args:
        db: Write-capable async session (must NOT be a read replica session).
        task: ORM instance fetched in the same session (avoids re-fetch).
        new_status: Target status enum value.
    
    Returns:
        Updated AgentTask instance (post-commit state).
    
    Raises:
        ValueError: If the transition is not valid per US-021 state machine.
    """
    service = get_transition_service()
    return await service.transition(db, task, new_status)
