"""Prometheus metrics for FHIR client resilience patterns.

Exposes metrics for circuit breaker, retry, rate limiter, and fetch duration.
Scraped by Cloud Monitoring (GCP Prometheus integration).

Metrics:
  - fhir_circuit_state{state}            — Gauge (CLOSED=0, HALF_OPEN=1, OPEN=2)
  - fhir_retry_total{outcome}            — Counter (success, exhausted, no_retry_needed)
  - fhir_rate_limited_total              — Counter (rate limiter backoff events)
  - fhir_fetch_duration_seconds{resource_type} — Histogram (fetch latency)

Design refs:
    US-018 DoD — Prometheus metrics requirement
    TR-016     — Observability / metrics
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Circuit Breaker Metrics ───────────────────────────────────────────────────
CIRCUIT_STATE: Gauge = Gauge(
    name="fhir_circuit_state",
    documentation=(
        "Current circuit breaker state for FHIR API calls. "
        "Values: 0=CLOSED, 1=HALF_OPEN, 2=OPEN"
    ),
)

# ── Retry Metrics ─────────────────────────────────────────────────────────────
RETRY_TOTAL: Counter = Counter(
    name="fhir_retry_total",
    documentation=(
        "Total FHIR API retry outcomes. "
        "Labels: outcome (success, exhausted, no_retry_needed)"
    ),
    labelnames=["outcome"],
)

# ── Rate Limiter Metrics ──────────────────────────────────────────────────────
RATE_LIMITED_TOTAL: Counter = Counter(
    name="fhir_rate_limited_total",
    documentation=(
        "Total number of FHIR API requests delayed due to rate limiting "
        "(token bucket empty, backoff applied)."
    ),
)

# ── Fetch Duration Metrics ────────────────────────────────────────────────────
FETCH_DURATION: Histogram = Histogram(
    name="fhir_fetch_duration_seconds",
    documentation=(
        "FHIR resource fetch latency in seconds, labelled by resource type. "
        "Measured from HTTP request start to response body received."
    ),
    labelnames=["resource_type"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


# ── Helper Functions ──────────────────────────────────────────────────────────
def set_circuit_state(state: str) -> None:
    """Update circuit breaker state gauge.

    Args:
        state: CircuitBreakerState value (CLOSED, HALF_OPEN, OPEN)
    """
    state_values = {"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}
    CIRCUIT_STATE.set(state_values.get(state, 0))


def increment_retry_outcome(outcome: str) -> None:
    """Increment retry outcome counter.

    Args:
        outcome: Retry result (success, exhausted, no_retry_needed)
    """
    RETRY_TOTAL.labels(outcome=outcome).inc()


def increment_rate_limited() -> None:
    """Increment rate limiter backoff counter."""
    RATE_LIMITED_TOTAL.inc()


def observe_fetch_duration(resource_type: str, duration: float) -> None:
    """Record FHIR fetch duration.

    Args:
        resource_type: FHIR resource type (Patient, Encounter, etc.)
        duration: Fetch duration in seconds
    """
    FETCH_DURATION.labels(resource_type=resource_type).observe(duration)
