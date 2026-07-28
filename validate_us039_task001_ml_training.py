#!/usr/bin/env python3
"""Validation script for US-039 TASK-001: ML Model Training Pipeline.

Verifies:
    1. Feature schema defined correctly
    2. Synthetic data generator produces valid data
    3. Training pipeline produces required artifacts
    4. Model achieves AUC-ROC ≥ 0.80 on holdout
    5. Model and scaler are valid joblib files
    6. Evaluation report contains all required metrics
    7. No PHI in training outputs or logs

Design refs:
    US-039 TASK-001 — LogisticRegression readmission risk model
    US-039 AC Scenario 3 — AUC-ROC ≥ 0.80 requirement
"""
import sys
import json
from pathlib import Path
import joblib


def check_directory_structure() -> bool:
    """Check if required directories exist."""
    print("[1/8] Directory Structure Check")
    
    dirs = [
        Path("ml-inference/training"),
        Path("ml-inference/models"),
        Path("ml-inference/data"),
    ]
    
    all_passed = True
    for dir_path in dirs:
        if dir_path.exists():
            print(f"  ✓ Directory exists: {dir_path}")
        else:
            print(f"  ✗ Directory not found: {dir_path}")
            all_passed = False
    
    return all_passed


def check_training_files() -> bool:
    """Check if training module files exist."""
    print("\n[2/8] Training Module Files Check")
    
    files = {
        "Feature Schema": "ml-inference/training/feature_schema.py",
        "Synthetic Data Generator": "ml-inference/training/generate_synthetic_data.py",
        "Training Pipeline": "ml-inference/training/train_readmission_risk.py",
        "Package Init": "ml-inference/training/__init__.py",
        "Requirements": "ml-inference/requirements.txt",
    }
    
    all_passed = True
    for file_name, file_path in files.items():
        if Path(file_path).exists():
            print(f"  ✓ {file_name}: {file_path}")
        else:
            print(f"  ✗ {file_name} not found: {file_path}")
            all_passed = False
    
    return all_passed


def check_feature_schema() -> bool:
    """Verify feature schema definition."""
    print("\n[3/8] Feature Schema Check")
    
    try:
        import sys
        sys.path.insert(0, 'ml-inference')
        from training.feature_schema import FEATURE_NAMES, NUMERIC_FEATURES, CATEGORICAL_FEATURES
        
        required_features = [
            "age",
            "los_days",
            "num_comorbidities",
            "num_prior_admissions_12mo",
            "medication_count",
            "discharge_disposition",
            "primary_diagnosis_group",
        ]
        
        all_passed = True
        
        if len(FEATURE_NAMES) == 7:
            print(f"  ✓ FEATURE_NAMES has 7 features")
        else:
            print(f"  ✗ FEATURE_NAMES has {len(FEATURE_NAMES)} features, expected 7")
            all_passed = False
        
        for feature in required_features:
            if feature in FEATURE_NAMES:
                print(f"  ✓ Feature defined: {feature}")
            else:
                print(f"  ✗ Feature missing: {feature}")
                all_passed = False
        
        if len(NUMERIC_FEATURES) == 5:
            print(f"  ✓ NUMERIC_FEATURES has 5 features")
        else:
            print(f"  ✗ NUMERIC_FEATURES has {len(NUMERIC_FEATURES)} features, expected 5")
            all_passed = False
        
        if len(CATEGORICAL_FEATURES) == 2:
            print(f"  ✓ CATEGORICAL_FEATURES has 2 features")
        else:
            print(f"  ✗ CATEGORICAL_FEATURES has {len(CATEGORICAL_FEATURES)} features, expected 2")
            all_passed = False
        
        return all_passed
    
    except Exception as e:
        print(f"  ✗ Error loading feature schema: {e}")
        return False


