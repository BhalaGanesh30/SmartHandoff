"""
Base agent class for specialist agents.

This is a simplified stub for US-025. The full BaseAgent implementation
with Pub/Sub consumer, retry logic, and DLQ forwarding lives in the
base-agent/ service (US-024).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """
    Abstract base class for specialist agents.

    Args:
        subscription_id: GCP Pub/Sub subscription ID (e.g. 'docs-agent-sub').
    """

    def __init__(self, subscription_id: str) -> None:
        self._subscription_id = subscription_id

    @abstractmethod
    def can_handle(self, event_type: str) -> bool:
        """Return True if this agent can process the given ADT event type."""

    @abstractmethod
    async def process(self, event: dict[str, Any]) -> None:
        """Process a single ADT event."""
