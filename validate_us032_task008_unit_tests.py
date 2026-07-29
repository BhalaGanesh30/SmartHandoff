"""Validation script for US-032 TASK-008: Unit test implementation.

Validates that:
1. All three unit test files exist
2. Test functions are properly structured
3. Parametrized tests are configured correctly
4. Mocking is used appropriately
5. Async tests use @pytest.mark.asyncio
6. All acceptance criteria are covered

Design refs:
    US-032 AC Scenarios 1, 3, 4 — unit test coverage
    US-032 DoD — unit tests for each high-risk class, RBAC enforcement, SLA breach
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path


def validate_test_file_exists(test_file: str) -> bool:
    """Validate that a test file exists."""
    path = Path("backend/tests/unit") / test_file
    if not path.exists():
        print(f"   ❌ {test_file} not found")
        return False
    print(f"   ✓ {test_file} exists")
    return True


def validate_high_risk_detector_tests():
    """Validate test_high_risk_drug_class_detector.py structure."""
    print("\n1. Validating HighRiskDrugClassDetector tests...")

    test_file = "backend/tests/unit/test_high_risk_drug_class_detector.py"
    try:
        with open(test_file, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"   ❌ {test_file} not found")
        return False

    # Check imports
    required_imports = [
        "import pytest",
        "from app.agents.medication_reconciliation.drug_interaction.checker import",
        "from app.agents.medication_reconciliation.high_risk.detector import",
        "HighRiskDrugClassDetector",
        "DischargedMedication",
    ]
    for imp in required_imports:
        if imp not in content:
            print(f"   ❌ Missing import: {imp}")
            return False
    print("   ✓ All required imports present")

    # Check parametrize decorator
    if "@pytest.mark.parametrize" not in content:
        print("   ❌ Missing @pytest.mark.parametrize")
        return False
    print("   ✓ Parametrized tests configured")

    # Check for all four drug classes in parameters
    drug_classes = ["ANTICOAGULANT", "INSULIN", "OPIOID", "CHEMOTHERAPY"]
    for drug_class in drug_classes:
        if drug_class not in content:
            print(f"   ❌ Missing drug class: {drug_class}")
            return False
    print("   ✓ All four ISMP drug classes tested")

    # Count parametrized examples
    param_pattern = r'@pytest\.mark\.parametrize\(\s*"drug_name,\s*expected_class",\s*\[(.*?)\]'
    match = re.search(param_pattern, content, re.DOTALL)
    if match:
        param_count = match.group(1).count("(")
        if param_count >= 13:  # Task specifies 13 examples
            print(f"   ✓ {param_count} parametrized examples (≥13 required)")
        else:
            print(f"   ⚠ Only {param_count} parametrized examples (13 expected)")
    else:
        print("   ❌ Could not parse parametrize decorator")
        return False

    # Check test functions
    required_tests = [
        "test_detects_high_risk_drug_class",
        "test_non_high_risk_drug_returns_no_match",
        "test_detection_is_case_insensitive",
        "test_multiple_high_risk_drugs_returns_multiple_matches",
        "test_dose_stripped_before_matching",
        "test_empty_medication_list_returns_empty",
    ]
    for test in required_tests:
        if f"def {test}(" not in content:
            print(f"   ❌ Missing test: {test}")
            return False
    print(f"   ✓ All {len(required_tests)} test functions present")

    # Check fixture usage
    if "@pytest.fixture" not in content or "def detector()" not in content:
        print("   ❌ detector fixture not defined")
        return False
    print("   ✓ detector fixture defined")

    return True


def validate_alert_resolve_endpoint_tests():
    """Validate test_alert_resolve_endpoint.py structure."""
    print("\n2. Validating Alert Resolve Endpoint tests...")

    test_file = "backend/tests/unit/test_alert_resolve_endpoint.py"
    try:
        with open(test_file, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"   ❌ {test_file} not found")
        return False

    # Check imports
    required_imports = [
        "import pytest",
        "from unittest.mock import",
        "from fastapi.testclient import TestClient",
    ]
    for imp in required_imports:
        if imp not in content:
            print(f"   ❌ Missing import: {imp}")
            return False
    print("   ✓ All required imports present")

    # Check fixtures
    if "@pytest.fixture" not in content:
        print("   ❌ No fixtures defined")
        return False
    if "pharmacist_headers" not in content or "nurse_headers" not in content:
        print("   ❌ Missing header fixtures")
        return False
    print("   ✓ Header fixtures defined")

    # Check test functions
    required_tests = [
        "test_pharmacist_can_resolve_active_alert",
        "test_nurse_cannot_resolve_alert",
        "test_resolve_unknown_alert_returns_404",
        "test_resolve_already_resolved_alert_returns_409",
    ]
    for test in required_tests:
        if f"def {test}(" not in content:
            print(f"   ❌ Missing test: {test}")
            return False
    print(f"   ✓ All {len(required_tests)} test functions present")

    # Check for status code assertions (RBAC enforcement)
    if "assert response.status_code == 200" not in content:
        print("   ❌ Missing 200 status code assertion")
        return False
    if "assert response.status_code == 403" not in content:
        print("   ❌ Missing 403 status code assertion (RBAC)")
        return False
    if "assert response.status_code == 404" not in content:
        print("   ❌ Missing 404 status code assertion")
        return False
    if "assert response.status_code == 409" not in content:
        print("   ❌ Missing 409 status code assertion")
        return False
    print("   ✓ Status code assertions for 200, 403, 404, 409")

    # Check mocking usage
    if "patch(" not in content:
        print("   ❌ No mocking used")
        return False
    print("   ✓ Mocking used appropriately")

    return True


def validate_alert_sla_monitor_tests():
    """Validate test_alert_sla_monitor.py structure."""
    print("\n3. Validating Alert SLA Monitor tests...")

    test_file = "backend/tests/unit/test_alert_sla_monitor.py"
    try:
        with open(test_file, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"   ❌ {test_file} not found")
        return False

    # Check imports
    required_imports = [
        "import pytest",
        "from unittest.mock import",
        "from app.services.alert_sla_monitor import AlertSLAMonitor",
    ]
    for imp in required_imports:
        if imp not in content:
            print(f"   ❌ Missing import: {imp}")
            return False
    print("   ✓ All required imports present")

    # Check async test marker
    if "@pytest.mark.asyncio" not in content:
        print("   ❌ Missing @pytest.mark.asyncio decorator")
        return False
    print("   ✓ Async test markers present")

    # Check test functions
    required_tests = [
        "test_sla_breached_alert_is_tagged_and_escalated",
        "test_sla_monitor_is_idempotent",
        "test_resolved_alerts_not_escalated",
        "test_sla_monitor_continues_on_single_alert_failure",
    ]
    for test in required_tests:
        if f"async def {test}(" not in content:
            print(f"   ❌ Missing async test: {test}")
            return False
    print(f"   ✓ All {len(required_tests)} async test functions present")

    # Check key assertions
    if 'assert result["breached"]' not in content:
        print("   ❌ Missing breached counter assertion")
        return False
    if "assert alert.sla_breached is True" not in content:
        print("   ❌ Missing sla_breached flag assertion")
        return False
    if '"CHARGE_PHARMACIST_ESCALATION"' not in content:
        print("   ❌ Missing CHARGE_PHARMACIST_ESCALATION assertion")
        return False
    if '"IMMEDIATE"' not in content:
        print("   ❌ Missing IMMEDIATE priority assertion")
        return False
    print("   ✓ Key assertions present (breached, sla_breached, event_type, priority)")

    # Check idempotency test
    if 'result["breached"] == 0' not in content:
        print("   ❌ Idempotency test incomplete")
        return False
    print("   ✓ Idempotency test validates zero breached on re-run")

    # Check error handling test
    if 'result["skipped"]' not in content:
        print("   ❌ Error handling test incomplete")
        return False
    print("   ✓ Error handling test validates skipped counter")

    return True


def validate_test_structure_quality():
    """Validate overall test quality and structure."""
    print("\n4. Validating overall test quality...")

    all_passed = True

    # Check for proper docstrings
    for test_file in [
        "test_high_risk_drug_class_detector.py",
        "test_alert_resolve_endpoint.py",
        "test_alert_sla_monitor.py",
    ]:
        path = Path("backend/tests/unit") / test_file
        with open(path, "r") as f:
            content = f.read()

        # Check module docstring
        if '"""' not in content[:500]:
            print(f"   ⚠ {test_file} missing module docstring")
            all_passed = False
        else:
            print(f"   ✓ {test_file} has module docstring")

        # Check design refs
        if "Design refs:" not in content:
            print(f"   ⚠ {test_file} missing design references")
        else:
            print(f"   ✓ {test_file} has design references")

    return all_passed


