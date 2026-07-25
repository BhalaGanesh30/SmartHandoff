"""SmartHandoff shared agent base library.

Exports:
  BaseAgentSubscriber      — ABC for all Pub/Sub-consuming agent containers
  StructuredOutputHelper   — LangChain + Vertex AI structured output wrapper
  LLMRetryWrapper          — exponential-backoff retry for Vertex AI errors
  update_task_status       — DB write + SignalR broadcast for agent task transitions
  RetryableError           — transient errors for retry logic
  NonRetryableError        — permanent errors that should not be retried

Design refs:
    ADR-004, TR-004, TR-015, TR-017, US-024 DoD
"""
from agent_base.llm_retry import LLMRetryWrapper
from agent_base.status_updater import update_task_status
from agent_base.structured_output import (
    DEFAULT_MODEL_NAME,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    NonRetryableError,
    RetryableError,
    StructuredOutputHelper,
)
from agent_base.subscriber import BaseAgentSubscriber

__all__ = [
    "BaseAgentSubscriber",
    "LLMRetryWrapper",
    "StructuredOutputHelper",
    "RetryableError",
    "NonRetryableError",
    "DEFAULT_MODEL_NAME",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT_SECONDS",
    "update_task_status",
]
