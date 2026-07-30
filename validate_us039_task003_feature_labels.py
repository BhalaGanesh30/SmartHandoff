"""Validation script for US-039 TASK-003: Feature Labels Configuration.

Validates:
    1. feature_labels.yaml file structure
    2. All 7 features have labels in feature_labels section
    3. Discharge disposition encoding (0-4) documented
    4. Primary diagnosis group encoding (0-19) documented
    5. Startup validation in main.py catches missing labels
    6. .dockerignore includes config/ directory
    7. Predictor uses feature_labels correctly

US-039 TASK-003 — config/feature_labels.yaml with ordinal encoding documentation
"""
from __future__ import annotations

import os
import sys
import yaml
from pathlib import Path

# Add ml-inference to path
ML_INFERENCE_ROOT = Path(__file__).parent / "ml-inference"
sys.path.insert(0, str(ML_INFERENCE_ROOT))

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


def validate_yaml_structure() -> bool:
    """Validate feature_labels.yaml file structure and content."""
    print("\n1. YAML FILE STRUCTURE")
    print("=" * 60)
    
    try:
        yaml_path = ML_INFERENCE_ROOT / "config" / "feature_labels.yaml"
        
        check("YAML Structure", "feature_labels.yaml exists", yaml_path.exists())
        
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)
        
        check("YAML Structure", "YAML parses successfully", config is not None)
        check("YAML Structure", "Config is a dictionary", isinstance(config, dict))
        
        # Check main sections
        check("YAML Structure", "feature_labels section present",
              "feature_labels" in config)
        check("YAML Structure", "discharge_disposition_encoding section present",
              "discharge_disposition_encoding" in config)
        check("YAML Structure", "primary_diagnosis_group_encoding section present",
              "primary_diagnosis_group_encoding" in config)
        
        return True
    except Exception as e:
        check("YAML Structure", "YAML structure validation failed", False, str(e))
        return False


def validate_feature_labels() -> bool:
    """Validate all 7 features have human-readable labels."""
    print("\n2. FEATURE LABELS")
    print("=" * 60)
    
    try:
        from training.feature_schema import FEATURE_NAMES
        
        yaml_path = ML_INFERENCE_ROOT / "config" / "feature_labels.yaml"
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)
        
        feature_labels = config.get("feature_labels", {})
        
        check("Feature Labels", f"{len(FEATURE_NAMES)} features in schema",
              len(FEATURE_NAMES) == 7)
        
        # Check each feature has a label
        for feature in FEATURE_NAMES:
            has_label = feature in feature_labels
            label = feature_labels.get(feature, "")
            # Label should be meaningful (contain spaces or capitalization)
            is_readable = " " in label or any(c.isupper() for c in label)
            
            check("Feature Labels", f"'{feature}' has label", has_label)
            if has_label:
                check("Feature Labels", f"'{feature}' label is descriptive",
                      is_readable, f"Label: '{label}'")
        
        return True
    except Exception as e:
        check("Feature Labels", "Feature labels validation failed", False, str(e))
        return False


def validate_discharge_disposition_encoding() -> bool:
    """Validate discharge disposition encoding (0-4)."""
    print("\n3. DISCHARGE DISPOSITION ENCODING")
    print("=" * 60)
    
    try:
        yaml_path = ML_INFERENCE_ROOT / "config" / "feature_labels.yaml"
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)
        
        encoding = config.get("discharge_disposition_encoding", {})
        
        check("Discharge Encoding", "Encoding section exists", len(encoding) > 0)
        
        # Check all 5 values (0-4) are documented
        for i in range(5):
            has_value = i in encoding or str(i) in encoding
            check("Discharge Encoding", f"Value {i} documented", has_value)
        
        check("Discharge Encoding", "Exactly 5 values (0-4)",
              len(encoding) == 5)
        
        return True
    except Exception as e:
        check("Discharge Encoding", "Discharge encoding validation failed", False, str(e))
        return False


def validate_diagnosis_group_encoding() -> bool:
    """Validate primary diagnosis group encoding (0-19)."""
    print("\n4. PRIMARY DIAGNOSIS GROUP ENCODING")
    print("=" * 60)
    
    try:
        yaml_path = ML_INFERENCE_ROOT / "config" / "feature_labels.yaml"
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)
        
        encoding = config.get("primary_diagnosis_group_encoding", {})
        
        check("Diagnosis Encoding", "Encoding section exists", len(encoding) > 0)
        
        # Check all 20 values (0-19) are documented
        for i in range(20):
            has_value = i in encoding or str(i) in encoding
            check("Diagnosis Encoding", f"Value {i} documented", has_value)
        
        check("Diagnosis Encoding", "Exactly 20 values (0-19)",
              len(encoding) == 20)
        
        return True
    except Exception as e:
        check("Diagnosis Encoding", "Diagnosis encoding validation failed", False, str(e))
        return False


