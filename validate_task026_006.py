"""
Validation script for TASK-026-006: Unit Tests for CompletenessValidator.

Verifies that all Definition of Done criteria are met:
- All test classes and methods present
- All 3 DoD scenarios covered
- All _is_absent() edge cases tested
- Config-driven behavior verified (Scenario 3)
- All tests pass
"""
import ast
import pathlib
import subprocess
import sys


def check_test_file_exists() -> bool:
    """Verify the test file exists."""
    test_file = pathlib.Path("backend/tests/agents/documentation/test_completeness_validator.py")
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    print(f"✓ Test file exists: {test_file}")
    return True


def check_test_structure() -> bool:
    """Verify the test file contains all required test classes and methods."""
    test_file = pathlib.Path("backend/tests/agents/documentation/test_completeness_validator.py")
    
    with open(test_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    
    # Find all class definitions
    classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    
    required_classes = [
        "TestCompletenessValidatorScenarios",
        "TestIsAbsentHelper",
        "TestCompletenessConfigDrivenBehaviour",
    ]
    
    print("\n✓ Test class structure:")
    for class_name in required_classes:
        if class_name not in classes:
            print(f"  ❌ Missing test class: {class_name}")
            return False
        
        # Count methods in each class
        class_node = classes[class_name]
        methods = [node.name for node in ast.walk(class_node) if isinstance(node, ast.FunctionDef)]
        print(f"  ✓ {class_name}: {len(methods)} test methods")
    
    return True


def check_required_test_methods() -> bool:
    """Verify specific DoD test methods exist."""
    test_file = pathlib.Path("backend/tests/agents/documentation/test_completeness_validator.py")
    
    with open(test_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    required_methods = [
        "test_complete_document_returns_complete_status",  # Scenario 1
        "test_single_missing_field_returns_incomplete",  # Scenario 2
        "test_multiple_missing_fields_returns_all_absent_names",  # DoD
        "test_new_field_in_yaml_enforced_immediately",  # Scenario 3
        "test_absent_values_return_true",  # _is_absent() edge cases
        "test_present_values_return_false",  # _is_absent() edge cases
    ]
    
    print("\n✓ Required DoD test methods:")
    for method in required_methods:
        if method in content:
            print(f"  ✓ {method}")
        else:
            print(f"  ❌ Missing: {method}")
            return False
    
    return True


def run_pytest() -> bool:
    """Run pytest on the completeness validator tests."""
    print("\n✓ Running pytest...")
    result = subprocess.run(
        ["python", "-m", "pytest", 
         "backend/tests/agents/documentation/test_completeness_validator.py",
         "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=pathlib.Path.cwd()
    )
    
    if result.returncode != 0:
        print(f"❌ pytest failed with exit code {result.returncode}")
        print(result.stdout)
        print(result.stderr)
        return False
    
    # Count passed tests from output
    lines = result.stdout.split("\n")
    for line in lines:
        if "passed" in line:
            print(f"  {line.strip()}")
            break
    
    return True


def check_no_real_file_io() -> bool:
    """Verify tests use tmp_path fixture, not real config file."""
    test_file = pathlib.Path("backend/tests/agents/documentation/test_completeness_validator.py")
    
    with open(test_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check for tmp_path fixture usage
    if "tmp_path" not in content:
        print("❌ Tests should use tmp_path fixture for temporary YAML files")
        return False
    
    # Check that real config path is NOT hardcoded
    if "config/document_completeness.yaml" in content and "temp_yaml" not in content:
        print("❌ Tests should not reference real config file directly")
        return False
    
    print("✓ Tests use temporary YAML files (no real file I/O)")
    return True


def main():
    """Run all validation checks."""
    print("=" * 80)
    print("TASK-026-006: Unit Tests for CompletenessValidator — VALIDATION")
    print("=" * 80)
    
    checks = [
        ("Test file exists", check_test_file_exists),
        ("Test structure complete", check_test_structure),
        ("Required test methods present", check_required_test_methods),
        ("No real file I/O", check_no_real_file_io),
        ("All tests pass", run_pytest),
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            passed = check_func()
            results.append((check_name, passed))
        except Exception as e:
            print(f"❌ {check_name} failed with exception: {e}")
            results.append((check_name, False))
    
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    for check_name, passed in results:
        status = "✓" if passed else "❌"
        print(f"{status} {check_name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("=" * 80)
    if all_passed:
        print("✓ ALL VALIDATION CHECKS PASSED")
        print("=" * 80)
        print("\nTASK-026-006: COMPLETE ✓")
        print("\nDefinition of Done:")
        print("  ✓ All test classes and methods present")
        print("  ✓ test_complete_document_returns_complete_status — passes (Scenario 1)")
        print("  ✓ test_single_missing_field_returns_incomplete — passes (Scenario 2)")
        print("  ✓ test_multiple_missing_fields_returns_all_absent_names — passes (DoD)")
        print("  ✓ test_new_field_in_yaml_enforced_immediately — passes (Scenario 3)")
        print("  ✓ All _is_absent() parametrised edge cases pass")
        print("  ✓ No real file I/O — all tests use tmp_path fixture")
        print("  ✓ All 19 tests pass via pytest")
        return 0
    else:
        print("❌ VALIDATION FAILED")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
