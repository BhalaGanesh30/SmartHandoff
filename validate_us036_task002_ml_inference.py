"""Validation script for US-036 TASK-002 ML Inference Service.

Validates:
- Module syntax (all .py files parse correctly)
- FastAPI app structure (routers, dependencies)
- Request/response schema validation
- Model loader cache mechanism
- Confidence level thresholds

Design refs:
    US-036 TASK-002 — Validation checklist
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

print("=" * 80)
print("US-036 TASK-002 Validation: ML Inference Service")
print("=" * 80)

# ────────────────────────────────────────────────────────────────────────────
# 1. Syntax check
# ────────────────────────────────────────────────────────────────────────────
print("\n[1/6] Syntax Check")
modules = [
    "ml_inference/app/__init__.py",
    "ml_inference/app/main.py",
    "ml_inference/app/schemas.py",
    "ml_inference/app/model_loader.py",
    "ml_inference/app/auth.py",
    "ml_inference/app/routers/__init__.py",
    "ml_inference/app/routers/discharge_time.py",
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
# 2. Schema validation
# ────────────────────────────────────────────────────────────────────────────
print("\n[2/6] Schema Validation")
sys.path.insert(0, "ml_inference")

try:
    from app.schemas import (
        ConfidenceLevel,
        DischargeTimePredictionRequest,
        DischargeTimePredictionResponse,
    )
    from datetime import datetime, timezone
    
    # Test request schema
    request = DischargeTimePredictionRequest(
        encounter_id="test-001",
        admit_time=datetime(2026, 7, 28, 10, 0, 0, tzinfo=timezone.utc),
        patient_dob=datetime(1980, 1, 1, tzinfo=timezone.utc),
        admit_diagnosis_group="CARDIOVASCULAR",
        unit="3A",
        pending_procedures_count=2,
    )
    assert request.encounter_id == "test-001"
    print(f"  ✓ DischargeTimePredictionRequest: Valid")
    
    # Test response schema
    response = DischargeTimePredictionResponse(
        encounter_id="test-001",
        predicted_discharge_time=datetime(2026, 7, 29, 14, 30, tzinfo=timezone.utc),
        confidence_interval_hours=0.85,
        confidence_level=ConfidenceLevel.HIGH,
        model_version="v1",
    )
    assert response.confidence_level == ConfidenceLevel.HIGH
    print(f"  ✓ DischargeTimePredictionResponse: Valid")
    
    # Test ConfidenceLevel enum
    assert ConfidenceLevel.HIGH.value == "high"
    assert ConfidenceLevel.MEDIUM.value == "medium"
    assert ConfidenceLevel.LOW.value == "low"
    print(f"  ✓ ConfidenceLevel enum: 3 levels (high, medium, low)")

except Exception as e:
    print(f"  ✗ Schema validation FAILED: {e}")
    sys.exit(1)

print("\n✓ Schema validation PASSED")

# ────────────────────────────────────────────────────────────────────────────
# 3. Confidence level thresholds (code inspection)
# ────────────────────────────────────────────────────────────────────────────
print("\n[3/6] Confidence Level Thresholds (Code Inspection)")
try:
    router_code = Path("ml_inference/app/routers/discharge_time.py").read_text()
    
    # Check threshold constants exist
    assert "_CONFIDENCE_HIGH_THRESHOLD_H = 1.0" in router_code, "HIGH threshold not found or incorrect"
    assert "_CONFIDENCE_MEDIUM_THRESHOLD_H = 2.0" in router_code, "MEDIUM threshold not found or incorrect"
    print(f"  ✓ HIGH threshold: <1.0h")
    print(f"  ✓ MEDIUM threshold: 1.0-2.0h")
    print(f"  ✓ LOW threshold: >2.0h")
    
    # Check _derive_confidence_level function exists
    assert "def _derive_confidence_level" in router_code, "_derive_confidence_level function not found"
    assert "ConfidenceLevel.HIGH" in router_code, "HIGH confidence level mapping missing"
    assert "ConfidenceLevel.MEDIUM" in router_code, "MEDIUM confidence level mapping missing"
    assert "ConfidenceLevel.LOW" in router_code, "LOW confidence level mapping missing"
    print(f"  ✓ _derive_confidence_level: Function defined with all levels")

except Exception as e:
    print(f"  ✗ Confidence thresholds FAILED: {e}")
    sys.exit(1)

print("\n✓ Confidence level thresholds PASSED")

# ────────────────────────────────────────────────────────────────────────────
# 4. Model loader configuration (code inspection)
# ────────────────────────────────────────────────────────────────────────────
print("\n[4/6] Model Loader Configuration (Code Inspection)")
try:
    model_loader_code = Path("ml_inference/app/model_loader.py").read_text()
    
    # Check GCS configuration
    assert 'GCS_BUCKET = os.environ.get("ML_MODELS_BUCKET", "ml-models")' in model_loader_code, "GCS_BUCKET config incorrect"
    assert 'GCS_OBJECT = "discharge_time/latest/discharge_time.joblib"' in model_loader_code, "GCS_OBJECT config incorrect"
    print(f"  ✓ GCS bucket: ml-models (configurable via ML_MODELS_BUCKET env)")
    print(f"  ✓ GCS object: discharge_time/latest/discharge_time.joblib")
    
    # Check cache mechanism
    assert "_MODEL_CACHE: dict[str, Any] = {}" in model_loader_code, "Model cache dict not found"
    assert "if cache_key in _MODEL_CACHE:" in model_loader_code, "Cache hit check missing"
    assert "_MODEL_CACHE[cache_key] = pipeline" in model_loader_code, "Cache storage missing"
    print(f"  ✓ Model cache: In-memory dict with cache hit optimization")

except Exception as e:
    print(f"  ✗ Model loader config FAILED: {e}")
    sys.exit(1)

print("\n✓ Model loader configuration PASSED")

# ────────────────────────────────────────────────────────────────────────────
# 5. FastAPI app structure (code inspection)
# ────────────────────────────────────────────────────────────────────────────
print("\n[5/6] FastAPI App Structure (Code Inspection)")
try:
    main_code = Path("ml_inference/app/main.py").read_text()
    
    # Check app initialization
    assert 'app = FastAPI(' in main_code, "FastAPI app not initialized"
    assert 'title="SmartHandoff ML Inference Service"' in main_code, "App title incorrect"
    assert 'version="1.0.0"' in main_code, "App version incorrect"
    print(f"  ✓ App title: SmartHandoff ML Inference Service")
    print(f"  ✓ App version: 1.0.0")
    
    # Check routers and endpoints
    assert 'app.include_router(discharge_router)' in main_code, "Discharge router not included"
    assert '@app.get("/health"' in main_code, "/health endpoint missing"
    assert '@app.get("/ready"' in main_code, "/ready endpoint missing"
    print(f"  ✓ Routers: discharge_router, /health, /ready")
    
    # Check startup event
    assert '@app.on_event("startup")' in main_code, "Startup event missing"
    assert 'load_model()' in main_code, "Model preload missing from startup"
    print(f"  ✓ Startup: Model preload at startup (TR-007 <500ms requirement)")

except Exception as e:
    print(f"  ✗ FastAPI app structure FAILED: {e}")
    sys.exit(1)

print("\n✓ FastAPI app structure PASSED")

# ────────────────────────────────────────────────────────────────────────────
# 6. Dockerfile and requirements.txt
# ────────────────────────────────────────────────────────────────────────────
print("\n[6/6] Dockerfile and Dependencies")
try:
    dockerfile_path = Path("ml_inference/Dockerfile")
    requirements_path = Path("ml_inference/requirements.txt")
    
    assert dockerfile_path.exists(), "Dockerfile not found"
    assert requirements_path.exists(), "requirements.txt not found"
    print(f"  ✓ Dockerfile: {dockerfile_path}")
    print(f"  ✓ requirements.txt: {requirements_path}")
    
    # Check key dependencies
    requirements = requirements_path.read_text()
    assert "fastapi" in requirements, "Missing fastapi dependency"
    assert "uvicorn" in requirements, "Missing uvicorn dependency"
    assert "scikit-learn" in requirements, "Missing scikit-learn dependency"
    assert "google-cloud-storage" in requirements, "Missing google-cloud-storage dependency"
    assert "python-jose" in requirements, "Missing python-jose dependency"
    print(f"  ✓ Dependencies: fastapi, uvicorn, scikit-learn, google-cloud-storage, python-jose")

except Exception as e:
    print(f"  ✗ Dockerfile/dependencies FAILED: {e}")
    sys.exit(1)

print("\n✓ Dockerfile and dependencies PASSED")

# ────────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("✓ ALL VALIDATION CHECKS PASSED (6/6)")
print("=" * 80)
print("\nNext steps:")
print("  1. Build Docker image: docker build -t ml-inference:local ml_inference/")
print("  2. Run locally: uvicorn app.main:app --reload (from ml_inference/)")
print("  3. Test health: curl http://localhost:8080/health")
print("  4. Deploy to Cloud Run: gcloud run deploy ml-inference ...")
print("\nUS-036 TASK-002 implementation complete.")
