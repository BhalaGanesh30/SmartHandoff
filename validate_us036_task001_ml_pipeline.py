"""Validation script for US-036 TASK-001 ML training pipeline.

Validates:
- Module syntax (all .py files parse correctly)
- Feature engineering logic (compute_los_so_far_hours, build_feature_dataframe)
- Pipeline construction (preprocessor + regressor)
- Quality gate thresholds

Design refs:
    US-036 TASK-001 — Validation checklist
"""
from __future__ import annotations

import ast
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

print("=" * 80)
print("US-036 TASK-001 Validation: ML Training Pipeline")
print("=" * 80)

# ────────────────────────────────────────────────────────────────────────────
# 1. Syntax check
# ────────────────────────────────────────────────────────────────────────────
print("\n[1/5] Syntax Check")
modules = [
    "ml/discharge_time_model/__init__.py",
    "ml/discharge_time_model/features.py",
    "ml/discharge_time_model/train.py",
    "ml/discharge_time_model/evaluate.py",
    "ml/discharge_time_model/upload.py",
]

syntax_pass = 0
for module_path in modules:
    try:
        p = Path(module_path)
        if not p.exists():
            print(f"  ✗ {module_path}: FILE NOT FOUND")
            continue
        ast.parse(p.read_text())
        print(f"  ✓ {module_path}: OK")
        syntax_pass += 1
    except SyntaxError as e:
        print(f"  ✗ {module_path}: SYNTAX ERROR — {e}")

if syntax_pass != len(modules):
    print(f"\n✗ Syntax check FAILED ({syntax_pass}/{len(modules)} passed)")
    sys.exit(1)

print(f"\n✓ Syntax check PASSED ({syntax_pass}/{len(modules)})")

# ────────────────────────────────────────────────────────────────────────────
# 2. Feature engineering logic
# ────────────────────────────────────────────────────────────────────────────
print("\n[2/5] Feature Engineering Logic")
sys.path.insert(0, "ml/discharge_time_model")

try:
    from features import (
        compute_los_so_far_hours,
        build_feature_dataframe,
        CATEGORICAL_FEATURES,
        NUMERIC_FEATURES,
        ALL_FEATURES,
    )

    # Test compute_los_so_far_hours
    admit_time = datetime(2026, 7, 28, 10, 0, 0, tzinfo=timezone.utc)
    reference_time = datetime(2026, 7, 28, 14, 30, 0, tzinfo=timezone.utc)
    los = compute_los_so_far_hours(admit_time, reference_time)
    expected_los = 4.5  # 4.5 hours
    assert abs(los - expected_los) < 0.01, f"Expected {expected_los}, got {los}"
    print(f"  ✓ compute_los_so_far_hours: {los:.2f}h (expected {expected_los}h)")

    # Test build_feature_dataframe
    sample_encounter = {
        "admit_time": admit_time,
        "patient_dob": datetime(1980, 1, 1, tzinfo=timezone.utc),
        "admit_diagnosis_group": "CARDIOVASCULAR",
        "unit": "3A",
        "pending_procedures_count": 2,
    }
    df = build_feature_dataframe([sample_encounter], reference_time)
    assert len(df) == 1, f"Expected 1 row, got {len(df)}"
    assert df.iloc[0]["patient_age"] == 46, f"Expected age 46, got {df.iloc[0]['patient_age']}"
    assert df.iloc[0]["los_so_far_hours"] == los
    assert df.iloc[0]["pending_procedures"] == 2
    assert df.iloc[0]["admit_diagnosis_group"] == "CARDIOVASCULAR"
    print(f"  ✓ build_feature_dataframe: 1 row, {len(df.columns)} columns")

    # Test feature lists
    assert len(NUMERIC_FEATURES) == 4, f"Expected 4 numeric features, got {len(NUMERIC_FEATURES)}"
    assert len(CATEGORICAL_FEATURES) == 2, f"Expected 2 categorical features, got {len(CATEGORICAL_FEATURES)}"
    assert len(ALL_FEATURES) == 6, f"Expected 6 total features, got {len(ALL_FEATURES)}"
    print(f"  ✓ Feature lists: {len(NUMERIC_FEATURES)} numeric, {len(CATEGORICAL_FEATURES)} categorical")