def validate_startup_validation() -> bool:
    """Validate main.py has startup validation logic."""
    print("\n5. STARTUP VALIDATION IN main.py")
    print("=" * 60)
    
    try:
        main_py = ML_INFERENCE_ROOT / "app" / "main.py"
        
        with open(main_py, "r") as f:
            content = f.read()
        
        # Check for validation logic
        check("Startup Validation", "Imports FEATURE_NAMES",
              "from training.feature_schema import FEATURE_NAMES" in content)
        check("Startup Validation", "Checks for missing features",
              "missing = [f for f in FEATURE_NAMES if f not in feature_labels]" in content)
        check("Startup Validation", "Raises RuntimeError if missing",
              "raise RuntimeError" in content and "missing labels for features" in content)
        check("Startup Validation", "Logs validation success",
              "Feature labels validated" in content)
        
        return True
    except Exception as e:
        check("Startup Validation", "Startup validation check failed", False, str(e))
        return False


def validate_dockerignore() -> bool:
    """Validate .dockerignore does not exclude config/ directory."""
    print("\n6. DOCKERIGNORE CONFIGURATION")
    print("=" * 60)
    
    try:
        dockerignore_path = ML_INFERENCE_ROOT / ".dockerignore"
        
        check("Dockerignore", ".dockerignore exists", dockerignore_path.exists())
        
        with open(dockerignore_path, "r") as f:
            content = f.read()
        
        # Config should NOT be explicitly excluded (we want it in the image)
        # Check for explicit "config/" line (not as a negation pattern like !config/)
        lines = [line.strip() for line in content.split('\n')]
        config_excluded = "config/" in lines or "config" in lines
        check("Dockerignore", "config/ NOT explicitly excluded (present in image)",
              not config_excluded)
        
        # Common patterns should be excluded
        check("Dockerignore", "__pycache__/ excluded", "__pycache__/" in content)
        check("Dockerignore", "tests/ excluded", "tests/" in content)
        check("Dockerignore", "data/ excluded", "data/" in content)
        check("Dockerignore", "models/ excluded", "models/" in content)
        
        return True
    except Exception as e:
        check("Dockerignore", "Dockerignore validation failed", False, str(e))
        return False


def validate_predictor_usage() -> bool:
    """Validate predictor.py uses feature_labels correctly."""
    print("\n7. PREDICTOR FEATURE LABEL USAGE")
    print("=" * 60)
    
    try:
        # Set environment variables
        os.environ["ML_MODEL_LOCAL_DIR"] = str(ML_INFERENCE_ROOT / "models")
        os.environ["ML_MODEL_VERSION"] = "1.0.0"
        os.environ["PYTHONPATH"] = str(ML_INFERENCE_ROOT)
        
        # Load model first
        from app.model_loader import load_model
        load_model()
        
        # Load feature labels
        yaml_path = ML_INFERENCE_ROOT / "config" / "feature_labels.yaml"
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)
        feature_labels = config.get("feature_labels", {})
        
        # Test prediction with feature labels
        from app.schemas import ReadmissionFeatures
        from app.predictor import predict
        
        features = ReadmissionFeatures(
            age=65.0,
            los_days=5.0,
            num_comorbidities=3.0,
            num_prior_admissions_12mo=1.0,
            medication_count=6.0,
            discharge_disposition=0.0,
            primary_diagnosis_group=2.0
        )
        
        response = predict(features, feature_labels)
        
        check("Predictor Usage", "Prediction successful", response is not None)
        check("Predictor Usage", "Contributing factors returned",
              len(response.contributing_factors) == 5)
        
        # Check that labels are human-readable (not raw feature names)
        for factor in response.contributing_factors:
            is_human_readable = " " in factor.feature or "(" in factor.feature
            raw_feature = factor.feature in ["age", "los_days", "num_comorbidities",
                                              "num_prior_admissions_12mo", "medication_count",
                                              "discharge_disposition", "primary_diagnosis_group"]
            
            check("Predictor Usage",
                  f"'{factor.feature}' is human-readable (not raw feature name)",
                  is_human_readable and not raw_feature)
        
        return True
    except Exception as e:
        check("Predictor Usage", "Predictor usage validation failed", False, str(e))
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
        return True
    else:
        print("❌ SOME VALIDATIONS FAILED")
        return False


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("US-039 TASK-003 VALIDATION")
    print("Feature Labels Configuration")
    print("=" * 60)
    
    validate_yaml_structure()
    validate_feature_labels()
    validate_discharge_disposition_encoding()
    validate_diagnosis_group_encoding()
    validate_startup_validation()
    validate_dockerignore()
    validate_predictor_usage()
    
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
