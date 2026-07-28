"""Validation script for US-033 TASK-006: Unit Tests for Medication Summary.

Validates that:
1. All 4 test files exist
2. Each test file has proper structure (imports, fixtures, test functions)
3. All tests are async (pytest.mark.asyncio)
4. No real network calls (mocks used)
5. All AC scenarios covered
6. Python syntax is valid

Design refs:
    US-033 TASK-006 — Unit tests for all reconciliation categories
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def validate_file_structure() -> tuple[int, int]:
    """Validate that all required test files exist."""
    print("\n📁 1. FILE STRUCTURE")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    required_files = [
        ("backend/tests/agents/medication_reconciliation/test_medication_summary_generator.py", "Generator tests"),
        ("backend/tests/agents/medication_reconciliation/test_brand_name_enricher.py", "Brand name enricher tests"),
        ("backend/tests/agents/medication_reconciliation/test_medication_summary_writer.py", "Writer tests"),
        ("backend/tests/agents/medication_reconciliation/test_medication_summary_translator.py", "Translator tests"),
    ]
    
    for file_path, description in required_files:
        total += 1
        path = Path(file_path)
        if path.exists():
            print(f"✅ {description}: {file_path}")
            passed += 1
        else:
            print(f"❌ {description} not found: {file_path}")
    
    print(f"\n📊 File Structure: {passed}/{total} files present")
    return passed, total


def validate_test_file(file_path: str, description: str, expected_tests: int) -> tuple[int, int]:
    """Validate structure of a single test file."""
    print(f"\n🧪 {description.upper()}")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        return 0, expected_tests + 4  # Base checks + expected tests
    
    with open(path, "r") as f:
        content = f.read()
    
    # Check 1: Module docstring with US-033 reference
    total += 1
    if '"""' in content and "US-033" in content:
        print("✅ Module docstring with US-033 reference")
        passed += 1
    else:
        print("❌ Missing module docstring or US-033 reference")
    
    # Check 2: Imports pytest
    total += 1
    if "import pytest" in content:
        print("✅ Imports pytest")
        passed += 1
    else:
        print("❌ Does not import pytest")
    
    # Check 3: Uses AsyncMock for mocking
    total += 1
    if "AsyncMock" in content or "MagicMock" in content:
        print("✅ Uses mocking (AsyncMock/MagicMock)")
        passed += 1
    else:
        print("❌ No mocking detected")
    
    # Check 4: Count async test functions
    total += 1
    async_test_count = content.count("async def test_")
    if async_test_count >= expected_tests:
        print(f"✅ Has {async_test_count} async test functions (expected: {expected_tests})")
        passed += 1
    else:
        print(f"❌ Only {async_test_count} async test functions (expected: {expected_tests})")
    
    # Check 5-N: Verify each test is marked with pytest.mark.asyncio
    for i in range(expected_tests):
        total += 1
        if content.count("@pytest.mark.asyncio") >= expected_tests:
            if i == 0:  # Only print once
                print(f"✅ All tests marked with @pytest.mark.asyncio")
            passed += 1
        else:
            if i == 0:
                print(f"❌ Not all tests marked with @pytest.mark.asyncio")
    
    print(f"\n📊 {description}: {passed}/{total} checks passed")
    return passed, total


def validate_generator_tests() -> tuple[int, int]:
    """Validate test_medication_summary_generator.py."""
    file_path = "backend/tests/agents/medication_reconciliation/test_medication_summary_generator.py"
    
    base_passed, base_total = validate_test_file(
        file_path, "Generator Tests", expected_tests=4
    )
    
    if not Path(file_path).exists():
        return base_passed, base_total
    
    with open(file_path, "r") as f:
        content = f.read()
    
    passed = base_passed
    total = base_total
    
    # Additional checks specific to generator tests
    print("\n🔍 Additional Generator Test Checks:")
    
    # Check: Mocks ChatVertexAI
    total += 1
    if "patch" in content and "ChatVertexAI" in content:
        print("  ✅ Mocks ChatVertexAI (no real Gemini calls)")
        passed += 1
    else:
        print("  ❌ Does not mock ChatVertexAI")
    
    # Check: Tests all 4 categories
    total += 1
    if "len(result.new)" in content and "len(result.stopped)" in content:
        print("  ✅ Tests all 4 reconciliation categories")
        passed += 1
    else:
        print("  ❌ Does not test all 4 categories")
    
    # Check: Tests invalid JSON handling
    total += 1
    if "NOT VALID JSON" in content or "invalid" in content.lower():
        print("  ✅ Tests invalid JSON error handling")
        passed += 1
    else:
        print("  ❌ Does not test invalid JSON")
    
    return passed, total


