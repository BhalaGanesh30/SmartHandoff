"""
Validation script for US-027 TASK-007: Unit Tests for Patient Instructions.

Validates all 4 test files created for FK scoring, language fallback, and
back-translation quality check.
"""
import pathlib
import subprocess
import sys


def main() -> int:
    """Run validation checks and report results."""
    print()
    print("=" * 80)
    print("US-027 TASK-007 VALIDATION: Unit Tests for Patient Instructions")
    print("=" * 80)
    print()

    # Check 1: Verify test files exist
    print("Check 1: Test files exist")
    print("-" * 80)
    test_files = [
        "backend/tests/agents/documentation/test_reading_level_scorer.py",
        "backend/tests/agents/documentation/test_language_utils.py",
        "backend/tests/agents/documentation/test_patient_instructions_generator.py",
        "backend/tests/agents/documentation/test_patient_instructions_translator.py",
    ]

    all_exist = True
    for fpath in test_files:
        p = pathlib.Path(fpath)
        exists = p.exists()
        size = p.stat().st_size if exists else 0
        status = "✓" if exists else "✗"
        print(f"{status} {fpath:<75} {size:>6} bytes")
        if not exists:
            all_exist = False

    if not all_exist:
        print()
        print("✗ VALIDATION FAILED: Not all test files exist")
        return 1

    print()
    print("✓ All 4 test files exist")
    print()

    # Check 2: Run pytest
    print("Check 2: Run pytest on all test files")
    print("-" * 80)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/agents/documentation/test_reading_level_scorer.py",
            "tests/agents/documentation/test_language_utils.py",
            "tests/agents/documentation/test_patient_instructions_generator.py",
            "tests/agents/documentation/test_patient_instructions_translator.py",
            "-v",
            "--tb=short",
        ],
        cwd="backend",
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        print()
        print("✗ VALIDATION FAILED: pytest returned non-zero exit code")
        return 1

    # Parse test results
    output_lines = result.stdout.split("\n")
    passed_line = [line for line in output_lines if "passed" in line]
    if passed_line:
        print(passed_line[-1])

    print()
    print("✓ All tests passed")
    print()

    # Check 3: Verify test count
    print("Check 3: Verify expected test count")
    print("-" * 80)
    expected_tests = {
        "test_reading_level_scorer.py": 6,
        "test_language_utils.py": 9,
        "test_patient_instructions_generator.py": 3,
        "test_patient_instructions_translator.py": 5,
    }

    for fname, expected_count in expected_tests.items():
        actual_count = sum(
            1
            for line in output_lines
            if fname in line and "PASSED" in line
        )
        status = "✓" if actual_count == expected_count else "✗"
        print(
            f"{status} {fname:<50} {actual_count:>2}/{expected_count} tests"
        )

    total_expected = sum(expected_tests.values())
    total_actual = sum(
        1 for line in output_lines if "PASSED" in line
    )

    print()
    print(f"Total: {total_actual}/{total_expected} tests passed")
    print()

    if total_actual != total_expected:
        print("✗ VALIDATION FAILED: Test count mismatch")
        return 1

    # Check 4: Verify implementation summary exists
    print("Check 4: Implementation summary document")
    print("-" * 80)
    summary_path = pathlib.Path("US-027-TASK-007-IMPLEMENTATION-SUMMARY.md")
    if summary_path.exists():
        summary_size = summary_path.stat().st_size
        print(f"✓ {summary_path} ({summary_size:,} bytes)")
    else:
        print(f"✗ {summary_path} NOT FOUND")
        return 1

    print()
    print("=" * 80)
    print("✓ ALL VALIDATION CHECKS PASSED")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  • 4 test files created")
    print(f"  • {total_actual} unit tests passing")
    print(f"  • 0 test failures")
    print(f"  • Implementation summary documented")
    print()
    print("US-027 TASK-007: COMPLETE ✓")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
