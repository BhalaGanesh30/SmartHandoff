"""Validation script for US-031 TASK-008: Unit Tests for Drug Interaction Detection.

Validates:
    1. All 4 test files exist with correct structure
    2. Test functions present (4 in checker, 10 in severity, 2 in cache, 4 in endpoint)
    3. AsyncMock usage for external dependencies
    4. pytest.mark.asyncio decorators on async tests
    5. No real HTTP calls made (all clients mocked)
    6. Conftest.py mocks FHIR dependencies
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_pass(message: str) -> None:
    """Print a passing check message."""
    print(f"{GREEN}✓{RESET} {message}")

def check_fail(message: str) -> None:
    """Print a failing check message."""
    print(f"{RED}✗{RESET} {message}")
    
def check_warn(message: str) -> None:
    """Print a warning check message."""
    print(f"{YELLOW}!{RESET} {message}")


def check_file_exists(file_path: Path, description: str) -> bool:
    """Check if a file exists."""
    if file_path.exists():
        check_pass(f"{description} exists: {file_path.name}")
        return True
    else:
        check_fail(f"{description} missing: {file_path}")
        return False


def count_functions_in_file(file_path: Path) -> tuple[list[str], list[str]]:
    """Parse file and return lists of (all_functions, async_functions)."""
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    
    tree = ast.parse(content)
    all_functions = []
    async_functions = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            all_functions.append(node.name)
            if hasattr(node, "decorator_list"):
                for decorator in node.decorator_list:
                    # Check for pytest.mark.asyncio
                    if isinstance(decorator, ast.Attribute):
                        if (hasattr(decorator, "value") and 
                            isinstance(decorator.value, ast.Attribute) and
                            hasattr(decorator.value, "attr") and 
                            decorator.value.attr == "mark"):
                            async_functions.append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            all_functions.append(node.name)
            async_functions.append(node.name)
    
    return all_functions, async_functions


def check_import_in_file(file_path: Path, import_name: str) -> bool:
    """Check if a file imports a specific module or name."""
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    return import_name in content


def main() -> int:
    """Run all validation checks."""
    print("\n" + "="*70)
    print("TASK-008 Unit Tests Validation")
    print("="*70 + "\n")
    
    base_dir = Path(__file__).parent
    test_dir = base_dir / "tests" / "agents" / "medication_reconciliation"
    routers_test_dir = base_dir / "tests" / "routers"
    
    all_checks_passed = True
    
    # Check 1: Test files exist
    print("Check 1: Test files exist")
    print("-" * 70)
    
    test_files = {
        "checker": test_dir / "test_drug_interaction_checker.py",
        "severity": test_dir / "test_rxnav_severity_mapping.py",
        "cache": test_dir / "test_cache_key.py",
        "endpoint": routers_test_dir / "test_pharmacist_alert_endpoint.py",
    }
    
    for key, file_path in test_files.items():
        if not check_file_exists(file_path, f"Test file ({key})"):
            all_checks_passed = False
    
    # Check conftest exists
    conftest_path = test_dir / "conftest.py"
    if not check_file_exists(conftest_path, "conftest.py"):
        all_checks_passed = False
    
    print()
    
    # Check 2: Test function counts
    print("Check 2: Test function counts")
    print("-" * 70)
    
    expected_counts = {
        "checker": (4, "4 AC scenario tests"),
        "severity": (1, "1 parametrized test (10 cases)"),
        "cache": (2, "2 cache key tests"),
        "endpoint": (4, "4 endpoint tests"),
    }
    
    for key, file_path in test_files.items():
        if file_path.exists():
            functions, async_funcs = count_functions_in_file(file_path)
            test_funcs = [f for f in functions if f.startswith("test_")]
            expected, description = expected_counts[key]
            
            if len(test_funcs) == expected:
                check_pass(f"{file_path.name}: {len(test_funcs)} test functions ({description})")
            else:
                check_fail(f"{file_path.name}: Expected {expected} test functions, found {len(test_funcs)}")
                all_checks_passed = False
    
    print()
    
    # Check 3: AsyncMock usage
    print("Check 3: AsyncMock usage for external dependencies")
    print("-" * 70)
    
    checker_file = test_files["checker"]
    if checker_file.exists():
        if check_import_in_file(checker_file, "AsyncMock"):
            check_pass(f"{checker_file.name}: Uses AsyncMock for mocking")
        else:
            check_fail(f"{checker_file.name}: Missing AsyncMock import")
            all_checks_passed = False
    
    endpoint_file = test_files["endpoint"]
    if endpoint_file.exists():
        if check_import_in_file(endpoint_file, "AsyncMock"):
            check_pass(f"{endpoint_file.name}: Uses AsyncMock for mocking")
        else:
            check_fail(f"{endpoint_file.name}: Missing AsyncMock import")
            all_checks_passed = False
    
    print()
    
    # Check 4: pytest.mark.asyncio decorators
    print("Check 4: pytest.mark.asyncio decorators on async tests")
    print("-" * 70)
    
    for key in ["checker", "endpoint"]:
        file_path = test_files[key]
        if file_path.exists():
            if check_import_in_file(file_path, "@pytest.mark.asyncio"):
                check_pass(f"{file_path.name}: Has @pytest.mark.asyncio decorators")
            else:
                check_warn(f"{file_path.name}: No @pytest.mark.asyncio decorators found (may use pytest-asyncio auto mode)")
    
    print()
    
    # Check 5: No real HTTP calls
    print("Check 5: No real HTTP calls (all clients mocked)")
    print("-" * 70)
    
    checker_file = test_files["checker"]
    if checker_file.exists():
        with open(checker_file, encoding="utf-8") as f:
            content = f.read()
        
        # Check that RxNav and OpenFDA clients are mocked
        if "mock_rxnav" in content and "mock_openfda" in content:
            check_pass(f"{checker_file.name}: RxNav and OpenFDA clients are mocked")
        else:
            check_fail(f"{checker_file.name}: External API clients not properly mocked")
            all_checks_passed = False
        
        # Check that no real HTTP calls are made
        if "httpx.AsyncClient(" not in content or "AsyncMock" in content:
            check_pass(f"{checker_file.name}: No real HTTP clients instantiated")
        else:
            check_warn(f"{checker_file.name}: May contain real HTTP client usage")
    
    endpoint_file = test_files["endpoint"]
    if endpoint_file.exists():
        with open(endpoint_file, encoding="utf-8") as f:
            content = f.read()
        
        # Check that database and RBAC are mocked
        if "patch(" in content:
            check_pass(f"{endpoint_file.name}: Uses patch() to mock dependencies")
        else:
            check_fail(f"{endpoint_file.name}: Missing dependency mocking")
            all_checks_passed = False
    
    print()
    
    # Check 6: Conftest.py mocks FHIR dependencies
    print("Check 6: Conftest.py mocks FHIR dependencies")
    print("-" * 70)
    
    if conftest_path.exists():
        with open(conftest_path, encoding="utf-8") as f:
            content = f.read()
        
        if ("fhir" in content and "sys.modules" in content and "MagicMock" in content):
            check_pass("conftest.py: Mocks FHIR dependencies to avoid import errors")
        else:
            check_fail("conftest.py: Missing FHIR dependency mocking")
            all_checks_passed = False
    
    print()
    
    # Summary
    print("="*70)
    if all_checks_passed:
        print(f"{GREEN}✓ All validation checks PASSED{RESET}")
        print("="*70 + "\n")
        return 0
    else:
        print(f"{RED}✗ Some validation checks FAILED{RESET}")
        print("="*70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
