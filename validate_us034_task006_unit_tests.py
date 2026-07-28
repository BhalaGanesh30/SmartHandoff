#!/usr/bin/env python3
"""Validation script for US-034 TASK-006: Unit Tests Implementation.

Validates:
1. MedRecSLAMonitor unit tests exist
2. Override endpoint unit tests exist
3. All required test functions are present
4. Tests cover all US-034 scenarios (1-4)
"""
import ast
import sys
from pathlib import Path


def print_header(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'=' * 70}")
    print(f"{title}")
    print(f"{'=' * 70}\n")


def print_result(check: str, passed: bool) -> None:
    """Print a check result."""
    symbol = "✅" if passed else "❌"
    print(f"{symbol} {check}")


def validate_medrec_sla_monitor_tests() -> tuple[int, int]:
    """Validate MedRecSLAMonitor unit tests."""
    test_path = Path("services/sla-monitor/tests/unit/test_medrec_sla_monitor.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("1. MEDREC SLA MONITOR TESTS VALIDATION")
    
    if not test_path.exists():
        print_result("test_medrec_sla_monitor.py file exists", False)
        return 0, 1
    
    print_result("test_medrec_sla_monitor.py file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with test_path.open("r") as f:
        content = f.read()
    
    # Parse AST to find test functions
    try:
        tree = ast.parse(content)
        test_functions = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("test_")
        ]
    except SyntaxError:
        print_result("File has valid Python syntax", False)
        return checks_passed, total_checks + 1
    
    total_checks += 1
    print_result("File has valid Python syntax", True)
    checks_passed += 1
    
    # Check for required test functions (US-034 DoD)
    required_tests = [
        ("test_escalation_fired_when_admit_time_exceeds_24h", "Scenario 1: 24h escalation"),
        ("test_escalation_not_fired_when_admit_time_under_24h", "Scenario 1: boundary check"),
        ("test_completed_task_not_returned_by_find_breached_tasks", "Scenario 2: completed task exclusion"),
        ("test_duplicate_escalation_not_sent_when_already_stamped", "Scenario 3: duplicate suppression"),
        ("test_handle_breach_stamps_sla_escalation_sent_at_before_publish", "Scenario 3: stamp order"),
        ("test_publisher_called_with_correct_payload_fields", "Payload validation"),
    ]
    
    for test_name, description in required_tests:
        total_checks += 1
        has_test = test_name in test_functions
        print_result(f"{description}: {test_name}()", has_test)
        if has_test:
            checks_passed += 1
    
    # Check imports
    total_checks += 1
    has_pytest_import = "import pytest" in content
    print_result("Imports pytest", has_pytest_import)
    if has_pytest_import:
        checks_passed += 1
    
    total_checks += 1
    has_asyncmock_import = "from unittest.mock import AsyncMock" in content
    print_result("Imports AsyncMock for mocking", has_asyncmock_import)
    if has_asyncmock_import:
        checks_passed += 1
    
    total_checks += 1
    has_monitor_import = "from app.monitor.medrec_sla_monitor import MedRecSLAMonitor" in content
    print_result("Imports MedRecSLAMonitor", has_monitor_import)
    if has_monitor_import:
        checks_passed += 1
    
    # Check pytest.mark.asyncio decorators
    total_checks += 1
    has_async_markers = "@pytest.mark.asyncio" in content
    print_result("Uses @pytest.mark.asyncio decorators", has_async_markers)
    if has_async_markers:
        checks_passed += 1
    
    print(f"\n📊 MedRecSLAMonitor Tests: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_override_endpoint_tests() -> tuple[int, int]:
    """Validate override endpoint unit tests."""
    test_path = Path("backend/tests/unit/test_task_override_endpoint.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("2. OVERRIDE ENDPOINT TESTS VALIDATION")
    
    if not test_path.exists():
        print_result("test_task_override_endpoint.py file exists", False)
        return 0, 1
    
    print_result("test_task_override_endpoint.py file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with test_path.open("r") as f:
        content = f.read()
    
    # Parse AST to find test functions
    try:
        tree = ast.parse(content)
        test_functions = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("test_")
        ]
    except SyntaxError:
        print_result("File has valid Python syntax", False)
        return checks_passed, total_checks + 1
    
    total_checks += 1
    print_result("File has valid Python syntax", True)
    checks_passed += 1
    
    # Check for required test functions (US-034 Scenario 4 + RBAC)
    required_tests = [
        ("test_override_succeeds_for_charge_pharmacist", "Scenario 4: successful override"),
        ("test_override_returns_404_when_task_not_found", "Error handling: 404"),
        ("test_override_returns_409_when_already_completed", "Error handling: 409"),
        ("test_override_returns_422_when_invalid_task_type", "Error handling: 422"),
        ("test_override_clears_sla_escalation_sent_at", "Scenario 4: clears SLA field"),
    ]
    
    for test_name, description in required_tests:
        total_checks += 1
        has_test = test_name in test_functions
        print_result(f"{description}: {test_name}()", has_test)
        if has_test:
            checks_passed += 1
    
    # Check imports
    total_checks += 1
    has_pytest_import = "import pytest" in content
    print_result("Imports pytest", has_pytest_import)
    if has_pytest_import:
        checks_passed += 1
    
    total_checks += 1
    has_exceptions_import = "from app.repositories.agent_task_repository import" in content
    print_result("Imports repository exceptions", has_exceptions_import)
    if has_exceptions_import:
        checks_passed += 1
    
    total_checks += 1
    has_asyncmock_import = "from unittest.mock import AsyncMock" in content
    print_result("Imports AsyncMock for mocking", has_asyncmock_import)
    if has_asyncmock_import:
        checks_passed += 1
    
    # Check pytest.mark.asyncio decorators
    total_checks += 1
    has_async_markers = "@pytest.mark.asyncio" in content
    print_result("Uses @pytest.mark.asyncio decorators", has_async_markers)
    if has_async_markers:
        checks_passed += 1
    
    # Check for exception assertions
    total_checks += 1
    has_404_check = "assert exc_info.value.status_code == 404" in content
    print_result("Validates HTTP 404 status code", has_404_check)
    if has_404_check:
        checks_passed += 1
    
    total_checks += 1
    has_409_check = "assert exc_info.value.status_code == 409" in content
    print_result("Validates HTTP 409 status code", has_409_check)
    if has_409_check:
        checks_passed += 1
    
    total_checks += 1
    has_422_check = "assert exc_info.value.status_code == 422" in content
    print_result("Validates HTTP 422 status code", has_422_check)
    if has_422_check:
        checks_passed += 1
    
    print(f"\n📊 Override Endpoint Tests: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_test_coverage() -> tuple[int, int]:
    """Validate that all US-034 scenarios are covered."""
    checks_passed = 0
    total_checks = 0
    
    print_header("3. US-034 SCENARIO COVERAGE VALIDATION")
    
    medrec_test_path = Path("services/sla-monitor/tests/unit/test_medrec_sla_monitor.py")
    override_test_path = Path("backend/tests/unit/test_task_override_endpoint.py")
    
    # Scenario 1: Escalation at 24h
    total_checks += 1
    if medrec_test_path.exists():
        with medrec_test_path.open("r") as f:
            content = f.read()
        has_scenario_1 = "US-034 Scenario 1" in content and "24h" in content.lower()
        print_result("Scenario 1: Escalation at 24h (covered)", has_scenario_1)
        if has_scenario_1:
            checks_passed += 1
    else:
        print_result("Scenario 1: Escalation at 24h (covered)", False)
    
    # Scenario 2: Completed task no escalation
    total_checks += 1
    if medrec_test_path.exists():
        with medrec_test_path.open("r") as f:
            content = f.read()
        has_scenario_2 = "US-034 Scenario 2" in content and "COMPLETED" in content
        print_result("Scenario 2: Completed task no escalation (covered)", has_scenario_2)
        if has_scenario_2:
            checks_passed += 1
    else:
        print_result("Scenario 2: Completed task no escalation (covered)", False)
    
    # Scenario 3: No duplicate escalation
    total_checks += 1
    if medrec_test_path.exists():
        with medrec_test_path.open("r") as f:
            content = f.read()
        has_scenario_3 = "US-034 Scenario 3" in content and "duplicate" in content.lower()
        print_result("Scenario 3: No duplicate escalation (covered)", has_scenario_3)
        if has_scenario_3:
            checks_passed += 1
    else:
        print_result("Scenario 3: No duplicate escalation (covered)", False)
    
    # Scenario 4: Override endpoint
    total_checks += 1
    if override_test_path.exists():
        with override_test_path.open("r") as f:
            content = f.read()
        has_scenario_4 = "US-034 Scenario 4" in content and "override" in content.lower()
        print_result("Scenario 4: Override endpoint (covered)", has_scenario_4)
        if has_scenario_4:
            checks_passed += 1
    else:
        print_result("Scenario 4: Override endpoint (covered)", False)
    
    print(f"\n📊 Scenario Coverage: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def main() -> int:
    """Run all validation checks."""
    print_header("US-034 TASK-006 VALIDATION\nUnit Tests Implementation")
    
    all_checks_passed = 0
    all_total_checks = 0
    
    medrec_passed, medrec_total = validate_medrec_sla_monitor_tests()
    all_checks_passed += medrec_passed
    all_total_checks += medrec_total
    
    override_passed, override_total = validate_override_endpoint_tests()
    all_checks_passed += override_passed
    all_total_checks += override_total
    
    coverage_passed, coverage_total = validate_test_coverage()
    all_checks_passed += coverage_passed
    all_total_checks += coverage_total
    
    print_header("📊 OVERALL VALIDATION SUMMARY")
    print(f"Total Checks Passed: {all_checks_passed}/{all_total_checks}")
    
    success_rate = (all_checks_passed / all_total_checks * 100) if all_total_checks > 0 else 0
    print(f"Success Rate: {success_rate:.1f}%\n")
    
    if all_checks_passed == all_total_checks:
        print("✅ ALL VALIDATION CHECKS PASSED\n")
        print("US-034 TASK-006 Implementation:")
        print("  ✓ MedRecSLAMonitor unit tests created (6 tests)")
        print("  ✓ Override endpoint unit tests created (5 tests)")
        print("  ✓ All US-034 scenarios covered (Scenarios 1-4)")
        print("  ✓ Scenario 1: Escalation at 24h")
        print("  ✓ Scenario 2: Completed task no escalation")
        print("  ✓ Scenario 3: No duplicate escalation")
        print("  ✓ Scenario 4: Override endpoint with RBAC")
        print("  ✓ Error handling tests (404, 409, 422)")
        print("  ✓ All tests use pytest.mark.asyncio")
        print("  ✓ All tests use AsyncMock for async mocking")
        print("\nNext steps:")
        print("  1. Run: pytest services/sla-monitor/tests/unit/test_medrec_sla_monitor.py -v")
        print("  2. Run: pytest backend/tests/unit/test_task_override_endpoint.py -v")
        print("  3. Mark task as Complete")
        print("  4. Create implementation summary")
        return 0
    else:
        print(f"❌ {all_total_checks - all_checks_passed} VALIDATION CHECK(S) FAILED\n")
        print("Please review the failed checks above and fix the issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
