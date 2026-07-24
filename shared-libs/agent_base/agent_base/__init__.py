"""SmartHandoff shared agent base library.

Exports:
  BaseAgentSubscriber   — ABC for all Pub/Sub-consuming agent containers
  StructuredOutputMixin — Pydantic-validated LangChain chain invocation
  LLMRetryWrapper       — exponential-backoff retry for Vertex AI errors
  update_task_status    — DB write + SignalR broadcast for agent task transitions

Design refs:
    ADR-004, TR-004, TR-015, TR-017, US-020 DoD
"""
from agent_base.llm_retry import LLMRetryWrapper
from agent_base.status_updater import update_task_status
from agent_base.structured_output import StructuredOutputError, StructuredOutputMixin
from agent_base.subscriber import BaseAgentSubscriber

__all__ = [
    "BaseAgentSubscriber",
    "LLMRetryWrapper",
    "StructuredOutputError",
    "StructuredOutputMixin",
    "update_task_status",
]