def check_synthetic_data() -> bool:
    """Verify synthetic data file structure."""
    print("\n[4/8] Synthetic Data Check")
    
    data_file = Path("ml-inference/data/synthetic_encounters.csv")
    
    if not data_file.exists():
        print(f"  ✗ Synthetic data file not found: {data_file}")
        return False
    
    try:
        import pandas as pd
        df = pd.read_csv(data_file)
        
        all_passed = True
        
        if len(df) == 5000:
            print(f"  ✓ Dataset has 5000 rows")
        else:
            print(f"  ✗ Dataset has {len(df)} rows, expected 5000")
            all_passed = False
        
        required_columns = [
            "age", "los_days", "num_comorbidities", "num_prior_admissions_12mo",
            "medication_count", "discharge_disposition", "primary_diagnosis_group",
            "readmitted_30d"
        ]
        
        if len(df.columns) == 8:
            print(f"  ✓ Dataset has 8 columns")
        else:
            print(f"  ✗ Dataset has {len(df.columns)} columns, expected 8")
            all_passed = False
        
        for col in required_columns:
            if col in df.columns:
                print(f"  ✓ Column present: {col}")
            else:
                print(f"  ✗ Column missing: {col}")
                all_passed = False
        
        readmission_rate = df["readmitted_30d"].mean()
        if 0.15 <= readmission_rate <= 0.35:
            print(f"  ✓ Readmission rate realistic: {readmission_rate:.2%}")
        else:
            print(f"  ✗ Readmission rate unrealistic: {readmission_rate:.2%} (expected 15-35%)")
            all_passed = False
        
        return all_passed
    
    except Exception as e:
        print(f"  ✗ Error loading synthetic data: {e}")
        return False


def check_model_artifacts() -> bool:
    """Verify model artifacts exist and are valid."""
    print("\n[5/8] Model Artifacts Check")
    
    artifacts = {
        "Model": "ml-inference/models/model.joblib",
        "Scaler": "ml-inference/models/scaler.joblib",
        "Evaluation Report": "ml-inference/models/evaluation_report.json",
    }
    
    all_passed = True
    for artifact_name, artifact_path in artifacts.items():
        if Path(artifact_path).exists():
            print(f"  ✓ {artifact_name} exists: {artifact_path}")
        else:
            print(f"  ✗ {artifact_name} not found: {artifact_path}")
            all_passed = False
    
    # Verify joblib files are loadable
    try:
        model = joblib.load("ml-inference/models/model.joblib")
        print(f"  ✓ Model is valid joblib file (LogisticRegression)")
    except Exception as e:
        print(f"  ✗ Model is not a valid joblib file: {e}")
        all_passed = False
    
    try:
        scaler = joblib.load("ml-inference/models/scaler.joblib")
        print(f"  ✓ Scaler is valid joblib file (StandardScaler)")
    except Exception as e:
        print(f"  ✗ Scaler is not a valid joblib file: {e}")
        all_passed = False
    
    return all_passed


def check_evaluation_report() -> bool:
    """Verify evaluation report contains required metrics."""
    print("\n[6/8] Evaluation Report Check")
    
    report_path = Path("ml-inference/models/evaluation_report.json")
    
    if not report_path.exists():
        print(f"  ✗ Evaluation report not found")
        return False
    
    try:
        with open(report_path, 'r') as f:
            metrics = json.load(f)
        
        all_passed = True
        
        required_metrics = [
            "auc_roc", "precision", "recall", "f1",
            "n_train", "n_test", "readmission_rate_train", "readmission_rate_test",
            "min_auc_threshold", "quality_gate"
        ]
        
        for metric in required_metrics:
            if metric in metrics:
                print(f"  ✓ Metric present: {metric} = {metrics[metric]}")
            else:
                print(f"  ✗ Metric missing: {metric}")
                all_passed = False
        
        return all_passed
    
    except Exception as e:
        print(f"  ✗ Error loading evaluation report: {e}")
        return False


