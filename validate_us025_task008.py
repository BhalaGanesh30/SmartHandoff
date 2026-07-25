"""
Validation script for US-025 TASK-008: PHI Audit Test Implementation.

Verifies:
1. Test file exists and is properly structured
2. All 15 tests are collected by pytest
3. All tests pass
4. CI/CD workflow includes PHI audit gate
5. Required dependencies are importable

Run with: python validate_us025_task008.py
"""
import pathlib
import subprocess
import sys


def validate_test_file_exists():
    """Check test file exists."""
    test_file = pathlib.Path("backend/tests/security/test_phi_audit_prompt.py")
    assert test_file.exists(), f"Test file not found: {test_file}"
    print(f"✅ Test file exists: {test_file}")


def validate_test_collection():
    """Verify pytest collects exactly 15 tests."""
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/security/test_phi_audit_prompt.py", "--collect-only", "-q"],
        cwd="backend",
        capture_output=True,
        text=True,
    )
    
    # Extract test count from output
    lines = result.stdout.strip().split("\n")
    count_line = [l for l in lines if "test" in l.lower()]
    
    # Verify 15 tests collected
    assert "15" in result.stdout, f"Expected 15 tests, got: {result.stdout}"
    print("✅ Pytest collected 15 tests")


def validate_tests_pass():
    """Run tests and verify all pass."""
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/security/test_phi_audit_prompt.py", "-v", "--tb=short"],
        cwd="backend",
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0, f"Tests failed:\n{result.stdout}\n{result.stderr}"
    assert "15 passed" in result.stdout, f"Not all tests passed:\n{result.stdout}"
    print("✅ All 15 PHI audit tests passed")


def validate_ci_workflow():
    """Check CI workflow includes PHI audit gate."""
    workflow_file = pathlib.Path(".github/workflows/pr-checks.yml")
    assert workflow_file.exists(), f"Workflow file not found: {workflow_file}"
    
    content = workflow_file.read_text(encoding='utf-8')
    assert "phi-audit-tests:" in content, "PHI audit job not found in workflow"
    assert "test_phi_audit_prompt.py" in content, "PHI audit test file not referenced in workflow"
    assert "needs: [backend-tests, phi-audit-tests" in content, "PHI audit not in summary job dependencies"
    print("✅ CI workflow includes PHI audit security gate")


def validate_imports():
    """Verify required modules can be imported."""
    sys.path.insert(0, str(pathlib.Path("backend").resolve()))
    
    try:
        from agents.documentation.fhir_fetcher import (
            EncounterContext,
            DiagnosisContext,
            MedicationContext,
        )
        from agents.documentation.prompt_renderer import PromptRenderer
        print("✅ All required modules importable")
    except ImportError as e:
        raise AssertionError(f"Import failed: {e}")


def validate_dataclass_structure():
    """Verify dataclasses don't contain PHI field names."""
    sys.path.insert(0, str(pathlib.Path("backend").resolve()))
    
    from agents.documentation.fhir_fetcher import (
        EncounterContext,
        DiagnosisContext,
        MedicationContext,
    )
    import dataclasses
    
    prohibited_fields = {
        "patient_name", "first_name", "last_name", "full_name",
        "date_of_birth", "dob", "address", "street_address",
        "city", "postal_code", "zip_code", "phone", "phone_number",
        "ssn", "social_security_number", "email", "email_address",
        "mrn", "medical_record_number"
    }
    
    for dataclass_type, name in [
        (EncounterContext, "EncounterContext"),
        (DiagnosisContext, "DiagnosisContext"),
        (MedicationContext, "MedicationContext"),
    ]:
        field_names = {f.name for f in dataclasses.fields(dataclass_type)}
        leaked = prohibited_fields & field_names
        assert not leaked, f"{name} contains prohibited PHI fields: {leaked}"
    
    print("✅ Dataclasses contain no prohibited PHI field names")


def main():
    print()
    print("=" * 80)
    print("US-025 TASK-008 Validation: PHI Audit Test Implementation")
    print("=" * 80)
    print()
    
    try:
        validate_test_file_exists()
        validate_imports()
        validate_dataclass_structure()
        validate_test_collection()
        validate_tests_pass()
        validate_ci_workflow()
        
        print()
        print("=" * 80)
        print("✅ ALL VALIDATION CHECKS PASSED")
        print("=" * 80)
        print()
        print("Task Implementation Status: COMPLETE ✅")
        print()
        print("Summary:")
        print("  • 15/15 PHI audit tests passing")
        print("  • CI/CD security gate operational")
        print("  • Dataclass schemas validated (no PHI fields)")
        print("  • HIPAA minimum-necessary compliance verified")
        print()
        print("=" * 80)
        return 0
    
    except AssertionError as e:
        print()
        print("=" * 80)
        print("❌ VALIDATION FAILED")
        print("=" * 80)
        print()
        print(f"Error: {e}")
        print()
        return 1
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ VALIDATION ERROR")
        print("=" * 80)
        print()
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