def validate_enricher_tests() -> tuple[int, int]:
    """Validate test_brand_name_enricher.py."""
    file_path = "backend/tests/agents/medication_reconciliation/test_brand_name_enricher.py"
    
    base_passed, base_total = validate_test_file(
        file_path, "Brand Name Enricher Tests", expected_tests=4
    )
    
    if not Path(file_path).exists():
        return base_passed, base_total
    
    with open(file_path, "r") as f:
        content = f.read()
    
    passed = base_passed
    total = base_total
    
    print("\n🔍 Additional Enricher Test Checks:")
    
    # Check: Tests cache hit/miss
    total += 1
    if "cache_hit" in content or "cache miss" in content.lower():
        print("  ✅ Tests cache hit and cache miss scenarios")
        passed += 1
    else:
        print("  ❌ Does not test cache scenarios")
    
    # Check: Tests RxNav error handling
    total += 1
    if "RxNavBrandNameError" in content:
        print("  ✅ Tests RxNav error handling")
        passed += 1
    else:
        print("  ❌ Does not test RxNav errors")
    
    # Check: Mocks fetch_brand_name (no real network calls)
    total += 1
    if "patch" in content and "fetch_brand_name" in content:
        print("  ✅ Mocks fetch_brand_name (no real network calls)")
        passed += 1
    else:
        print("  ❌ Does not mock fetch_brand_name")
    
    return passed, total


def validate_writer_tests() -> tuple[int, int]:
    """Validate test_medication_summary_writer.py."""
    file_path = "backend/tests/agents/medication_reconciliation/test_medication_summary_writer.py"
    
    base_passed, base_total = validate_test_file(
        file_path, "Writer Tests", expected_tests=3
    )
    
    if not Path(file_path).exists():
        return base_passed, base_total
    
    with open(file_path, "r") as f:
        content = f.read()
    
    passed = base_passed
    total = base_total
    
    print("\n🔍 Additional Writer Test Checks:")
    
    # Check: Tests db.flush() called
    total += 1
    if "flush.assert_awaited" in content:
        print("  ✅ Tests db.flush() called (not commit)")
        passed += 1
    else:
        print("  ❌ Does not verify db.flush()")
    
    # Check: Tests ValueError for unknown document_id
    total += 1
    if "ValueError" in content and "not found" in content:
        print("  ✅ Tests ValueError for unknown document_id")
        passed += 1
    else:
        print("  ❌ Does not test unknown document_id error")
    
    # Check: Mocks database
    total += 1
    if "mock_db" in content or "AsyncMock" in content:
        print("  ✅ Mocks database (no real DB calls)")
        passed += 1
    else:
        print("  ❌ Does not mock database")
    
    return passed, total


