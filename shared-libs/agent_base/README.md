# agent_base

SmartHandoff shared LangChain base agent library.

## Overview

Provides reusable components for all SmartHandoff AI agents:

- **BaseAgentSubscriber**: Abstract base class for Pub/Sub-consuming agents
- **StructuredOutputMixin**: Pydantic-validated LangChain chain invocation
- **LLMRetryWrapper**: Exponential-backoff retry for transient Vertex AI errors

## Installation

From the repository root:

```bash
pip install -e shared-libs/agent_base/
```

## Usage

```python
from agent_base import BaseAgentSubscriber, StructuredOutputMixin, LLMRetryWrapper

class MyAgent(BaseAgentSubscriber, StructuredOutputMixin):
    async def process_task(self, task: AgentTask) -> None:
        # Your agent logic here
        pass
```

## Design References

- ADR-004: Structured output enforced via Pydantic schemas
- TR-004: AI document generation <30 seconds with retry
- TR-015: Pub/Sub consumer pattern
- TR-017: SIGTERM integration
- US-020: LangChain base agent class extraction
