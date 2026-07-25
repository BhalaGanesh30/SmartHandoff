"""
Performance test: p95 discharge summary generation latency < 30 seconds.

Test environment: staging (STAGE)
LLM: Vertex AI Gemini 1.5 Pro (real API calls)
FHIR: Staging FHIR R4 server with seeded encounters
Concurrency: asyncio.gather (10 concurrent batches of 10)

Run with:
    pytest tests/performance/test_discharge_summary_p95.py \
        --env=staging \
        -v \
        --timeout=600
"""
from __future__ import annotations

import asyncio
import statistics
import time
from typing import List

import pytest

from agents.documentation.agent import DocumentationAgent
from tests.performance.fixtures.encounter_factory import build_test_encounters


# ---- Configuration --------------------------------------------------------
P95_LATENCY_THRESHOLD_MS = 30_000   # 30 seconds
TOTAL_TEST_CASES = 100
BATCH_SIZE = 10                      # 10 concurrent generations per batch


# ---- Fixtures -------------------------------------------------------------

@pytest.fixture(scope="module")
def test_encounters():
    """
    Generate 100 test EncounterContext instances with varying complexity:
    - diagnosis count: 1–8 (uniformly distributed)
    - medication count: 1–12 (uniformly distributed)
    - length of stay: 1–14 days
    """
    return build_test_encounters(count=TOTAL_TEST_CASES)


@pytest.fixture(scope="module")
def documentation_agent(staging_fhir_client, staging_doc_repository, staging_settings):
    """Real DocumentationAgent wired to staging dependencies."""
    return DocumentationAgent(
        fhir_client=staging_fhir_client,
        document_repository=staging_doc_repository,
        project_id=staging_settings.GCP_PROJECT_ID,
        location=staging_settings.GCP_REGION,
    )


# ---- Performance Harness --------------------------------------------------

async def _run_single(agent: DocumentationAgent, event: dict) -> int:
    """Run one generation and return wall-clock milliseconds."""
    start = time.monotonic_ns()
    await agent.process(event)
    return (time.monotonic_ns() - start) // 1_000_000


async def _run_batch(agent: DocumentationAgent, events: list[dict]) -> list[int]:
    """Run a batch of events concurrently; return list of latencies in ms."""
    return list(await asyncio.gather(*[_run_single(agent, e) for e in events]))


# ---- Test -----------------------------------------------------------------

@pytest.mark.performance
@pytest.mark.asyncio
@pytest.mark.timeout(600)  # 10-minute overall test timeout
async def test_p95_discharge_summary_latency(documentation_agent, test_encounters):
    """
    Assert that the 95th-percentile discharge summary generation latency
    is under 30,000 ms across 100 test cases.
    """
    all_latencies: List[int] = []

    # Run in batches of BATCH_SIZE to avoid overwhelming staging Gemini quota
    for batch_start in range(0, TOTAL_TEST_CASES, BATCH_SIZE):
        batch = test_encounters[batch_start : batch_start + BATCH_SIZE]
        events = [
            {"event_type": "A03", "encounter_id": enc.encounter_id, "occurred_at": "2026-07-16T10:00:00Z"}
            for enc in batch
        ]
        batch_latencies = await _run_batch(documentation_agent, events)
        all_latencies.extend(batch_latencies)

        # Progress log for CI visibility
        completed = min(batch_start + BATCH_SIZE, TOTAL_TEST_CASES)
        current_p95 = _percentile(all_latencies, 95)
        print(f"  [{completed}/{TOTAL_TEST_CASES}] running p95 = {current_p95} ms")

    # ---- Assertions -------------------------------------------------------
    assert len(all_latencies) == TOTAL_TEST_CASES, (
        f"Expected {TOTAL_TEST_CASES} latency samples, got {len(all_latencies)}"
    )

    p95_ms = _percentile(all_latencies, 95)
    p50_ms = _percentile(all_latencies, 50)
    max_ms = max(all_latencies)
    min_ms = min(all_latencies)
    mean_ms = int(statistics.mean(all_latencies))

    # Report for CI output
    print(
        f"\n=== Discharge Summary Generation Latency Report ===\n"
        f"  Samples : {TOTAL_TEST_CASES}\n"
        f"  p50     : {p50_ms} ms\n"
        f"  p95     : {p95_ms} ms  (threshold: {P95_LATENCY_THRESHOLD_MS} ms)\n"
        f"  mean    : {mean_ms} ms\n"
        f"  min     : {min_ms} ms\n"
        f"  max     : {max_ms} ms\n"
        f"  fallback count: {sum(1 for l in all_latencies if l >= 25_000)}\n"
    )

    assert p95_ms < P95_LATENCY_THRESHOLD_MS, (
        f"p95 latency {p95_ms} ms exceeds threshold {P95_LATENCY_THRESHOLD_MS} ms. "
        f"Histogram: min={min_ms}ms, p50={p50_ms}ms, p95={p95_ms}ms, max={max_ms}ms"
    )


def _percentile(data: List[int], percentile: int) -> int:
    """Compute the Nth percentile from a list of integer millisecond values."""
    if not data:
        raise ValueError("Cannot compute percentile of empty list")
    sorted_data = sorted(data)
    index = int(len(sorted_data) * percentile / 100)
    return sorted_data[min(index, len(sorted_data) - 1)]