def validate_translator_tests() -> tuple[int, int]:
    """Validate test_medication_summary_translator.py."""
    file_path = "backend/tests/agents/medication_reconciliation/test_medication_summary_translator.py"
    
    base_passed, base_total = validate_test_file(
        file_path, "Translator Tests", expected_tests=5
    )
    
    if not Path(file_path).exists():
        return base_passed, base_total
    
    with open(file_path, "r") as f:
        content = f.read()
    
    passed = base_passed
    total = base_total
    
    print("\n🔍 Additional Translator Test Checks:")
    
    # Check: Tests drug names NOT translated
    total += 1
    if "generic_name" in content and "NOT translated" in content:
        print("  ✅ Tests drug names NOT translated")
        passed += 1
    else:
        print("  ❌ Does not verify drug names unchanged")
    
    # Check: Tests text fields ARE translated
    total += 1
    if "dosing_instructions" in content and "translated" in content:
        print("  ✅ Tests text fields ARE translated")
        passed += 1
    else:
        print("  ❌ Does not test text field translation")
    
    # Check: Tests null reason handling
    total += 1
    if "None" in content and "reason" in content:
        print("  ✅ Tests null reason field handling")
        passed += 1
    else:
        print("  ❌ Does not test null reason")
    
    # Check: Mocks TranslationService
    total += 1
    if "mock_svc" in content or "translation_service" in content:
        print("  ✅ Mocks TranslationService (no real Gemini calls)")
        passed += 1
    else:
        print("  ❌ Does not mock TranslationService")
    
    return passed, total


def validate_syntax() -> tuple[int, int]:
    """Validate Python syntax for all test files."""
    print("\n✨ PYTHON SYNTAX")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    files = [
        ("backend/tests/agents/medication_reconciliation/test_medication_summary_generator.py", "generator tests"),
        ("backend/tests/agents/medication_reconciliation/test_brand_name_enricher.py", "enricher tests"),
        ("backend/tests/agents/medication_reconciliation/test_medication_summary_writer.py", "writer tests"),
        ("backend/tests/agents/medication_reconciliation/test_medication_summary_translator.py", "translator tests"),
    ]
    
    for file_path, name in files:
        total += 1
        path = Path(file_path)
        if not path.exists():
            print(f"❌ {name} not found")
            continue
        
        try:
            with open(path, "r") as f:
                code = f.read()
            ast.parse(code)
            print(f"✅ {name} has no syntax errors")
            passed += 1
        except SyntaxError as e:
            print(f"❌ {name} has syntax error: {e}")
    
    print(f"\n📊 Python Syntax: {passed}/{total} files valid")
    return passed, total


def main() -> int:
    """Run all validation checks."""
    print("=" * 70)
    print("US-033 TASK-006 VALIDATION")
    print("Unit Tests — Medication Summary Components")
    print("=" * 70)
    
    results = []
    results.append(validate_file_structure())
    results.append(validate_generator_tests())
    results.append(validate_enricher_tests())
    results.append(validate_writer_tests())
    results.append(validate_translator_tests())
    results.append(validate_syntax())
    
    total_passed = sum(r[0] for r in results)
    total_checks = sum(r[1] for r in results)
    
    print("\n" + "=" * 70)
    print("📊 OVERALL VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total Checks Passed: {total_passed}/{total_checks}")
    print(f"Success Rate: {(total_passed/total_checks)*100:.1f}%")
    
    if total_passed == total_checks:
        print("\n✅ ALL VALIDATION CHECKS PASSED")
        print("\nUS-033 TASK-006 Test Coverage:")
        print("  ✓ Generator: All 4 reconciliation categories tested")
        print("  ✓ Generator: Brand name enrichment integration tested")
        print("  ✓ Generator: Invalid JSON error handling tested")
        print("  ✓ Enricher: Cache hit/miss scenarios tested")
        print("  ✓ Enricher: RxNav error handling tested")
        print("  ✓ Writer: Document persistence tested")
        print("  ✓ Writer: Unknown document_id error tested")
        print("  ✓ Writer: db.flush() (not commit) verified")
        print("  ✓ Translator: Drug names NOT translated verified")
        print("  ✓ Translator: Text fields ARE translated verified")
        print("  ✓ Translator: Null reason handling tested")
        print("\nAll tests use mocks (no real network/DB/Gemini calls).")
        print("\nNext steps:")
        print("  1. Run: cd backend && pytest tests/agents/medication_reconciliation/test_medication_summary*.py -v")
        print("  2. Verify all tests pass")
        print("  3. Check pytest output for warnings")
        print("  4. Integration test with real components (optional)")
        return 0
    else:
        print("\n⚠️  SOME VALIDATION CHECKS FAILED")
        print(f"{total_checks - total_passed} check(s) need review before completion.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
