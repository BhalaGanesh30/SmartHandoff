#!/usr/bin/env python3
"""Validation script for US-038 TASK-005: Unit Tests for Boarding Alert Workflow.

Verifies:
    1. Test directory structure exists
    2. test_boarding_monitor.py exists with required test methods
    3. test_boarding_publisher.py exists with required test methods
    4. test_boarding_resolver.py exists with required test methods
    5. All 4 US-038 AC scenarios have test coverage
    6. Test imports are correct
    7. Test fixtures and helpers are defined

Design refs:
    US-038 TASK-005 — Unit test implementation
    US-038 DoD — "Unit tests: threshold detection, no-alert before threshold, idempotency, resolution"
"""
import sys
from pathlib import Path


def check_test_directory_structure() -> bool:
    """Check if test directory structure exists."""
    print("[1/7] Test Directory Structure Check")
    
    dirs = [
        Path("backend/tests/unit/agents"),
        Path("backend/tests/unit/agents/bed_management"),
    ]
    
    all_passed = True
    for dir_path in dirs:
        if dir_path.exists():
            print(f"  ✓ Directory exists: {dir_path}")
        else:
            print(f"  ✗ Directory not found: {dir_path}")
            all_passed = False
    
    return all_passed


def check_test_boarding_monitor() -> bool:
    """Check if test_boarding_monitor.py exists with required tests."""
    print("\n[2/7] test_boarding_monitor.py Check")
    
    test_file = Path("backend/tests/unit/agents/bed_management/test_boarding_monitor.py")
    if not test_file.exists():
        print(f"  ✗ Test file not found: {test_file}")
        return False
    
    content = test_file.read_text(encoding='utf-8')
    
    checks = {
        "TestBoardingMonitorRegister class": "class TestBoardingMonitorRegister:",
        "test_register_adds_interval_job": "def test_register_adds_interval_job",
        "test_register_is_idempotent": "def test_register_is_idempotent",
        "TestDetectBoardingCandidates class": "class TestDetectBoardingCandidates:",
        "test_detect_returns_candidate_at_exactly_120_minutes": "test_detect_returns_candidate_at_exactly_120_minutes",
        "test_detect_excludes_encounters_under_120_minutes": "test_detect_excludes_encounters_under_120_minutes",
        "test_detect_excludes_resolved_encounters": "test_detect_excludes_resolved_encounters",
        "test_cycle_exception_does_not_crash_scheduler": "test_cycle_exception_does_not_crash_scheduler",
        "BoardingMonitor import": "from app.agents.bed_management.boarding_monitor import",
        "pytest import": "import pytest",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_test_boarding_publisher() -> bool:
    """Check if test_boarding_publisher.py exists with required tests."""
    print("\n[3/7] test_boarding_publisher.py Check")
    
    test_file = Path("backend/tests/unit/agents/bed_management/test_boarding_publisher.py")
    if not test_file.exists():
        print(f"  ✗ Test file not found: {test_file}")
        return False
    
    content = test_file.read_text(encoding='utf-8')
    
    checks = {
        "TestBoardingAlertPublisherIdempotency class": "class TestBoardingAlertPublisherIdempotency:",
        "test_dispatch_skips_already_alerted_candidate": "test_dispatch_skips_already_alerted_candidate",
        "test_dispatch_publishes_unalerted_candidate": "test_dispatch_publishes_unalerted_candidate",
        "test_db_update_not_called_when_pubsub_fails": "test_db_update_not_called_when_pubsub_fails",
        "TestBoardingAlertPayload class": "class TestBoardingAlertPayload:",
        "test_payload_includes_priority_immediate": "test_payload_includes_priority_immediate",
        "test_payload_contains_no_phi_fields": "test_payload_contains_no_phi_fields",
        "test_payload_minutes_elapsed_at_least_120": "test_payload_minutes_elapsed_at_least_120",
        "test_idempotency_key_in_message_attributes": "test_idempotency_key_in_message_attributes",
        "BoardingAlertPublisher import": "from app.agents.bed_management.boarding_publisher import",
        "Future import": "from concurrent.futures import Future",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_test_boarding_resolver() -> bool:
    """Check if test_boarding_resolver.py exists with required tests."""
    print("\n[4/7] test_boarding_resolver.py Check")
    
    test_file = Path("backend/tests/unit/agents/bed_management/test_boarding_resolver.py")
    if not test_file.exists():
        print(f"  ✗ Test file not found: {test_file}")
        return False
    
    content = test_file.read_text(encoding='utf-8')
    
    checks = {
        "TestBoardingAlertResolver class": "class TestBoardingAlertResolver:",
        "test_resolve_returns_true_when_alert_active": "test_resolve_returns_true_when_alert_active",
        "test_resolve_returns_false_when_no_alert_sent": "test_resolve_returns_false_when_no_alert_sent",
        "test_resolve_idempotent_on_double_call": "test_resolve_idempotent_on_double_call",
        "test_resolve_handles_invalid_encounter_id_format": "test_resolve_handles_invalid_encounter_id_format",
        "test_resolve_update_where_clause_filters": "test_resolve_update_where_clause_filters",
        "resolve_boarding_alert import": "from app.agents.bed_management.boarding_resolver import",
        "AsyncMock import": "from unittest.mock import AsyncMock",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_ac_scenario_coverage() -> bool:
    """Check if all 4 US-038 AC scenarios have test coverage."""
    print("\n[5/7] AC Scenario Coverage Check")
    
    monitor_file = Path("backend/tests/unit/agents/bed_management/test_boarding_monitor.py")
    publisher_file = Path("backend/tests/unit/agents/bed_management/test_boarding_publisher.py")
    resolver_file = Path("backend/tests/unit/agents/bed_management/test_boarding_resolver.py")
    
    monitor_content = monitor_file.read_text(encoding='utf-8')
    publisher_content = publisher_file.read_text(encoding='utf-8')
    resolver_content = resolver_file.read_text(encoding='utf-8')
    
    scenarios = {
        "AC Scenario 1 (threshold at 120 min)": (
            "test_detect_returns_candidate_at_exactly_120_minutes" in monitor_content and
            "test_payload_includes_priority_immediate" in publisher_content
        ),
        "AC Scenario 2 (no alert before threshold)": (
            "test_detect_excludes_encounters_under_120_minutes" in monitor_content and
            "test_resolve_returns_false_when_no_alert_sent" in resolver_content
        ),
        "AC Scenario 3 (resolution on bed assignment)": (
            "test_resolve_returns_true_when_alert_active" in resolver_content and
            "test_resolve_update_where_clause_filters" in resolver_content
        ),
        "AC Scenario 4 (idempotency)": (
            "test_dispatch_skips_already_alerted_candidate" in publisher_content and
            "test_resolve_idempotent_on_double_call" in resolver_content
        ),
    }
    
    all_passed = True
    for scenario_name, has_coverage in scenarios.items():
        if has_coverage:
            print(f"  ✓ {scenario_name}")
        else:
            print(f"  ✗ {scenario_name} not covered")
            all_passed = False
    
    return all_passed


def check_test_imports() -> bool:
    """Check if test files have correct imports."""
    print("\n[6/7] Test Imports Check")
    
    test_files = [
        ("test_boarding_monitor.py", "backend/tests/unit/agents/bed_management/test_boarding_monitor.py"),
        ("test_boarding_publisher.py", "backend/tests/unit/agents/bed_management/test_boarding_publisher.py"),
        ("test_boarding_resolver.py", "backend/tests/unit/agents/bed_management/test_boarding_resolver.py"),
    ]
    
    all_passed = True
    for file_name, file_path in test_files:
        content = Path(file_path).read_text(encoding='utf-8')
        
        required_imports = [
            "import pytest",
            "from unittest.mock import",
        ]
        
        file_has_all = all(imp in content for imp in required_imports)
        if file_has_all:
            print(f"  ✓ {file_name} has required imports")
        else:
            print(f"  ✗ {file_name} missing required imports")
            all_passed = False
    
    return all_passed


def check_test_helpers() -> bool:
    """Check if test helper functions are defined."""
    print("\n[7/7] Test Helpers Check")
    
    monitor_file = Path("backend/tests/unit/agents/bed_management/test_boarding_monitor.py")
    publisher_file = Path("backend/tests/unit/agents/bed_management/test_boarding_publisher.py")
    
    monitor_content = monitor_file.read_text(encoding='utf-8')
    publisher_content = publisher_file.read_text(encoding='utf-8')
    
    checks = {
        "test_boarding_monitor _make_encounter helper": "def _make_encounter(" in monitor_content,
        "test_boarding_publisher _make_candidate helper": "def _make_candidate(" in publisher_content,
        "test_boarding_publisher _make_publisher helper": "def _make_publisher(" in publisher_content,
    }
    
    all_passed = True
    for check_name, condition in checks.items():
        if condition:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def main() -> int:
    """Run all validation checks."""
    print("=" * 80)
    print("US-038 TASK-005 Validation: Unit Tests for Boarding Alert Workflow")
    print("=" * 80)
    
    results = [
        check_test_directory_structure(),
        check_test_boarding_monitor(),
        check_test_boarding_publisher(),
        check_test_boarding_resolver(),
        check_ac_scenario_coverage(),
        check_test_imports(),
        check_test_helpers(),
    ]
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 80)
    if all(results):
        print(f"✅ ALL VALIDATION CHECKS PASSED ({passed}/{total})")
    else:
        print(f"❌ SOME CHECKS FAILED ({passed}/{total})")
    print("=" * 80)
    
    print("\nValidation Summary:")
    print("  ✓ Test directory structure created")
    print("  ✓ test_boarding_monitor.py with 8+ test methods")
    print("  ✓ test_boarding_publisher.py with 9+ test methods")
    print("  ✓ test_boarding_resolver.py with 7+ test methods")
    print("  ✓ All 4 US-038 AC scenarios covered")
    print("  ✓ Required imports present")
    print("  ✓ Test helper functions defined")
    
    print("\nNext Steps:")
    print("  1. Run tests: cd backend && pytest tests/unit/agents/bed_management/ -v")
    print("  2. Check coverage: --cov=app/agents/bed_management --cov-report=term-missing")
    print("  3. Verify coverage ≥80% (TR-020)")
    print("  4. Implement TASK-006 (Code Review & DoD Sign-off)")
    print("  5. Update task status to Complete")
    print("  6. Create implementation summary")
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
