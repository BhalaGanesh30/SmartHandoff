"""AgentTask domain model — minimal Pydantic stub for testing.

Full ORM model defined in backend/app/models/agent_task.py.
This stub exists only to avoid circular import issues in unit tests.
"""
from __future__ import annotations


class AgentTask:
    """Minimal AgentTask stub for testing BaseAgent status updates."""

    def __init__(self, task_id: str, status: str = "PENDING"):
        self.id = task_id
        self.status = status
        self.retry_count = 0
        self.error_details = None
