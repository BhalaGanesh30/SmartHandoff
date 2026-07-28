#!/usr/bin/env python
"""Validation script for US-035 TASK-006: Unit Tests.

Validates:
1. Test File Structure
2. Test Discovery
3. Test Naming Conventions
4. Import Statements
5. Pytest Markers
6. Coverage Targets

Run: python validate_us035_task006_unit_tests.py

Design refs:
    US-035 TASK-006 — Unit test implementation for US-035 components
    US-035 DoD       — ≥80% branch coverage; all 4 AC scenarios covered
"""
from __future__ import annotations

import pathlib
import sys

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

TEST_FILES = [
    pathlib.Path("backend/tests/unit/agents/bed_management/test_bed_status_machine.py"),
    pathlib.Path("backend/tests/unit/agents/bed_management/test_bed_management_agent.py"),
    pathlib.Path("backend/tests/unit/agents/bed_management/test_bed_inventory_seeder.py"),
    pathlib.Path("backend/tests/unit/agents/bed_management/test_housekeeping_notifier.py"),
    pathlib.Path("backend/tests/unit/routers/test_beds.py"),
]

INIT_FILES = [
    pathlib.Path("backend/tests/unit/agents/bed_management/__init__.py"),
]

# ══════════════════════════════════════════════════════════════════════════════
# VALIDATORS
# ══════════════════════════════════════════════════════════════════════════════


def validate_file_structure() -> tuple[int, list[str]]:
    """Validate all test files and __init__.py files exist."""
    errors: list[str] = []
    checks_passed = 0

    # Check test files
    for test_file in TEST_FILES:
        if test_file.exists():
            print(f"✅ Test file exists: {test_file}")
            checks_passed += 1
        else:
            errors.append(f"❌ Test file missing: {test_file}")

    # Check __init__.py files
    for init_file in INIT_FILES:
        if init_file.exists():
            print(f"✅ __init__.py exists: {init_file}")
            checks_passed += 1
        else:
            errors.append(f"❌ __init__.py missing: {init_file}")

    return checks_passed, errors


def validate_test_naming() -> tuple[int, list[str]]:
    """Validate test function naming conventions."""
    errors: list[str] = []
    checks_passed = 0

    for test_file in TEST_FILES:
        if not test_file.exists():
            continue

        content = test_file.read_text(encoding="utf-8")
        
        # Check for test function definitions
        if "def test_" in content or "@pytest.mark.asyncio" in content:
            print(f"✅ {test_file.name}: Contains test functions")
            checks_passed += 1
        else:
            errors.append(f"❌ {test_file.name}: No test functions found")

        # Check for module docstring
        if '"""' in content[:500]:
            print(f"✅ {test_file.name}: Has module docstring")
            checks_passed += 1
        else:
            errors.append(f"❌ {test_file.name}: Missing module docstring")

    return checks_passed, errors


def validate_imports() -> tuple[int, list[str]]:
    """Validate required imports are present."""
    errors: list[str] = []
    checks_passed = 0

    # Required imports by file
    required_imports = {
        "test_bed_status_machine.py": [
            "import pytest",
            "from app.agents.bed_management.schemas import BedStatus",
            "from app.agents.bed_management.status_machine import resolve_target_status",
            "from app.exceptions import BedStatusTransitionError",
        ],
        "test_bed_management_agent.py": [
            "import pytest",
            "from unittest.mock import AsyncMock",
            "from app.agents.bed_management.agent import BedManagementAgent",
            "from app.agents.bed_management.schemas import BedStatus",
        ],
        "test_bed_inventory_seeder.py": [
            "import pytest",
            "from app.agents.bed_management.seeder import BedInventorySeeder",
        ],
        "test_housekeeping_notifier.py": [
            "import pytest",
            "from app.agents.bed_management.notifier import HousekeepingNotifier",
        ],
        "test_beds.py": [
            "import pytest",
            "from fastapi.testclient import TestClient",
            "from app.main import app",
        ],
    }

    for test_file in TEST_FILES:
        if not test_file.exists():
            continue

        content = test_file.read_text(encoding="utf-8")
        filename = test_file.name

        if filename not in required_imports:
            continue

        for required_import in required_imports[filename]:
            if required_import in content:
                print(f"✅ {filename}: {required_import}")
                checks_passed += 1
            else:
                errors.append(f"❌ {filename}: Missing {required_import}")

    return checks_passed, errors


def validate_pytest_markers() -> tuple[int, list[str]]:
    """Validate pytest markers for async tests."""
    errors: list[str] = []
    checks_passed = 0

    async_test_files = [
        "test_bed_management_agent.py",
        "test_bed_inventory_seeder.py",
        "test_housekeeping_notifier.py",
        "test_beds.py",
    ]

    for test_file in TEST_FILES:
        if not test_file.exists():
            continue

        if test_file.name not in async_test_files:
            continue

        content = test_file.read_text(encoding="utf-8")

        # Check for @pytest.mark.asyncio
        if "@pytest.mark.asyncio" in content:
            print(f"✅ {test_file.name}: Has @pytest.mark.asyncio markers")
            checks_passed += 1
        else:
            errors.append(f"❌ {test_file.name}: Missing @pytest.mark.asyncio markers")

    return checks_passed, errors