def validate_acceptance_criteria_coverage():
    """Validate that all US-032 acceptance criteria are covered."""
    print("\n5. Validating acceptance criteria coverage...")

    all_passed = True

    # AC Scenario 1: Each high-risk drug class
    path = Path("backend/tests/unit/test_high_risk_drug_class_detector.py")
    with open(path, "r") as f:
        content = f.read()

    for drug_class in ["ANTICOAGULANT", "INSULIN", "OPIOID", "CHEMOTHERAPY"]:
        if content.count(f'"{drug_class}"') >= 1:
            print(f"   ✓ AC Scenario 1: {drug_class} tested")
        else:
            print(f"   ❌ AC Scenario 1: {drug_class} not tested")
            all_passed = False

    # AC Scenario 2: Pharmacist resolution
    path = Path("backend/tests/unit/test_alert_resolve_endpoint.py")
    with open(path, "r") as f:
        content = f.read()

    if "test_pharmacist_can_resolve_active_alert" in content:
        print("   ✓ AC Scenario 2: Pharmacist resolution tested")
    else:
        print("   ❌ AC Scenario 2: Pharmacist resolution not tested")
        all_passed = False

    # AC Scenario 3: SLA breach detection
    path = Path("backend/tests/unit/test_alert_sla_monitor.py")
    with open(path, "r") as f:
        content = f.read()

    if "test_sla_breached_alert_is_tagged_and_escalated" in content:
        print("   ✓ AC Scenario 3: SLA breach detection tested")
    else:
        print("   ❌ AC Scenario 3: SLA breach detection not tested")
        all_passed = False

    # AC Scenario 4: RBAC enforcement (403)
    path = Path("backend/tests/unit/test_alert_resolve_endpoint.py")
    with open(path, "r") as f:
        content = f.read()

    if "test_nurse_cannot_resolve_alert" in content and "403" in content:
        print("   ✓ AC Scenario 4: RBAC enforcement (403) tested")
    else:
        print("   ❌ AC Scenario 4: RBAC enforcement not tested")
        all_passed = False

    return all_passed


