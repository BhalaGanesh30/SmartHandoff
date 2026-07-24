"""Exponential-backoff retry wrapper for Vertex AI LangChain calls.

Wraps any async callable with retry logic for transient Vertex AI errors:
  - ``google.api_core.exceptions.ResourceExhausted`` (429)
  - ``google.api_core.exceptions.ServiceUnavailable`` (503)
  - ``google.api_core.exceptions.DeadlineExceeded`` (504)

Design refs:
    TR-004   — AI document generation <30 seconds; retry with template fallback
    ADR-004  — LangChain abstracts LLM provider; retry wrapper is provider-agnostic
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted, ServiceUnavailable

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE_EXCEPTIONS = (ResourceExhausted, ServiceUnavailable, DeadlineExceeded)
_DEFAULT_DELAYS = (1.0, 2.0, 4.0, 8.0)  # 4 attempts; total max ~15 s


class LLMRetryWrapper:
    """Wraps an async LLM callable with configurable exponential-backoff retry.

    Args:
        delays: Tuple of sleep durations (seconds) between attempts.
            Length determines the number of retry attempts.

    Example::

        wrapper = LLMRetryWrapper()
        result = await wrapper.call(chain.ainvoke, inputs={"question": "..."})
    """

    def __init__(self, delays: tuple[float, ...] = _DEFAULT_DELAYS) -> None:
        self._delays = delays

    async def call(
        self,
        fn: Callable[..., Awaitable[T]],
        *args: object,
        **kwargs: object,
    ) -> T:
        """Call ``fn`` with retry on transient Vertex AI errors.

        Args:
            fn: Async callable to invoke (e.g. ``chain.ainvoke``).
            *args, **kwargs: Forwarded to ``fn``.

        Returns:
            Result of ``fn`` on success.

        Raises:
            The last exception if all retries are exhausted.
        """
        last_exc: Exception | None = None

        for attempt, delay in enumerate(self._delays, start=1):
            try:
                return await fn(*args, **kwargs)
            except _RETRYABLE_EXCEPTIONS as exc:
                last_exc = exc
                logger.warning(
                    "llm_retry",
                    extra={
                        "attempt": attempt,
                        "error": str(exc),
                        "next_delay_seconds": delay if attempt < len(self._delays) else None,
                    },
                )
                if attempt < len(self._delays):
                    await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]