def validate_test_coverage_mapping() -> tuple[int, list[str]]:
    """Validate all AC scenarios are mapped to tests."""
    errors: list[str] = []
    checks_passed = 0

    # AC scenario coverage mapping
    scenario_tests = {
        "SC-1 (A01)": ["test_a01_sets_bed_to_occupied", "test_a01_triggers_mv_refresh"],
        "SC-2 (A03)": ["test_a03_sets_bed_to_dirty_and_notifies"],
        "SC-3 (GET filter)": ["test_get_beds_filter_unit_and_status", "test_get_beds_no_filter_returns_all"],
        "SC-4 (Seeding)": ["test_seed_inserts_beds_on_first_run", "test_seed_is_idempotent_on_second_run"],
    }

    # Read all test files into one string for searching
    all_content = ""
    for test_file in TEST_FILES:
        if test_file.exists():
            all_content += test_file.read_text(encoding="utf-8")

    for scenario, test_names in scenario_tests.items():
        found_count = 0
        for test_name in test_names:
            if f"def {test_name}" in all_content or f"async def {test_name}" in all_content:
                found_count += 1

        if found_count == len(test_names):
            print(f"✅ {scenario}: All {len(test_names)} test(s) found")
            checks_passed += 1
        else:
            errors.append(f"❌ {scenario}: Only {found_count}/{len(test_names)} test(s) found")

    return checks_passed, errors


def validate_fixtures() -> tuple[int, list[str]]:
    """Validate pytest fixtures are defined."""
    errors: list[str] = []
    checks_passed = 0

    fixture_checks = {
        "test_bed_management_agent.py": ["mock_refresh_service", "mock_notifier", "mock_session_factory", "agent"],
        "test_bed_inventory_seeder.py": ["valid_yaml_path", "mock_refresh_service"],
        "test_housekeeping_notifier.py": ["mock_pubsub_client", "mock_session_factory", "notifier"],
        "test_beds.py": ["bed_manager_user", "physician_user", "mock_read_db", "mock_write_db"],
    }

    for test_file in TEST_FILES:
        if not test_file.exists():
            continue

        filename = test_file.name
        if filename not in fixture_checks:
            continue

        content = test_file.read_text(encoding="utf-8")

        for fixture_name in fixture_checks[filename]:
            if f"@pytest.fixture" in content and f"def {fixture_name}" in content:
                print(f"✅ {filename}: Fixture '{fixture_name}' defined")
                checks_passed += 1
            else:
                errors.append(f"❌ {filename}: Missing fixture '{fixture_name}'")

    return checks_passed, errors


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    """Run all validators and report results."""
    print("=" * 70)
    print("US-035 TASK-006 VALIDATION")
    print("Unit Tests for Bed Management System")
    print("=" * 70)

    all_errors: list[str] = []
    total_checks = 0
    total_passed = 0

    # 1. File Structure
    print("\n" + "=" * 70)
    print("1. FILE STRUCTURE")
    print("=" * 70)
    passed, errors = validate_file_structure()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 File Structure: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 File Structure: ✅ All checks passed")

    # 2. Test Naming
    print("\n" + "=" * 70)
    print("2. TEST NAMING CONVENTIONS")
    print("=" * 70)
    passed, errors = validate_test_naming()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Test Naming: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Test Naming: ✅ All checks passed")

    # 3. Imports
    print("\n" + "=" * 70)
    print("3. IMPORT STATEMENTS")
    print("=" * 70)
    passed, errors = validate_imports()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Imports: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Imports: ✅ All checks passed")

    # 4. Pytest Markers
    print("\n" + "=" * 70)
    print("4. PYTEST MARKERS")
    print("=" * 70)
    passed, errors = validate_pytest_markers()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Pytest Markers: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Pytest Markers: ✅ All checks passed")

    # 5. AC Coverage Mapping
    print("\n" + "=" * 70)
    print("5. ACCEPTANCE CRITERIA COVERAGE")
    print("=" * 70)
    passed, errors = validate_test_coverage_mapping()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 AC Coverage: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 AC Coverage: ✅ All checks passed")

    # 6. Fixtures
    print("\n" + "=" * 70)
    print("6. PYTEST FIXTURES")
    print("=" * 70)
    passed, errors = validate_fixtures()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Fixtures: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Fixtures: ✅ All checks passed")

    # Final Summary
    print("\n" + "=" * 70)
    print("📊 OVERALL VALIDATION SUMMARY")
    print("=" * 70)

    print(f"\nTotal Checks: {total_checks}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {len(all_errors)}")
    
    if all_errors:
        print(f"\n❌ VALIDATION FAILED: {len(all_errors)} critical error(s) found\n")
        print("Critical Errors:")
        for err in all_errors[:10]:
            print(f"  {err}")
        if len(all_errors) > 10:
            print(f"  ... and {len(all_errors) - 10} more errors")
    else:
        print(f"\n✅ ALL VALIDATION CHECKS PASSED ({total_passed}/{total_checks})\n")
        print("US-035 TASK-006 Implementation Status:")
        print("  ✓ 5 test files created")
        print("  ✓ All AC scenarios covered")
        print("  ✓ Pytest fixtures properly defined")
        print("  ✓ Async test markers present")
        print("  ✓ Required imports verified")

    if not all_errors:
        print("\nNext steps:")
        print("  1. Run pytest to execute tests:")
        print("     cd backend")
        print("     pytest tests/unit/agents/bed_management/ -v")
        print("     pytest tests/unit/routers/test_beds.py -v")
        print("  2. Check coverage:")
        print("     pytest tests/unit/agents/bed_management/ --cov=app/agents/bed_management")
        print("  3. Update task_006 status to Complete")
        print("  4. Create implementation summary")
    else:
        print("\nNext steps:")
        print("  1. Fix the critical errors listed above")
        print("  2. Re-run this validation script")
        print("  3. Ensure 100% pass rate before running pytest")

    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
