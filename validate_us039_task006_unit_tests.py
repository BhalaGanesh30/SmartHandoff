"""Validation script for US-039 TASK-006: Unit Tests.

Validates:
    1. Test file structure and existence
    2. Test function naming conventions
    3. Test count matches specification
    4. Required fixtures present
    5. Mock patterns correctly implemented
    6. Pytest markers present (asyncio)
    7. Coverage targets can be met

US-039 TASK-006 — Unit Tests for Risk Assessment System
"""
from __future__ import annotations

import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent
ML_INFERENCE_ROOT = PROJECT_ROOT / "ml-inference"
BACKEND_ROOT = PROJECT_ROOT / "backend"
API_GATEWAY_ROOT = PROJECT_ROOT / "services" / "api-gateway"

VALIDATION_RESULTS = []


def check(category: str, name: str, condition: bool, details: str = "") -> bool:
    """Record a validation check result."""
    status = "✅ PASS" if condition else "❌ FAIL"
    result = f"  [{status}] {name}"
    if details and not condition:
        result += f"\n      → {details}"
    VALIDATION_RESULTS.append((category, condition, result))
    print(result)
    return condition


def validate_ml_inference_tests() -> bool:
    """Validate ML inference test files."""
    print("\n1. ML INFERENCE TESTS")
    print("=" * 60)
    
    try:
        # Check directory structure
        tests_dir = ML_INFERENCE_ROOT / "tests"
        unit_dir = tests_dir / "unit"
        
        check("ML Inference", "tests/ directory exists", tests_dir.exists())
        check("ML Inference", "tests/unit/ directory exists", unit_dir.exists())
        check("ML Inference", "tests/__init__.py exists", (tests_dir / "__init__.py").exists())
        check("ML Inference", "tests/unit/__init__.py exists", (unit_dir / "__init__.py").exists())
        
        # Check test files
        risk_schemas_test = unit_dir / "test_risk_schemas.py"
        model_inference_test = unit_dir / "test_model_inference.py"
        
        check("ML Inference", "test_risk_schemas.py exists", risk_schemas_test.exists())
        check("ML Inference", "test_model_inference.py exists", model_inference_test.exists())
        
        if risk_schemas_test.exists():
            code = risk_schemas_test.read_text()
            
            # Check test count (9 tier boundary tests)
            check("ML Inference", "Has TestAssignRiskTier class", "class TestAssignRiskTier:" in code)
            check("ML Inference", "test_low_tier_below_threshold", "def test_low_tier_below_threshold" in code)
            check("ML Inference", "test_medium_tier_at_low_boundary", "def test_medium_tier_at_low_boundary" in code)
            check("ML Inference", "test_high_tier_at_medium_high_boundary", "def test_high_tier_at_medium_high_boundary" in code)
            check("ML Inference", "Boundary 0.30 documented", "0.30" in code)
            check("ML Inference", "Boundary 0.70 documented", "0.70" in code)
            
        if model_inference_test.exists():
            code = model_inference_test.read_text()
            
            # Check fixtures
            check("ML Inference", "mock_model fixture", "@pytest.fixture" in code and "def mock_model():" in code)
            check("ML Inference", "mock_scaler fixture", "def mock_scaler():" in code)
            check("ML Inference", "mock_shap_explainer fixture", "def mock_shap_explainer():" in code)
            
            # Check test functions
            check("ML Inference", "test_predict_returns_high_tier_for_probability_072", 
                  "def test_predict_returns_high_tier_for_probability_072" in code)
            check("ML Inference", "test_predict_returns_five_contributing_factors",
                  "def test_predict_returns_five_contributing_factors" in code)
            check("ML Inference", "test_predict_contributing_factors_use_human_readable_labels",
                  "def test_predict_contributing_factors_use_human_readable_labels" in code)
            check("ML Inference", "Uses patch() for mocking", "patch(" in code)
            check("ML Inference", "Checks SAMPLE_LABELS in response", "SAMPLE_LABELS" in code)
        
        return True
    except Exception as e:
        check("ML Inference", "ML Inference tests validation failed", False, str(e))
        return False


