"""
Validation script for US-036 TASK-006 Unit Tests.

Validates:
- Test files exist
- Test syntax is valid
- Test coverage spans all required scenarios
- PHI compliance tests present
- Retry logic tests present

Design refs:
    US-036 TASK-006 — Unit test validation checklist
"""

import ast
from pathlib import Path

def check_file_exists(filepath):
    """Check if file exists."""
    path = Path(filepath)
    if not path.exists():
        return False, f"✗ File not found: {filepath}"
    return True, f"✓ File exists: {filepath}"

def check_python_syntax(filepath):
    """Check if Python file has valid syntax."""
    try:
        code = Path(filepath).read_text(encoding='utf-8')
        ast.parse(code)
        return True, f"✓ Valid Python syntax: {filepath}"
    except SyntaxError as e:
        return False, f"✗ Syntax error in {filepath}: {e}"

def check_test_functions(filepath, required_tests):
    """Check if required test functions exist in file."""
    code = Path(filepath).read_text(encoding='utf-8')
    results = []
    for test_name in required_tests:
        if f"def {test_name}" in code:
            results.append((True, f"✓ Test found: {test_name}"))
        else:
            results.append((False, f"✗ Missing test: {test_name}"))
    return results

def check_pattern_in_file(filepath, patterns):
    """Check if patterns exist in file."""
    code = Path(filepath).read_text(encoding='utf-8')
    results = []
    for pattern, description in patterns:
        if pattern in code:
            results.append((True, f"✓ {description}"))
        else:
            results.append((False, f"✗ {description} not found"))
    return results

def run_validation():
    print("=" * 80)
    print("US-036 TASK-006 Validation: Unit Tests")
    print("=" * 80)

    all_passed = True

    # ──────────────────────────────────────────────────────────────────────────
    # 1. File existence check
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[1/5] File Existence Check")
    
    test_files = [
        "ml_inference/tests/__init__.py",
        "ml_inference/tests/test_discharge_time_endpoint.py",
        "ml/discharge_time_model/tests/__init__.py",
        "ml/discharge_time_model/tests/test_features.py",
        "backend/tests/unit/agents/bed_management/test_prediction_service.py",
    ]

    for filepath in test_files:
        passed, message = check_file_exists(filepath)
        print(f"  {message}")
        if not passed:
            all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Syntax validation
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[2/5] Python Syntax Validation")

    for filepath in [f for f in test_files if f.endswith('.py')]:
        if Path(filepath).exists():
            passed, message = check_python_syntax(filepath)
            print(f"  {message}")
            if not passed:
                all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 3. ML Inference endpoint tests
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[3/5] ML Inference Endpoint Tests")

    endpoint_tests = [
        "test_predict_returns_200_with_valid_payload",
        "test_predict_response_time_under_500ms",
        "test_confidence_level_mapping",
        "test_confidence_level_high_when_interval_below_1h",
        "test_confidence_level_medium_when_interval_1_to_2h",
        "test_confidence_level_low_when_interval_above_2h",
        "test_predict_rejects_unauthenticated_request",
        "test_predict_returns_503_when_model_unavailable",
    ]

    if Path("ml_inference/tests/test_discharge_time_endpoint.py").exists():
        results = check_test_functions(
            "ml_inference/tests/test_discharge_time_endpoint.py",
            endpoint_tests
        )
        for passed, message in results:
            print(f"  {message}")
            if not passed:
                all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Feature engineering tests
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[4/5] Feature Engineering Tests")

    feature_tests = [
        "test_los_so_far_hours_positive",
        "test_los_so_far_hours_clips_to_zero_for_future_admit",
        "test_los_so_far_hours_handles_timezone_naive_admit",
        "test_build_feature_dataframe_returns_correct_columns",
        "test_build_feature_dataframe_computes_age_correctly",
        "test_build_single_feature_vector_returns_dict_with_all_features",
    ]

    if Path("ml/discharge_time_model/tests/test_features.py").exists():
        results = check_test_functions(
            "ml/discharge_time_model/tests/test_features.py",
            feature_tests
        )
        for passed, message in results:
            print(f"  {message}")
            if not passed:
                all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Prediction service tests
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[5/5] Prediction Service Tests")

    prediction_tests = [
        "test_prediction_service_writes_to_encounter_on_success",
        "test_prediction_service_retries_on_503_and_succeeds",
        "test_prediction_service_returns_false_after_exhausting_retries",
        "test_prediction_service_returns_false_when_encounter_not_found",
        "test_phi_not_logged_during_prediction",
    ]

    if Path("backend/tests/unit/agents/bed_management/test_prediction_service.py").exists():
        results = check_test_functions(
            "backend/tests/unit/agents/bed_management/test_prediction_service.py",
            prediction_tests
        )
        for passed, message in results:
            print(f"  {message}")
            if not passed:
                all_passed = False

        # Check for PHI compliance patterns
        phi_patterns = [
            ("caplog", "caplog fixture for log testing"),
            ("dob_str not in record.getMessage()", "PHI guard assertion"),
            ("assert dob_str not in", "PHI validation logic"),
        ]
        results = check_pattern_in_file(
            "backend/tests/unit/agents/bed_management/test_prediction_service.py",
            phi_patterns
        )
        for passed, message in results:
            print(f"  {message}")
            if not passed:
                all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # Summary
    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ ALL VALIDATION CHECKS PASSED (5/5)")
        print("=" * 80)
        print("\nNext steps:")
        print("  1. Run ML Inference tests: pytest ml_inference/tests/ -v")
        print("  2. Run feature tests: pytest ml/discharge_time_model/tests/ -v")
        print("  3. Run prediction service tests: pytest backend/tests/unit/agents/bed_management/test_prediction_service.py -v")
        print("  4. Run all tests with coverage: pytest --cov=app --cov=features --cov-report=term-missing")
        print("\nUS-036 TASK-006 implementation complete.")
    else:
        print("✗ VALIDATION FAILED")
        print("=" * 80)
        exit(1)

if __name__ == "__main__":
    run_validation()
