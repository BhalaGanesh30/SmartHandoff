"""Circuit breaker pattern for FHIR API resilience (module-level singleton).

Design refs:
    US-018 AC Scenario 2 — Circuit opens after 10 failures in 60s
    US-018 AC Scenario 3 — Half-open probe after 120s
    US-018 Technical Notes — Module-level singleton per Cloud Run instance

The circuit breaker state is shared across all FHIRClient instances within
a single Cloud Run container. This prevents cascading failures when the EHR
is degraded.

Circuit breaker state machine:
    CLOSED ──(10 failures in 60s)──> OPEN
       ↑                                │
       │                                │ (120s cooldown)
       │                                ↓
       └──(probe succeeds)────── HALF_OPEN
                                        │
                    (probe fails) ──────┘
"""
from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from functools import wraps
from typing import Callable

from app.core.fhir.metrics import set_circuit_state

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Failing — reject requests
    HALF_OPEN = "HALF_OPEN"  # Probing — allow 1 test request


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """Circuit breaker for async functions.

    Tracks failure rate and opens circuit if threshold exceeded.

    Attributes:
        failure_threshold: Number of consecutive failures before opening
        timeout: Seconds to wait in OPEN state before HALF_OPEN probe
        window: Time window (seconds) for counting failures
    """

    def __init__(
        self,
        failure_threshold: int = 10,
        timeout: int = 120,
        window: int = 60,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Max consecutive failures before opening (default: 10)
            timeout: Cooldown period in OPEN state (default: 120s)
            window: Time window for counting failures (default: 60s)
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.window = window
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.opened_at: float | None = None
        self._lock = asyncio.Lock()

    async def _reset_if_window_expired(self) -> None:
        """Reset failure count if time window expired."""
        if self.last_failure_time:
            elapsed = time.monotonic() - self.last_failure_time
            if elapsed > self.window:
                logger.info(
                    "Circuit breaker failure window expired — resetting count",
                    extra={
                        "event": "circuit_breaker_window_reset",
                        "elapsed_seconds": elapsed,
                        "window_seconds": self.window,
                        "previous_failure_count": self.failure_count,
                    },
                )
                self.failure_count = 0
                self.last_failure_time = None

    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Function positional arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result if circuit closed or half-open probe succeeds

        Raises:
            CircuitBreakerError: If circuit is open
            Original exception: If function call fails
        """
        async with self._lock:
            await self._reset_if_window_expired()

            # OPEN state — reject requests until timeout
            if self.state == CircuitBreakerState.OPEN:
                elapsed = time.monotonic() - self.opened_at
                if elapsed < self.timeout:
                    logger.warning(
                        "Circuit breaker OPEN — rejecting request",
                        extra={
                            "event": "circuit_breaker_reject",
                            "state": self.state.value,
                            "elapsed_seconds": round(elapsed, 2),
                            "cooldown_remaining": round(self.timeout - elapsed, 2),
                            "failure_count": self.failure_count,
                        },
                    )
                    raise CircuitBreakerError(
                        f"Circuit breaker OPEN. Retry in {self.timeout - elapsed:.0f}s"
                    )
                else:
                    # Timeout expired — transition to HALF_OPEN for probe
                    self.state = CircuitBreakerState.HALF_OPEN
                    set_circuit_state("HALF_OPEN")
                    logger.info(
                        "Circuit breaker transitioning to HALF_OPEN for probe",
                        extra={
                            "event": "circuit_breaker_half_open",
                            "cooldown_elapsed": round(elapsed, 2),
                        },
                    )

        # CLOSED or HALF_OPEN — attempt call
        try:
            result = await func(*args, **kwargs)

            # Success — reset failure count
            async with self._lock:
                if self.state == CircuitBreakerState.HALF_OPEN:
                    self.state = CircuitBreakerState.CLOSED
                    set_circuit_state("CLOSED")
                    logger.info(
                        "Circuit breaker probe succeeded — CLOSING",
                        extra={
                            "event": "circuit_breaker_close",
                            "previous_failure_count": self.failure_count,
                        },
                    )
                self.failure_count = 0
                self.last_failure_time = None

            return result

        except Exception as exc:
            # Failure — increment count and possibly open circuit
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.monotonic()

                if self.state == CircuitBreakerState.HALF_OPEN:
                    # Probe failed — reopen circuit
                    self.state = CircuitBreakerState.OPEN
                    self.opened_at = time.monotonic()
                    set_circuit_state("OPEN")
                    logger.critical(
                        "Circuit breaker probe FAILED — REOPENING",
                        extra={
                            "event": "circuit_breaker_reopen",
                            "failure_count": self.failure_count,
                            "error": str(exc),
                        },
                    )
                elif self.failure_count >= self.failure_threshold:
                    # Threshold exceeded — open circuit
                    self.state = CircuitBreakerState.OPEN
                    self.opened_at = time.monotonic()
                    set_circuit_state("OPEN")
                    logger.critical(
                        "Circuit breaker OPENED due to failure threshold",
                        extra={
                            "event": "circuit_breaker_open",
                            "failure_count": self.failure_count,
                            "threshold": self.failure_threshold,
                            "error": str(exc),
                        },
                    )
                else:
                    logger.warning(
                        "Circuit breaker failure recorded",
                        extra={
                            "event": "circuit_breaker_failure",
                            "failure_count": self.failure_count,
                            "threshold": self.failure_threshold,
                            "state": self.state.value,
                            "error": str(exc),
                        },
                    )

            raise


# ── Module-level singleton instance ──────────────────────────────────────────
# Shared across all FHIRClient instances within this Cloud Run container.
_circuit_breaker_instance: CircuitBreaker | None = None
_instance_lock = asyncio.Lock()


async def get_circuit_breaker() -> CircuitBreaker:
    """Get the module-level singleton circuit breaker instance.

    Returns:
        CircuitBreaker singleton instance

    Thread-safe lazy initialization on first access.
    """
    global _circuit_breaker_instance
    async with _instance_lock:
        if _circuit_breaker_instance is None:
            _circuit_breaker_instance = CircuitBreaker(
                failure_threshold=10,
                timeout=120,
                window=60,
            )
            set_circuit_state("CLOSED")
            logger.info(
                "Circuit breaker singleton initialized",
                extra={
                    "event": "circuit_breaker_init",
                    "failure_threshold": 10,
                    "timeout": 120,
                    "window": 60,
                },
            )
        return _circuit_breaker_instance


def circuit_breaker(func: Callable) -> Callable:
    """Decorator to apply circuit breaker to async functions.

    Uses the module-level singleton circuit breaker instance.

    Usage:
        @circuit_breaker
        async def fetch_fhir_resource(url: str):
            ...
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        breaker = await get_circuit_breaker()
        return await breaker.call(func, *args, **kwargs)

    return wrapper


async def _reset_for_testing() -> None:
    """Reset circuit breaker singleton for testing.
    
    WARNING: This is for testing only. Not exported in __all__.
    Resets the singleton instance to None so next access creates fresh state.
    """
    global _circuit_breaker_instance
    async with _instance_lock:
        _circuit_breaker_instance = None
