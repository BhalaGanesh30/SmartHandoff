"""
Base agent class for specialist agents.

This is a simplified stub for US-035. The full BaseAgent implementation
with Pub/Sub consumer, retry logic, and DLQ forwarding lives in the
base-agent/ service (US-024).

Design refs:
    US-024 — BaseAgent framework
    US-035 — BedManagementAgent uses BaseAgent pattern
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RetryableError(Exception):
    """Exception raised when an operation should be retried by Pub/Sub."""
    pass


class BaseAgent(ABC):
    """
    Abstract base class for specialist agents.

    Args:
        subscription_id: GCP Pub/Sub subscription ID (e.g. 'bed-mgmt-agent-sub').
    """

    def __init__(self, subscription_id: str | None = None) -> None:
        self._subscription_id = subscription_id

    @abstractmethod
    def can_handle(self, event_type: str) -> bool:
        """Return True if this agent can process the given ADT event type."""

    @abstractmethod
    async def process(self, event: dict[str, Any]) -> Any:
        """Process a single ADT event.
        
        Returns:
            Structured output (Pydantic model) or None if event not handled.
        
        Raises:
            RetryableError: If operation failed but should be retried.
        """