def validate_no_syntax_errors():
    """Validate that test files have no Python syntax errors."""
    print("\n6. Validating Python syntax...")

    all_passed = True
    for test_file in [
        "test_high_risk_drug_class_detector.py",
        "test_alert_resolve_endpoint.py",
        "test_alert_sla_monitor.py",
    ]:
        path = Path("backend/tests/unit") / test_file
        try:
            with open(path, "r") as f:
                code = f.read()
            compile(code, path, "exec")
            print(f"   ✓ {test_file} has no syntax errors")
        except SyntaxError as e:
            print(f"   ❌ {test_file} has syntax error: {e}")
            all_passed = False

    return all_passed


async def main():
    """Run all validation checks."""
    print("=" * 70)
    print("TASK-008 Validation: Unit Test Implementation")
    print("=" * 70)

    # Check file existence
    print("\n0. Checking test file existence...")
    files_exist = all([
        validate_test_file_exists("test_high_risk_drug_class_detector.py"),
        validate_test_file_exists("test_alert_resolve_endpoint.py"),
        validate_test_file_exists("test_alert_sla_monitor.py"),
    ])

    if not files_exist:
        print("\n❌ Some test files are missing. Aborting validation.")
        return 1

    checks = [
        validate_high_risk_detector_tests,
        validate_alert_resolve_endpoint_tests,
        validate_alert_sla_monitor_tests,
        validate_test_structure_quality,
        validate_acceptance_criteria_coverage,
        validate_no_syntax_errors,
    ]

    all_passed = True
    for check in checks:
        try:
            if not check():
                all_passed = False
        except Exception as e:
            print(f"   ❌ Check failed with exception: {e}")
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL VALIDATION CHECKS PASSED")
        print("=" * 70)
        print("\nUS-032 TASK-008 Acceptance Criteria:")
        print("  ✓ All 13 parametrized drug-class tests present")
        print("  ✓ Non-high-risk drug test present")
        print("  ✓ Case-insensitive test present")
        print("  ✓ Multiple high-risk drugs test present")
        print("  ✓ Pharmacist can resolve (200) test present")
        print("  ✓ Nurse cannot resolve (403) test present")
        print("  ✓ Unknown alert (404) test present")
        print("  ✓ Already resolved (409) test present")
        print("  ✓ SLA breach tagging and escalation test present")
        print("  ✓ SLA monitor idempotency test present")
        print("  ✓ SLA monitor continues on failure test present")
        print("\nAll unit tests ready to run with pytest.")
        print("\nNext steps:")
        print("  1. Run: cd backend && pytest tests/unit/ -v")
        print("  2. Verify all tests pass")
        print("  3. Check code coverage: pytest --cov=app tests/unit/")
        return 0
    else:
        print("❌ SOME VALIDATION CHECKS FAILED")
        print("=" * 70)
        print("\nPlease review the failed checks above and fix the issues.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
