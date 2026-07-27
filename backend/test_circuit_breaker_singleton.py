"""Validation script for circuit breaker singleton refactoring (US-018 TASK-001).

Tests:
1. Circuit breaker is a module-level singleton
2. State persists across accessor calls
3. Multiple FHIRClient instances share the same circuit breaker

Run with: python -m pytest test_circuit_breaker_singleton.py -v
Or directly: python test_circuit_breaker_singleton.py
"""
import asyncio

from app.core.fhir.circuit_breaker import CircuitBreakerState, get_circuit_breaker


async def test_singleton():
    """Verify circuit breaker is a singleton."""
    print("Testing singleton pattern...")
    breaker1 = await get_circuit_breaker()
    breaker2 = await get_circuit_breaker()
    
    assert breaker1 is breaker2, "Circuit breaker should be singleton"
    assert breaker1.state == CircuitBreakerState.CLOSED
    print("✓ Circuit breaker singleton verified")


async def test_state_persistence():
    """Verify state persists across accessor calls."""
    print("\nTesting state persistence...")
    breaker = await get_circuit_breaker()
    
    # Simulate failure
    original_count = breaker.failure_count
    breaker.failure_count = 5
    
    # Get instance again — should have same state
    breaker2 = await get_circuit_breaker()
    assert breaker2.failure_count == 5, f"State should persist (expected 5, got {breaker2.failure_count})"
    
    # Reset for next tests
    breaker.failure_count = original_count
    print("✓ State persistence verified")


async def test_shared_across_clients():
    """Verify multiple clients would share the same circuit breaker instance."""
    print("\nTesting shared state across multiple accessor calls...")
    
    # Simulate what would happen with multiple FHIRClient instances
    breaker_client1 = await get_circuit_breaker()
    breaker_client2 = await get_circuit_breaker()
    
    # Modify state through first "client"
    breaker_client1.failure_count = 7
    
    # Verify second "client" sees the same state
    assert breaker_client2.failure_count == 7, "State should be shared"
    assert breaker_client1 is breaker_client2, "Should be same instance"
    
    # Reset
    breaker_client1.failure_count = 0
    print("✓ Shared state across clients verified")


async def test_initialization_parameters():
    """Verify singleton is initialized with correct parameters."""
    print("\nTesting initialization parameters...")
    breaker = await get_circuit_breaker()
    
    assert breaker.failure_threshold == 10, "Failure threshold should be 10"
    assert breaker.timeout == 120, "Timeout should be 120s"
    assert breaker.window == 60, "Window should be 60s"
    assert breaker.state == CircuitBreakerState.CLOSED, "Initial state should be CLOSED"
    print("✓ Initialization parameters verified")


async def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Circuit Breaker Singleton Validation (US-018 TASK-001)")
    print("=" * 60)
    
    try:
        await test_singleton()
        await test_state_persistence()
        await test_shared_across_clients()
        await test_initialization_parameters()
        
        print("\n" + "=" * 60)
        print("✓ All validation tests passed!")
        print("=" * 60)
        return 0
        
    except AssertionError as exc:
        print(f"\n✗ Validation failed: {exc}")
        return 1
    except Exception as exc:
        print(f"\n✗ Unexpected error: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