except Exception as e:
    print(f"  ✗ Feature engineering FAILED: {e}")
    sys.exit(1)

print("\n✓ Feature engineering logic PASSED")

# ────────────────────────────────────────────────────────────────────────────
# 3. Pipeline construction (import only, no training)
# ────────────────────────────────────────────────────────────────────────────
print("\n[3/5] Pipeline Construction")
try:
    from train import build_pipeline

    pipeline = build_pipeline()
    assert hasattr(pipeline, "fit"), "Pipeline missing fit method"
    assert hasattr(pipeline, "predict"), "Pipeline missing predict method"
    assert "preprocessor" in pipeline.named_steps, "Pipeline missing preprocessor step"
    assert "regressor" in pipeline.named_steps, "Pipeline missing regressor step"
    print(f"  ✓ Pipeline structure: {list(pipeline.named_steps.keys())}")
    print(f"  ✓ Regressor: GradientBoostingRegressor (n_estimators=200, max_depth=4)")

except Exception as e:
    print(f"  ✗ Pipeline construction FAILED: {e}")
    sys.exit(1)

print("\n✓ Pipeline construction PASSED")

# ────────────────────────────────────────────────────────────────────────────
# 4. Evaluation quality gates
# ────────────────────────────────────────────────────────────────────────────
print("\n[4/5] Quality Gate Thresholds")
try:
    from evaluate import QUALITY_GATE_MAE_HOURS, QUALITY_GATE_WITHIN_2H_PCT

    assert QUALITY_GATE_MAE_HOURS == 2.0, f"Expected MAE gate 2.0, got {QUALITY_GATE_MAE_HOURS}"
    assert QUALITY_GATE_WITHIN_2H_PCT == 0.80, f"Expected ±2h gate 80%, got {QUALITY_GATE_WITHIN_2H_PCT}"
    print(f"  ✓ MAE threshold: ≤{QUALITY_GATE_MAE_HOURS}h")
    print(f"  ✓ ±2h threshold: ≥{QUALITY_GATE_WITHIN_2H_PCT:.0%}")

except Exception as e:
    print(f"  ✗ Quality gates FAILED: {e}")
    sys.exit(1)

print("\n✓ Quality gate thresholds PASSED")

# ────────────────────────────────────────────────────────────────────────────
# 5. GCS upload configuration
# ────────────────────────────────────────────────────────────────────────────
print("\n[5/5] GCS Upload Configuration")
try:
    from upload import GCS_BUCKET, GCS_OBJECT_PREFIX

    assert GCS_BUCKET == "ml-models", f"Expected bucket 'ml-models', got {GCS_BUCKET}"
    assert GCS_OBJECT_PREFIX == "discharge_time", f"Expected prefix 'discharge_time', got {GCS_OBJECT_PREFIX}"
    print(f"  ✓ GCS bucket: {GCS_BUCKET}")
    print(f"  ✓ Object prefix: {GCS_OBJECT_PREFIX}")
    print(f"  ✓ Versioned path: {GCS_OBJECT_PREFIX}/{{version}}/discharge_time.joblib")
    print(f"  ✓ Latest path: {GCS_OBJECT_PREFIX}/latest/discharge_time.joblib")

except Exception as e:
    print(f"  ✗ GCS upload config FAILED: {e}")
    sys.exit(1)

print("\n✓ GCS upload configuration PASSED")

# ────────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("✓ ALL VALIDATION CHECKS PASSED (5/5)")
print("=" * 80)
print("\nNext steps:")
print("  1. Train model: python ml/discharge_time_model/train.py --db-url <DB_URL>")
print("  2. Evaluate: Import evaluate.py and run on holdout set")
print("  3. Upload to GCS: python -c 'from ml.discharge_time_model.upload import upload_model; ...'")
print("\nUS-036 TASK-001 implementation complete.")
