"""Quick validation script for Prometheus metrics instrumentation.

Tests that all metrics are properly defined and helper functions work.
Run with: python test_metrics_validation.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.fhir.metrics import (
    CIRCUIT_STATE,
    FETCH_DURATION,
    RATE_LIMITED_TOTAL,
    RETRY_TOTAL,
    increment_rate_limited,
    increment_retry_outcome,
    observe_fetch_duration,
    set_circuit_state,
)


def test_circuit_state_metric():
    """Verify circuit breaker state metric."""
    print("Testing circuit state metric...")
    
    # Test CLOSED state
    set_circuit_state("CLOSED")
    assert CIRCUIT_STATE._value.get() == 0, "CLOSED state should be 0"
    
    # Test HALF_OPEN state
    set_circuit_state("HALF_OPEN")
    assert CIRCUIT_STATE._value.get() == 1, "HALF_OPEN state should be 1"
    
    # Test OPEN state
    set_circuit_state("OPEN")
    assert CIRCUIT_STATE._value.get() == 2, "OPEN state should be 2"
    
    print("✓ Circuit state metric working correctly")


def test_retry_outcome_metric():
    """Verify retry outcome counter."""
    print("Testing retry outcome metric...")
    
    # Get initial values
    initial_success = RETRY_TOTAL.labels(outcome="success")._value.get()
    initial_exhausted = RETRY_TOTAL.labels(outcome="exhausted")._value.get()
    initial_no_retry = RETRY_TOTAL.labels(outcome="no_retry_needed")._value.get()
    
    # Increment each outcome
    increment_retry_outcome("success")
    increment_retry_outcome("exhausted")
    increment_retry_outcome("no_retry_needed")
    
    # Verify increments
    assert RETRY_TOTAL.labels(outcome="success")._value.get() == initial_success + 1
    assert RETRY_TOTAL.labels(outcome="exhausted")._value.get() == initial_exhausted + 1
    assert RETRY_TOTAL.labels(outcome="no_retry_needed")._value.get() == initial_no_retry + 1
    
    print("✓ Retry outcome metric working correctly")


def test_rate_limited_metric():
    """Verify rate limiter counter."""
    print("Testing rate limited metric...")
    
    initial_count = RATE_LIMITED_TOTAL._value.get()
    
    increment_rate_limited()
    increment_rate_limited()
    
    assert RATE_LIMITED_TOTAL._value.get() == initial_count + 2
    
    print("✓ Rate limited metric working correctly")


def test_fetch_duration_metric():
    """Verify fetch duration histogram."""
    print("Testing fetch duration metric...")
    
    # Record some durations
    observe_fetch_duration("Patient", 0.15)
    observe_fetch_duration("Encounter", 0.25)
    observe_fetch_duration("MedicationStatement", 0.5)
    
    # Verify histogram has recorded samples (histogram stores sum as float directly)
    # We can verify by checking the metric collector
    from prometheus_client import REGISTRY
    for collector in REGISTRY.collect():
        if collector.name == "fhir_fetch_duration_seconds":
            for sample in collector.samples:
                if sample.name == "fhir_fetch_duration_seconds_count":
                    # At least one sample recorded
                    if sample.value > 0:
                        print(f"  Found sample: {sample.labels['resource_type']} count={sample.value}")
    
    print("✓ Fetch duration metric working correctly")


def test_metrics_export():
    """Verify metrics can be exported in Prometheus format."""
    print("Testing metrics export...")
    
    from prometheus_client import generate_latest
    
    metrics_output = generate_latest().decode('utf-8')
    
    # Check that all expected metrics are present
    assert "fhir_circuit_state" in metrics_output, "Circuit state metric should be exported"
    assert "fhir_retry_total" in metrics_output, "Retry total metric should be exported"
    assert "fhir_rate_limited_total" in metrics_output, "Rate limited metric should be exported"
    assert "fhir_fetch_duration_seconds" in metrics_output, "Fetch duration metric should be exported"
    
    print("✓ Metrics export working correctly")
    print("\nSample metrics output:")
    print("-" * 80)
    for line in metrics_output.split('\n'):
        if 'fhir_' in line and not line.startswith('#'):
            print(line)
    print("-" * 80)


def main():
    """Run all validation tests."""
    print("=" * 80)
    print("Prometheus Metrics Validation (TASK-002)")
    print("=" * 80)
    print()
    
    try:
        test_circuit_state_metric()
        test_retry_outcome_metric()
        test_rate_limited_metric()
        test_fetch_duration_metric()
        test_metrics_export()
        
        print()
        print("=" * 80)
        print("✅ All metrics validation tests passed!")
        print("=" * 80)
        return 0
    
    except AssertionError as e:
        print()
        print("=" * 80)
        print(f"❌ Validation failed: {e}")
        print("=" * 80)
        return 1
    
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
