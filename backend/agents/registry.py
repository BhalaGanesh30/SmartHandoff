"""
Agent registry for all specialist agents.

This module maintains a registry of all specialist agent classes.
The agent runner uses this registry to instantiate and manage agents.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from agents.documentation.agent import DocumentationAgent

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

# List of all agent classes
# Each class should extend BaseAgent and implement can_handle() and process()
AGENT_REGISTRY: list[type[BaseAgent]] = [
    DocumentationAgent,
]