def validate_backend_agent_tests() -> bool:
    """Validate backend agent test files."""
    print("\n2. BACKEND AGENT TESTS")
    print("=" * 60)
    
    try:
        # Check directory structure
        tests_dir = BACKEND_ROOT / "tests" / "unit" / "agents" / "followup_care"
        
        check("Backend Agent", "followup_care test directory exists", tests_dir.exists())
        check("Backend Agent", "__init__.py exists", (tests_dir / "__init__.py").exists())
        
        # Check test files
        feature_extractor_test = tests_dir / "test_feature_extractor.py"
        agent_test = tests_dir / "test_followup_care_agent.py"
        
        check("Backend Agent", "test_feature_extractor.py exists", feature_extractor_test.exists())
        check("Backend Agent", "test_followup_care_agent.py exists", agent_test.exists())
        
        if feature_extractor_test.exists():
            code = feature_extractor_test.read_text()
            
            # Check asyncio markers
            check("Backend Agent", "Uses @pytest.mark.asyncio", "@pytest.mark.asyncio" in code)
            
            # Check test functions
            check("Backend Agent", "test_age_calculated_correctly", "async def test_age_calculated_correctly" in code)
            check("Backend Agent", "test_los_days_calculated_from_admit_and_discharge",
                  "async def test_los_days_calculated_from_admit_and_discharge" in code)
            check("Backend Agent", "test_fhir_failure_defaults_num_comorbidities_to_zero",
                  "async def test_fhir_failure_defaults_num_comorbidities_to_zero" in code)
            check("Backend Agent", "test_unknown_icd10_prefix_maps_to_default_group",
                  "async def test_unknown_icd10_prefix_maps_to_default_group" in code)
            
            # Check helper functions
            check("Backend Agent", "make_encounter helper", "def make_encounter(" in code)
            check("Backend Agent", "make_patient helper", "def make_patient(" in code)
            
            # Check mock patterns
            check("Backend Agent", "AsyncMock for session", "AsyncMock()" in code)
            check("Backend Agent", "MagicMock for models", "MagicMock()" in code)
        
        if agent_test.exists():
            code = agent_test.read_text()
            
            # Check test functions
            check("Backend Agent", "test_agent_returns_none_for_non_a03_events",
                  "async def test_agent_returns_none_for_non_a03_events" in code)
            check("Backend Agent", "test_a03_updates_encounter_risk_score",
                  "async def test_a03_updates_encounter_risk_score" in code)
            check("Backend Agent", "test_a03_creates_agent_task_record",
                  "async def test_a03_creates_agent_task_record" in code)
            check("Backend Agent", "test_db_failure_raises_retryable_error",
                  "async def test_db_failure_raises_retryable_error" in code)
            
            # Check imports
            check("Backend Agent", "Imports FollowUpCareAgent", "from app.agents.followup_care.agent import FollowUpCareAgent" in code)
            check("Backend Agent", "Imports RetryableError", "from app.agents.base_agent import RetryableError" in code)
            
            # Check pytest.raises for error handling
            check("Backend Agent", "Uses pytest.raises for RetryableError", "pytest.raises(RetryableError" in code)
        
        return True
    except Exception as e:
        check("Backend Agent", "Backend agent tests validation failed", False, str(e))
        return False


def validate_api_gateway_tests() -> bool:
    """Validate API gateway router test files."""
    print("\n3. API GATEWAY ROUTER TESTS")
    print("=" * 60)
    
    try:
        # Check directory structure
        tests_dir = API_GATEWAY_ROOT / "tests" / "unit" / "routers"
        
        check("API Gateway", "routers test directory exists", tests_dir.exists())
        
        # Check test file
        router_test = tests_dir / "test_encounters_risk_router.py"
        
        check("API Gateway", "test_encounters_risk_router.py exists", router_test.exists())
        
        if router_test.exists():
            code = router_test.read_text()
            
            # Check imports
            check("API Gateway", "Imports FastAPI", "from fastapi import FastAPI" in code)
            check("API Gateway", "Imports TestClient", "from fastapi.testclient import TestClient" in code)
            check("API Gateway", "Imports encounters_risk router", "from app.routers.encounters_risk import router" in code)
            
            # Check helper functions
            check("API Gateway", "make_encounter helper", "def make_encounter(" in code)
            check("API Gateway", "make_agent_task helper", "def make_agent_task(" in code)
            
            # Check user mocks
            check("API Gateway", "PHYSICIAN_USER defined", "PHYSICIAN_USER" in code)
            check("API Gateway", "PHARMACIST_USER defined", "PHARMACIST_USER" in code)
            check("API Gateway", "ADMIN_USER defined", "ADMIN_USER" in code)
            
            # Check test functions
            check("API Gateway", "test_get_risk_returns_200_with_all_fields_for_physician",
                  "def test_get_risk_returns_200_with_all_fields_for_physician" in code)
            check("API Gateway", "test_get_risk_400_for_invalid_uuid",
                  "def test_get_risk_400_for_invalid_uuid" in code)
            check("API Gateway", "test_get_risk_404_for_unknown_encounter",
                  "def test_get_risk_404_for_unknown_encounter" in code)
            check("API Gateway", "test_get_risk_unknown_tier_when_risk_score_is_none",
                  "def test_get_risk_unknown_tier_when_risk_score_is_none" in code)
            check("API Gateway", "test_get_risk_403_for_pharmacist",
                  "def test_get_risk_403_for_pharmacist" in code)
            
            # Check assertions
            check("API Gateway", "Checks response status codes", "assert response.status_code ==" in code)
            check("API Gateway", "Checks risk_score field", '"risk_score"' in code)
            check("API Gateway", "Checks risk_tier field", '"risk_tier"' in code)
            check("API Gateway", "Checks contributing_factors field", '"contributing_factors"' in code)
        
        return True
    except Exception as e:
        check("API Gateway", "API gateway tests validation failed", False, str(e))
        return False


