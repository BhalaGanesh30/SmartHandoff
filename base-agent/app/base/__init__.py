"""SmartHandoff base agent framework.

Provides shared functionality for all specialist agents:
- Error hierarchy with RetryableError and NonRetryableError
- Exponential backoff retry decorator
- Base agent ABC with Pub/Sub lifecycle management
- Cancellation flag checking
- Structured output with Pydantic validation

All specialist agents (Coordinator, Docs, MedRecon, Bed Management,
Follow-up Care, Patient Communication) inherit from BaseAgent.
"""
from __future__ import annotations

__all__ = [
    "AgentError",
    "RetryableError",
    "NonRetryableError",
    "retry_with_backoff",
    "MAX_ATTEMPTS",
    "StructuredOutputHelper",
    "DEFAULT_MODEL_NAME",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT_SECONDS",
]

from .errors import (
    AgentError,
    RetryableError,
    NonRetryableError,
    retry_with_backoff,
    MAX_ATTEMPTS,
)
from .structured_output import (
    StructuredOutputHelper,
    DEFAULT_MODEL_NAME,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
)