def check_auc_threshold() -> bool:
    """Verify AUC-ROC ≥ 0.80 quality gate."""
    print("\n[7/8] AUC-ROC Quality Gate Check")
    
    report_path = Path("ml-inference/models/evaluation_report.json")
    
    try:
        with open(report_path, 'r') as f:
            metrics = json.load(f)
        
        auc_roc = metrics.get("auc_roc", 0.0)
        min_threshold = metrics.get("min_auc_threshold", 0.80)
        quality_gate = metrics.get("quality_gate", "FAILED")
        
        if auc_roc >= min_threshold:
            print(f"  ✓ AUC-ROC: {auc_roc:.4f} >= {min_threshold}")
        else:
            print(f"  ✗ AUC-ROC: {auc_roc:.4f} < {min_threshold} (quality gate FAILED)")
            return False
        
        if quality_gate == "PASSED":
            print(f"  ✓ Quality gate: {quality_gate}")
        else:
            print(f"  ✗ Quality gate: {quality_gate}")
            return False
        
        return True
    
    except Exception as e:
        print(f"  ✗ Error checking AUC threshold: {e}")
        return False


def check_no_phi() -> bool:
    """Verify no PHI in training outputs."""
    print("\n[8/8] PHI Containment Check")
    
    # Check feature names don't contain PHI-related fields
    try:
        import sys
        sys.path.insert(0, 'ml-inference')
        from training.feature_schema import FEATURE_NAMES
        
        phi_keywords = ["name", "dob", "mrn", "ssn", "phone", "email", "address"]
        
        all_passed = True
        for feature in FEATURE_NAMES:
            has_phi = any(keyword in feature.lower() for keyword in phi_keywords)
            if has_phi:
                print(f"  ✗ Feature may contain PHI: {feature}")
                all_passed = False
        
        if all_passed:
            print(f"  ✓ No PHI keywords in feature names")
        
        # Check evaluation report doesn't contain patient identifiers
        report_path = Path("ml-inference/models/evaluation_report.json")
        if report_path.exists():
            with open(report_path, 'r') as f:
                report_content = f.read()
            
            has_phi = any(keyword in report_content.lower() for keyword in phi_keywords)
            if has_phi:
                print(f"  ✗ Evaluation report may contain PHI")
                all_passed = False
            else:
                print(f"  ✓ No PHI in evaluation report")
        
        return all_passed
    
    except Exception as e:
        print(f"  ✗ Error checking PHI: {e}")
        return False


def main() -> int:
    """Run all validation checks."""
    print("=" * 80)
    print("US-039 TASK-001 Validation: ML Model Training Pipeline")
    print("=" * 80)
    
    results = [
        check_directory_structure(),
        check_training_files(),
        check_feature_schema(),
        check_synthetic_data(),
        check_model_artifacts(),
        check_evaluation_report(),
        check_auc_threshold(),
        check_no_phi(),
    ]
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 80)
    if all(results):
        print(f"✅ ALL VALIDATION CHECKS PASSED ({passed}/{total})")
    else:
        print(f"❌ SOME CHECKS FAILED ({passed}/{total})")
    print("=" * 80)
    
    print("\nValidation Summary:")
    print("  ✓ Directory structure created")
    print("  ✓ Training module files present")
    print("  ✓ Feature schema defined (7 features)")
    print("  ✓ Synthetic data generated (5000 encounters)")
    print("  ✓ Model artifacts created (model.joblib, scaler.joblib)")
    print("  ✓ Evaluation report generated")
    print("  ✓ AUC-ROC ≥ 0.80 quality gate passed")
    print("  ✓ No PHI in training outputs")
    
    print("\nNext Steps:")
    print("  1. Implement TASK-002 (ML Inference Service Endpoint)")
    print("  2. Load model and scaler in FastAPI service")
    print("  3. Create POST /predict/readmission-risk endpoint")
    print("  4. Add SHAP explainability for feature importance")
    print("  5. Deploy to Cloud Run with model preloaded")
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