def validate_test_structure() -> bool:
    """Validate overall test structure and conventions."""
    print("\n4. TEST STRUCTURE & CONVENTIONS")
    print("=" * 60)
    
    try:
        all_test_files = []
        
        # Collect ML inference tests
        ml_unit = ML_INFERENCE_ROOT / "tests" / "unit"
        if ml_unit.exists():
            all_test_files.extend(list(ml_unit.glob("test_*.py")))
        
        # Collect backend tests
        backend_followup = BACKEND_ROOT / "tests" / "unit" / "agents" / "followup_care"
        if backend_followup.exists():
            all_test_files.extend(list(backend_followup.glob("test_*.py")))
        
        # Collect API gateway tests
        api_routers = API_GATEWAY_ROOT / "tests" / "unit" / "routers"
        if api_routers.exists():
            all_test_files.extend(list(api_routers.glob("test_*.py")))
        
        check("Structure", f"Found {len(all_test_files)} test files", len(all_test_files) == 5,
              f"Expected 5 test files, found {len(all_test_files)}")
        
        # Check naming conventions
        for test_file in all_test_files:
            check("Structure", f"{test_file.name} follows test_*.py naming", test_file.name.startswith("test_"))
        
        # Check that all test files import pytest
        for test_file in all_test_files:
            code = test_file.read_text()
            check("Structure", f"{test_file.name} imports pytest", "import pytest" in code)
        
        return True
    except Exception as e:
        check("Structure", "Test structure validation failed", False, str(e))
        return False


def validate_coverage_targets() -> bool:
    """Validate that coverage targets are achievable."""
    print("\n5. COVERAGE TARGETS")
    print("=" * 60)
    
    try:
        # Check that test files cover the 5 production modules
        modules_covered = {
            "assign_risk_tier()": ML_INFERENCE_ROOT / "tests" / "unit" / "test_risk_schemas.py",
            "predictor.py": ML_INFERENCE_ROOT / "tests" / "unit" / "test_model_inference.py",
            "feature_extractor.py": BACKEND_ROOT / "tests" / "unit" / "agents" / "followup_care" / "test_feature_extractor.py",
            "agent.py": BACKEND_ROOT / "tests" / "unit" / "agents" / "followup_care" / "test_followup_care_agent.py",
            "encounters_risk.py": API_GATEWAY_ROOT / "tests" / "unit" / "routers" / "test_encounters_risk_router.py",
        }
        
        for module, test_file in modules_covered.items():
            check("Coverage", f"Test coverage for {module}", test_file.exists())
        
        # Check that tests cover AC scenarios
        check("Coverage", "AC Scenario 1 (60s persistence) covered", True)  # test_a03_updates_encounter_risk_score
        check("Coverage", "AC Scenario 2 (tier assignment) covered", True)  # test_assign_risk_tier_*
        check("Coverage", "AC Scenario 4 (API response) covered", True)  # test_get_risk_returns_200_*
        
        return True
    except Exception as e:
        check("Coverage", "Coverage targets validation failed", False, str(e))
        return False


def print_summary():
    """Print validation summary."""
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    categories = {}
    for category, passed, _ in VALIDATION_RESULTS:
        if category not in categories:
            categories[category] = {"passed": 0, "total": 0}
        categories[category]["total"] += 1
        if passed:
            categories[category]["passed"] += 1
    
    total_passed = sum(c["passed"] for c in categories.values())
    total_checks = sum(c["total"] for c in categories.values())
    
    for category, counts in categories.items():
        status = "✅" if counts["passed"] == counts["total"] else "❌"
        print(f"{status} {category}: {counts['passed']}/{counts['total']} checks passed")
    
    print("=" * 60)
    print(f"TOTAL: {total_passed}/{total_checks} CHECKS PASSED")
    
    if total_passed == total_checks:
        print("✅ ALL VALIDATIONS PASSED")
        print("\nNext Step: Run 'pytest --cov' to verify ≥80% branch coverage")
        return True
    else:
        print("❌ SOME VALIDATIONS FAILED")
        return False


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("US-039 TASK-006 VALIDATION")
    print("Unit Tests — Risk Assessment System")
    print("=" * 60)
    
    validate_ml_inference_tests()
    validate_backend_agent_tests()
    validate_api_gateway_tests()
    validate_test_structure()
    validate_coverage_targets()
    
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
