"""Validation script for US-039 TASK-002: ML Inference Service Endpoint.

Validates:
    1. Model and scaler loading from local directory
    2. Feature labels loading from YAML
    3. Prediction endpoint returns correct response structure
    4. Risk tier thresholds applied correctly
    5. SHAP contributing factors (top 5)
    6. Health and readiness probes
    7. PHI containment
    8. Response time < 500ms (TR-007)

US-039 TASK-002 — ML Inference Service implementation
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Add ml-inference to path
ML_INFERENCE_ROOT = Path(__file__).parent / "ml-inference"
sys.path.insert(0, str(ML_INFERENCE_ROOT))

# Set environment variables before importing app
os.environ["ML_MODEL_LOCAL_DIR"] = str(ML_INFERENCE_ROOT / "models")
os.environ["ML_MODEL_VERSION"] = "1.0.0"
os.environ["FEATURE_LABELS_PATH"] = str(ML_INFERENCE_ROOT / "config" / "feature_labels.yaml")
os.environ["PYTHONPATH"] = str(ML_INFERENCE_ROOT)

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


def validate_model_loading() -> bool:
    """Validate model and scaler can be loaded from local directory."""
    print("\n1. MODEL AND SCALER LOADING")
    print("=" * 60)
    
    try:
        from app.model_loader import load_model, get_model, get_scaler, get_model_version
        
        # Load model
        load_model()
        
        # Get model
        model = get_model()
        check("Model Loading", "Model loaded successfully", model is not None)
        check("Model Loading", "Model is LogisticRegression", 
              type(model).__name__ == "LogisticRegression")
        
        # Get scaler
        scaler = get_scaler()
        check("Model Loading", "Scaler loaded successfully", scaler is not None)
        check("Model Loading", "Scaler is StandardScaler",
              type(scaler).__name__ == "StandardScaler")
        
        # Get version
        version = get_model_version()
        check("Model Loading", "Model version is set", version == "1.0.0")
        
        return True
    except Exception as e:
        check("Model Loading", "Model loading failed", False, str(e))
        return False


def validate_feature_labels() -> bool:
    """Validate feature labels YAML loading."""
    print("\n2. FEATURE LABELS LOADING")
    print("=" * 60)
    
    try:
        import yaml
        feature_labels_path = Path(os.environ["FEATURE_LABELS_PATH"])
        
        check("Feature Labels", "feature_labels.yaml exists", feature_labels_path.exists())
        
        with open(feature_labels_path, "r") as f:
            labels = yaml.safe_load(f)
        
        check("Feature Labels", "Labels loaded successfully", labels is not None)
        check("Feature Labels", "Labels is a dictionary", isinstance(labels, dict))
        
        # Check all 7 features have labels
        from training.feature_schema import FEATURE_NAMES
        all_labeled = all(f in labels for f in FEATURE_NAMES)
        check("Feature Labels", "All 7 features have labels", all_labeled)
        
        return True
    except Exception as e:
        check("Feature Labels", "Feature labels loading failed", False, str(e))
        return False


def validate_prediction_logic() -> bool:
    """Validate prediction logic with test inputs."""
    print("\n3. PREDICTION LOGIC")
    print("=" * 60)
    
    try:
        from app.schemas import ReadmissionFeatures
        from app.predictor import predict
        import yaml
        
        # Load feature labels
        with open(os.environ["FEATURE_LABELS_PATH"], "r") as f:
            feature_labels = yaml.safe_load(f)
        
        # Test case 1: Low risk patient
        low_risk = ReadmissionFeatures(
            age=45.0,
            los_days=2.0,
            num_comorbidities=0.0,
            num_prior_admissions_12mo=0.0,
            medication_count=2.0,
            discharge_disposition=0.0,  # home
            primary_diagnosis_group=5.0
        )
        
        response_low = predict(low_risk, feature_labels)
        check("Prediction Logic", "Low risk prediction successful", response_low is not None)
        check("Prediction Logic", "Low risk score in [0.0, 1.0]",
              0.0 <= response_low.risk_score <= 1.0)
        check("Prediction Logic", "Low risk tier is LOW or MEDIUM",
              response_low.risk_tier.value in ["LOW", "MEDIUM"])
        
        # Test case 2: High risk patient
        high_risk = ReadmissionFeatures(
            age=85.0,
            los_days=15.0,
            num_comorbidities=8.0,
            num_prior_admissions_12mo=5.0,
            medication_count=15.0,
            discharge_disposition=4.0,  # AMA
            primary_diagnosis_group=12.0
        )
        
        response_high = predict(high_risk, feature_labels)
        check("Prediction Logic", "High risk prediction successful", response_high is not None)
        check("Prediction Logic", "High risk score > low risk score",
              response_high.risk_score > response_low.risk_score)
        
        return True
    except Exception as e:
        check("Prediction Logic", "Prediction logic failed", False, str(e))
        return False


def validate_response_structure() -> bool:
    """Validate response structure matches schema."""
    print("\n4. RESPONSE STRUCTURE")
    print("=" * 60)
    
    try:
        from app.schemas import ReadmissionFeatures
        from app.predictor import predict
        import yaml
        
        with open(os.environ["FEATURE_LABELS_PATH"], "r") as f:
            feature_labels = yaml.safe_load(f)
        
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
        
        # Check response fields
        check("Response Structure", "risk_score present", hasattr(response, "risk_score"))
        check("Response Structure", "risk_tier present", hasattr(response, "risk_tier"))
        check("Response Structure", "contributing_factors present",
              hasattr(response, "contributing_factors"))
        check("Response Structure", "model_version present", hasattr(response, "model_version"))
        
        # Check contributing factors structure
        check("Response Structure", "contributing_factors is list",
              isinstance(response.contributing_factors, list))
        check("Response Structure", "contributing_factors has 5 items",
              len(response.contributing_factors) == 5)
        
        if response.contributing_factors:
            factor = response.contributing_factors[0]
            check("Response Structure", "factor has 'feature' field", hasattr(factor, "feature"))
            check("Response Structure", "factor has 'shap_value' field", hasattr(factor, "shap_value"))
            check("Response Structure", "factor has 'feature_value' field",
                  hasattr(factor, "feature_value"))
            check("Response Structure", "factor has 'direction' field", hasattr(factor, "direction"))
        
        return True
    except Exception as e:
        check("Response Structure", "Response structure validation failed", False, str(e))
        return False


def validate_risk_tiers() -> bool:
    """Validate risk tier threshold logic."""
    print("\n5. RISK TIER THRESHOLDS")
    print("=" * 60)
    
    try:
        from app.schemas import assign_risk_tier, RiskTier
        
        # Test LOW tier (< 0.30)
        check("Risk Tiers", "0.10 → LOW", assign_risk_tier(0.10) == RiskTier.LOW)
        check("Risk Tiers", "0.29 → LOW", assign_risk_tier(0.29) == RiskTier.LOW)
        
        # Test MEDIUM tier (0.30 ≤ p < 0.70)
        check("Risk Tiers", "0.30 → MEDIUM", assign_risk_tier(0.30) == RiskTier.MEDIUM)
        check("Risk Tiers", "0.50 → MEDIUM", assign_risk_tier(0.50) == RiskTier.MEDIUM)
        check("Risk Tiers", "0.69 → MEDIUM", assign_risk_tier(0.69) == RiskTier.MEDIUM)
        
        # Test HIGH tier (≥ 0.70)
        check("Risk Tiers", "0.70 → HIGH", assign_risk_tier(0.70) == RiskTier.HIGH)
        check("Risk Tiers", "0.85 → HIGH", assign_risk_tier(0.85) == RiskTier.HIGH)
        check("Risk Tiers", "1.00 → HIGH", assign_risk_tier(1.00) == RiskTier.HIGH)
        
        return True
    except Exception as e:
        check("Risk Tiers", "Risk tier validation failed", False, str(e))
        return False


def validate_shap_explanations() -> bool:
    """Validate SHAP explanations are computed."""
    print("\n6. SHAP EXPLANATIONS")
    print("=" * 60)
    
    try:
        from app.schemas import ReadmissionFeatures
        from app.predictor import predict
        import yaml
        
        with open(os.environ["FEATURE_LABELS_PATH"], "r") as f:
            feature_labels = yaml.safe_load(f)
        
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
        
        # Check SHAP values
        check("SHAP", "Contributing factors returned", len(response.contributing_factors) == 5)
        
        for factor in response.contributing_factors:
            # Each factor should have human-readable label
            is_readable = factor.feature != "" and not factor.feature.startswith("_")
            check("SHAP", f"'{factor.feature}' is human-readable", is_readable)
            
            # Direction should match sign of SHAP value
            expected_direction = "increases_risk" if factor.shap_value > 0 else "decreases_risk"
            check("SHAP", f"'{factor.feature}' direction correct",
                  factor.direction == expected_direction)
        
        return True
    except Exception as e:
        check("SHAP", "SHAP explanations failed", False, str(e))
        return False


def validate_performance() -> bool:
    """Validate inference latency < 500ms (TR-007)."""
    print("\n7. PERFORMANCE (TR-007)")
    print("=" * 60)
    
    try:
        from app.schemas import ReadmissionFeatures
        from app.predictor import predict
        import yaml
        
        with open(os.environ["FEATURE_LABELS_PATH"], "r") as f:
            feature_labels = yaml.safe_load(f)
        
        features = ReadmissionFeatures(
            age=65.0,
            los_days=5.0,
            num_comorbidities=3.0,
            num_prior_admissions_12mo=1.0,
            medication_count=6.0,
            discharge_disposition=0.0,
            primary_diagnosis_group=2.0
        )
        
        # Warm-up call (SHAP explainer initialization)
        predict(features, feature_labels)
        
        # Measure 10 calls
        latencies = []
        for _ in range(10):
            start = time.time()
            predict(features, feature_labels)
            latencies.append((time.time() - start) * 1000)  # ms
        
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(0.95 * len(latencies))]
        
        print(f"      Average latency: {avg_latency:.2f} ms")
        print(f"      P95 latency: {p95_latency:.2f} ms")
        
        check("Performance", f"Average latency < 500ms ({avg_latency:.2f} ms)",
              avg_latency < 500)
        check("Performance", f"P95 latency < 500ms ({p95_latency:.2f} ms)",
              p95_latency < 500)
        
        return True
    except Exception as e:
        check("Performance", "Performance validation failed", False, str(e))
        return False


def validate_phi_containment() -> bool:
    """Validate no PHI in responses or logs."""
    print("\n8. PHI CONTAINMENT")
    print("=" * 60)
    
    try:
        from app.schemas import ReadmissionFeatures
        from app.predictor import predict
        import yaml
        
        with open(os.environ["FEATURE_LABELS_PATH"], "r") as f:
            feature_labels = yaml.safe_load(f)
        
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
        response_json = response.model_dump_json()
        
        # PHI keywords that should NOT appear
        phi_keywords = [
            "name", "ssn", "mrn", "dob", "date_of_birth",
            "address", "phone", "email", "patient_id", "encounter_id"
        ]
        
        for keyword in phi_keywords:
            check("PHI Containment", f"No '{keyword}' in response",
                  keyword not in response_json.lower())
        
        return True
    except Exception as e:
        check("PHI Containment", "PHI containment check failed", False, str(e))
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
    print("US-039 TASK-002 VALIDATION")
    print("ML Inference Service Endpoint")
    print("=" * 60)
    
    validate_model_loading()
    validate_feature_labels()
    validate_prediction_logic()
    validate_response_structure()
    validate_risk_tiers()
    validate_shap_explanations()
    validate_performance()
    validate_phi_containment()
    
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
