"""
Validation script for TASK-007: Performance Test Implementation

Validates:
1. All required files exist
2. pytest.ini has performance marker
3. Performance test has correct markers and structure
4. Encounter factory generates correct data
5. Import statements work correctly
"""
import ast
import pathlib
import sys


def validate_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists."""
    p = pathlib.Path(filepath)
    exists = p.exists()
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {filepath}")
    return exists


def validate_pytest_marker() -> bool:
    """Validate pytest.ini contains performance marker."""
    print("\n" + "=" * 70)
    print("Validating pytest.ini marker configuration")
    print("=" * 70)
    
    pytest_ini = pathlib.Path("backend/pytest.ini")
    content = pytest_ini.read_text()
    
    has_marker = "performance:" in content
    status = "✓" if has_marker else "✗"
    print(f"{status} pytest.ini contains 'performance:' marker")
    
    has_description = "marks tests as performance tests" in content
    status = "✓" if has_description else "✗"
    print(f"{status} Performance marker has description")
    
    return has_marker and has_description


def validate_test_structure() -> bool:
    """Validate the performance test has correct structure."""
    print("\n" + "=" * 70)
    print("Validating test_discharge_summary_p95.py structure")
    print("=" * 70)
    
    test_file = pathlib.Path("backend/tests/performance/test_discharge_summary_p95.py")
    content = test_file.read_text()
    
    # Check for required imports
    checks = [
        ("import asyncio", "asyncio import"),
        ("import statistics", "statistics import"),
        ("import time", "time import"),
        ("import pytest", "pytest import"),
        ("from agents.documentation.agent import DocumentationAgent", "DocumentationAgent import"),
        ("from tests.performance.fixtures.encounter_factory import build_test_encounters", "encounter_factory import"),
        ("@pytest.mark.performance", "performance marker"),
        ("@pytest.mark.asyncio", "asyncio marker"),
        ("@pytest.mark.timeout(600)", "timeout marker"),
        ("async def test_p95_discharge_summary_latency", "test function"),
        ("P95_LATENCY_THRESHOLD_MS = 30_000", "threshold constant"),
        ("TOTAL_TEST_CASES = 100", "test case count"),
        ("BATCH_SIZE = 10", "batch size constant"),
        ("def _percentile", "percentile function"),
        ("assert p95_ms < P95_LATENCY_THRESHOLD_MS", "p95 assertion"),
    ]
    
    all_passed = True
    for check_str, description in checks:
        exists = check_str in content
        status = "✓" if exists else "✗"
        print(f"{status} {description}: {check_str[:50]}...")
        all_passed = all_passed and exists
    
    return all_passed


def validate_encounter_factory() -> bool:
    """Validate encounter factory structure."""
    print("\n" + "=" * 70)
    print("Validating encounter_factory.py")
    print("=" * 70)
    
    factory_file = pathlib.Path("backend/tests/performance/fixtures/encounter_factory.py")
    content = factory_file.read_text()
    
    checks = [
        ("def build_test_encounters", "build_test_encounters function"),
        ("from agents.documentation.fhir_fetcher import", "fhir_fetcher imports"),
        ("DiagnosisContext", "DiagnosisContext import"),
        ("MedicationContext", "MedicationContext import"),
        ("EncounterContext", "EncounterContext import"),
        ("_SAMPLE_DIAGNOSES", "sample diagnoses data"),
        ("_SAMPLE_MEDICATIONS", "sample medications data"),
        ("random.Random(seed)", "deterministic randomness"),
        ("rng.randint(1, 8)", "diagnosis count variation"),
        ("rng.randint(1, 12)", "medication count variation"),
    ]
    
    all_passed = True
    for check_str, description in checks:
        exists = check_str in content
        status = "✓" if exists else "✗"
        print(f"{status} {description}")
        all_passed = all_passed and exists
    
    return all_passed


def validate_imports() -> bool:
    """Validate all imports work correctly."""
    print("\n" + "=" * 70)
    print("Validating Python imports")
    print("=" * 70)
    
    try:
        # Add backend to path
        backend_path = pathlib.Path("backend").resolve()
        if str(backend_path) not in sys.path:
            sys.path.insert(0, str(backend_path))
        
        # Test encounter factory import
        from tests.performance.fixtures.encounter_factory import build_test_encounters
        print("✓ encounter_factory.build_test_encounters import successful")
        
        # Test factory functionality
        encounters = build_test_encounters(count=5, seed=42)
        print(f"✓ Generated {len(encounters)} test encounters")
        
        # Validate encounter structure
        enc = encounters[0]
        assert hasattr(enc, 'encounter_id'), "Missing encounter_id"
        assert hasattr(enc, 'diagnoses'), "Missing diagnoses"
        assert hasattr(enc, 'medications'), "Missing medications"
        assert len(enc.diagnoses) >= 1, "No diagnoses generated"
        assert len(enc.medications) >= 1, "No medications generated"
        print(f"✓ Encounter structure valid (diagnoses: {len(enc.diagnoses)}, meds: {len(enc.medications)})")
        
        return True
        
    except Exception as e:
        print(f"✗ Import validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation checks."""
    print("=" * 70)
    print("TASK-007 Implementation Validation")
    print("=" * 70)
    
    # File existence checks
    print("\nFile Existence Checks:")
    print("-" * 70)
    
    files = [
        ("backend/tests/performance/__init__.py", "Performance tests module init"),
        ("backend/tests/performance/fixtures/__init__.py", "Fixtures module init"),
        ("backend/tests/performance/fixtures/encounter_factory.py", "Encounter factory"),
        ("backend/tests/performance/test_discharge_summary_p95.py", "Performance test"),
        ("backend/pytest.ini", "pytest configuration"),
        ("US-025-TASK-007-IMPLEMENTATION-SUMMARY.md", "Implementation summary"),
    ]
    
    files_exist = all(validate_file_exists(f, desc) for f, desc in files)
    
    # Validation checks
    marker_valid = validate_pytest_marker()
    test_valid = validate_test_structure()
    factory_valid = validate_encounter_factory()
    imports_valid = validate_imports()
    
    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    results = [
        ("File existence", files_exist),
        ("pytest.ini marker", marker_valid),
        ("Test structure", test_valid),
        ("Encounter factory", factory_valid),
        ("Python imports", imports_valid),
    ]
    
    all_passed = all(passed for _, passed in results)
    
    for check_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check_name}")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL VALIDATION CHECKS PASSED")
        print("=" * 70)
        print("\nTASK-007 Implementation: COMPLETE")
        print("\nNext Steps:")
        print("  1. Configure staging environment with Vertex AI credentials")
        print("  2. Run: pytest tests/performance/test_discharge_summary_p95.py --env=staging -v")
        print("  3. Integrate into CI/CD staging gate pipeline")
        return 0
    else:
        print("✗ SOME VALIDATION CHECKS FAILED")
        print("=" * 70)
        print("\nPlease review the failed checks above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
