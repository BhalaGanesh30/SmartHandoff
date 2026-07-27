"""Abstract base class for all SmartHandoff LangChain agent subscribers.

Each specialised agent (Documentation, MedRecon, BedManagement, etc.) subclasses
``BaseAgentSubscriber`` and implements ``process_task()``. The base class owns:

  - Pub/Sub pull subscription lifecycle (``FlowControl(max_messages=10)``)
  - ACK-after-success / NACK-on-exception pattern
  - ``shutdown_event`` for SIGTERM integration (TR-017)
  - Prometheus ``agent_task_processing_latency_seconds`` histogram

Usage::

    class DocumentationAgent(BaseAgentSubscriber):
        async def process_task(self, task: AgentTask) -> None:
            draft = await self._generate_document(task)
            await self._persist_draft(draft)

Design refs:
    ADR-001, ADR-004, TR-015, TR-017, US-020 DoD
"""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from prometheus_client import Histogram

if TYPE_CHECKING:
    from app.models.agent_task import AgentTask

logger = logging.getLogger(__name__)

AGENT_TASK_LATENCY = Histogram(
    "agent_task_processing_latency_seconds",
    "Time from AgentTask receipt to completion",
    ["agent_type"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0],
)


class BaseAgentSubscriber(ABC):
    """Abstract base for all SmartHandoff agent Pub/Sub consumers.

    Subclasses must implement ``process_task(task: AgentTask) -> None``.

    Args:
        agent_type: Identifies this agent in metrics/logs (e.g. "DOCUMENTATION").
        subscription_id: Pub/Sub subscription ID for this agent.
        project_id: GCP project ID.
    """

    def __init__(
        self,
        agent_type: str,
        subscription_id: str,
        project_id: str,
    ) -> None:
        self.agent_type = agent_type
        self._subscription_id = subscription_id
        self._project_id = project_id
        self.shutdown_event: asyncio.Event = asyncio.Event()

    @abstractmethod
    async def process_task(self, task: "AgentTask") -> None:
        """Process a single ``AgentTask``. Implemented by each specialised agent.

        Args:
            task: ``AgentTask`` ORM object in ``PENDING`` status.

        Raises:
            Any exception — causes the Pub/Sub message to be NACKed.
        """
        ...

    async def run(self) -> None:
        """Start the Pub/Sub consumer. Blocks until ``shutdown_event`` is set."""
        from agent_base._internal_subscriber import _run_pull_loop  # noqa: PLC0415

        await _run_pull_loop(self)
