"""Error hierarchy and retry decorator for SmartHandoff base agent.

All specialist agents inherit these via ``BaseAgent``. The retry decorator
applies exponential backoff only for ``RetryableError`` subclasses; all
other exceptions propagate immediately.

Backoff schedule (US-024 DoD):
    Attempt 1 → wait 1 s → Attempt 2 → wait 2 s → Attempt 3 → raise

Design refs:
    TR-015  — DLQ: Pub/Sub max_delivery_attempts=5; non-retryable propagates so
              Pub/Sub counts the delivery and eventually routes to DLQ
    US-024  — retry decorator 3 attempts; exponential backoff 1s/2s/4s
"""
from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class AgentError(Exception):
    """Base class for all SmartHandoff agent errors.

    Args:
        message: Human-readable error description.
        error_detail: Optional structured dict serialised to
            ``AgentTask.error_details`` in the DB.
    """

    def __init__(self, message: str, error_detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_detail: dict[str, Any] = error_detail or {}


class RetryableError(AgentError):
    """Transient error that should be retried with exponential backoff.

    Raise for conditions that are expected to self-resolve:
    - Database connection timeouts
    - Pub/Sub transient delivery failures
    - Vertex AI rate-limit (429) responses
    - Network I/O errors

    Example::

        raise RetryableError(
            "DB connection timeout",
            error_detail={"db_host": "cloud-sql-proxy", "attempt": 1},
        )
    """


class NonRetryableError(AgentError):
    """Permanent error that must NOT be retried.

    Raise for conditions that cannot be resolved by retrying:
    - Schema validation failures (malformed Pub/Sub payload)
    - Business rule violations (encounter not found in FHIR)
    - Pydantic structured-output schema mismatch

    Example::

        raise NonRetryableError(
            "ADTEvent schema validation failed",
            error_detail={"field": "encounter_id", "value": None},
        )
    """


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

_BACKOFF_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)
"""Exponential backoff delays in seconds for each retry attempt (US-024 DoD)."""

MAX_ATTEMPTS: int = len(_BACKOFF_DELAYS) + 1
"""Total attempts = initial attempt + len(BACKOFF_DELAYS) = 4 total tries."""


def retry_with_backoff(func: _F) -> _F:
    """Async decorator that retries ``RetryableError`` with exponential backoff.

    Wraps an ``async`` coroutine function. On ``RetryableError``, waits the
    scheduled backoff delay then retries up to ``MAX_ATTEMPTS`` total. On
    ``NonRetryableError`` or any other exception, propagates immediately.

    Args:
        func: An ``async`` coroutine function to wrap.

    Returns:
        Wrapped coroutine with retry logic.

    Raises:
        RetryableError: When all ``MAX_ATTEMPTS`` are exhausted.
        NonRetryableError: Immediately, without retry.
        Exception: Any other exception, immediately, without retry.

    Example::

        class MyAgent(BaseAgent):
            @retry_with_backoff
            async def process(self, event: ADTEvent) -> BaseAgentOutput:
                ...
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exc: RetryableError | None = None

        for attempt, delay in enumerate(
            [0.0] + list(_BACKOFF_DELAYS), start=1
        ):
            if delay > 0:
                logger.warning(
                    "agent_retry_backoff",
                    extra={
                        "attempt": attempt,
                        "delay_seconds": delay,
                        "function": func.__qualname__,
                    },
                )
                await asyncio.sleep(delay)

            try:
                return await func(*args, **kwargs)

            except NonRetryableError:
                # Propagate immediately — no retry
                raise

            except RetryableError as exc:
                last_exc = exc
                logger.warning(
                    "agent_retryable_error",
                    extra={
                        "attempt": attempt,
                        "max_attempts": MAX_ATTEMPTS,
                        "error": str(exc),
                        "error_detail": exc.error_detail,
                        "function": func.__qualname__,
                    },
                )
                if attempt >= MAX_ATTEMPTS:
                    break  # exhausted — raise below

            except Exception:
                # Unknown error — treat as non-retryable; propagate immediately
                raise

        # All attempts exhausted
        raise last_exc  # type: ignore[misc]

    return wrapper  # type: ignore[return-value]
