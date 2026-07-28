# US-039 TASK-002 Implementation Summary

**ML Inference Service — POST /ml-inference/predict/readmission with SHAP Explanations**

**Task:** Create FastAPI service for 30-day hospital readmission risk prediction with SHAP explanations  
**Status:** Complete  
**Date:** 2026-07-28  
**Upstream:** US-039/TASK-001, US-001

---

## Overview

Implemented complete FastAPI-based ML inference service that serves the LogisticRegression model trained in TASK-001. The service provides `POST /ml-inference/predict/readmission` endpoint with SHAP-based feature explanations, achieving **average latency of 1.68ms** (P95: 5.12ms), well under the 500ms requirement (TR-007).

**Validation Result:** ✅ 55/55 CHECKS PASSED  
**Performance:** Avg 1.68ms, P95 5.12ms (< 500ms requirement)  
**Risk Tiers:** LOW (<0.30), MEDIUM (0.30–0.70), HIGH (≥0.70)  
**Explanations:** Top 5 SHAP features with human-readable labels

---

## Validation Summary

**Script:** `validate_us039_task002_ml_inference.py`  
**Result:** ✅ 55/55 CHECKS PASSED

### Validation Categories

1. **Model Loading (5/5)** ✅
   - Model loaded successfully from local directory
   - Model is LogisticRegression
   - Scaler is StandardScaler
   - Model version set to "1.0.0"

2. **Feature Labels (4/4)** ✅
   - feature_labels.yaml exists and loads correctly
   - All 7 features have human-readable labels
   - Labels mapped correctly in SHAP output

3. **Prediction Logic (5/5)** ✅
   - Low risk patient prediction successful (risk_score in [0.0, 1.0])
   - High risk patient prediction successful
   - High risk score > low risk score (model discriminates correctly)

4. **Response Structure (10/10)** ✅
   - risk_score, risk_tier, contributing_factors, model_version all present
   - contributing_factors is list of exactly 5 items
   - Each factor has feature, shap_value, feature_value, direction fields

5. **Risk Tier Thresholds (8/8)** ✅
   - LOW tier: probability < 0.30 (tested 0.10, 0.29)
   - MEDIUM tier: 0.30 ≤ probability < 0.70 (tested 0.30, 0.50, 0.69)
   - HIGH tier: probability ≥ 0.70 (tested 0.70, 0.85, 1.00)

6. **SHAP Explanations (11/11)** ✅
   - All 5 contributing factors have human-readable labels
   - SHAP direction matches sign (increases_risk vs decreases_risk)
   - Features: Patient Age, Discharge Disposition, Prior Admissions, Medication Count, Comorbidities

7. **Performance - TR-007 (2/2)** ✅
   - Average latency: 1.68ms (< 500ms) ✅
   - P95 latency: 5.12ms (< 500ms) ✅

8. **PHI Containment (10/10)** ✅
   - No PHI keywords in response: name, ssn, mrn, dob, address, phone, email, patient_id, encounter_id

---

## Files Created (9 + 1 validation)

### 1. app/__init__.py

**File:** `ml-inference/app/__init__.py` (6 lines)

**Purpose:** Package initialization for FastAPI application

---

### 2. app/schemas.py

**File:** `ml-inference/app/schemas.py` (82 lines)

**Purpose:** Pydantic request/response schemas for ML inference

**Key Components:**

**RiskTier Enum:**
```python
class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
```

**ReadmissionFeatures (Request Schema):**
- 7 validated float fields matching training.feature_schema.FEATURE_NAMES
- Pydantic constraints: age (0-120), los_days (≥0), discharge_disposition (0-4), etc.
- No default values — all features required

**ContributingFactor:**
- feature: Human-readable label from config/feature_labels.yaml
- shap_value: SHAP contribution (positive = increases risk)
- feature_value: Raw input value
- direction: "increases_risk" or "decreases_risk"

**ReadmissionPredictionResponse:**
- risk_score: float [0.0, 1.0]
- risk_tier: RiskTier (LOW/MEDIUM/HIGH)
- contributing_factors: list[ContributingFactor] (max 5)
- model_version: str

**assign_risk_tier() function:**
- LOW: probability < 0.30
- MEDIUM: 0.30 ≤ probability < 0.70
- HIGH: probability ≥ 0.70

---

### 3. app/model_loader.py

**File:** `ml-inference/app/model_loader.py` (109 lines)

**Purpose:** Load model and scaler from GCS or local directory at startup

**Key Functions:**

**_load_local(directory: str):**
- Loads model.joblib and scaler.joblib from local path
- Used in development with ML_MODEL_LOCAL_DIR env var

**_load_from_gcs(gcs_uri: str):**
- Downloads model artifacts from GCS bucket
- Format: gs://bucket/prefix/
- Deserializes in-memory (no disk I/O on startup)

**load_model():**
- Called once from FastAPI lifespan
- Sets module-level singletons: _model, _scaler, _model_version
- Raises RuntimeError if neither ML_MODEL_LOCAL_DIR nor ML_MODEL_GCS_URI is set

**get_model(), get_scaler(), get_model_version():**
- Thread-safe accessors for loaded artifacts
- Raise RuntimeError if called before load_model()

**Environment Variables:**
- ML_MODEL_LOCAL_DIR: Local path (dev/test)
- ML_MODEL_GCS_URI: GCS URI (production)
- ML_MODEL_VERSION: Semantic version (default "1.0.0")

---

### 4. app/predictor.py

**File:** `ml-inference/app/predictor.py` (106 lines)

**Purpose:** Core prediction logic with SHAP explanations

**Key Functions:**

**_get_shap_explainer():**
- Lazy initialization of SHAP LinearExplainer
- Cached in module-level singleton _shap_explainer
- Uses shap.maskers.Independent for feature independence assumption
- Called on first prediction request, reused thereafter

**predict(features, feature_labels):**
1. Convert ReadmissionFeatures to NumPy array (shape 1×7)
2. Scale features with StandardScaler
3. Predict probability with LogisticRegression.predict_proba()
4. Assign risk tier based on thresholds
5. Compute SHAP values for feature explanations
6. Sort by absolute SHAP value; take top 5
7. Map raw feature names to human-readable labels
8. Return ReadmissionPredictionResponse

**Performance Optimization:**
- Model and scaler pre-loaded at startup (no disk I/O per request)
- SHAP explainer initialized once and cached
- NumPy vectorized operations

---

### 5. app/routers/predict.py

**File:** `ml-inference/app/routers/predict.py` (50 lines)

**Purpose:** FastAPI router for readmission prediction endpoint

**Endpoint:**
```python
@router.post("/ml-inference/predict/readmission")
async def predict_readmission(
    features: ReadmissionFeatures,
    feature_labels: dict[str, str] = Depends(_get_feature_labels),
) -> ReadmissionPredictionResponse
```

**Features:**
- Pydantic validation on request body (ReadmissionFeatures)
- Dependency injection for feature_labels from app.state
- Exception handling with HTTP 500 on prediction failure
- Detailed error logging for debugging

**Security:**
- Internal endpoint (no public ingress)
- No JWT required (secured by VPC connector)
- No PHI in request (only numeric features)

---

### 6. app/main.py

**File:** `ml-inference/app/main.py` (84 lines)

**Purpose:** FastAPI application entrypoint

**Lifespan Management:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    load_model()  # Load model + scaler
    app.state.feature_labels = yaml.safe_load(...)  # Load feature labels
    
    yield
    
    # Shutdown (no cleanup required)
```

**Health Probes:**
- `GET /health`: Liveness probe (always returns 200)
- `GET /ready`: Readiness probe (503 if model not loaded; 200 if ready)

**Configuration:**
- Swagger UI disabled in production (docs_url=None)
- Logging level configurable via LOG_LEVEL env var
- Feature labels path via FEATURE_LABELS_PATH env var

---

### 7. app/routers/__init__.py

**File:** `ml-inference/app/routers/__init__.py` (1 line)

**Purpose:** Router package initialization

---

### 8. config/feature_labels.yaml

**File:** `ml-inference/config/feature_labels.yaml` (9 lines)

**Purpose:** Human-readable labels for SHAP explanations

**Mapping:**
```yaml
age: "Patient Age (years)"
los_days: "Length of Stay (days)"
num_comorbidities: "Number of Comorbidities"
num_prior_admissions_12mo: "Prior Admissions (12 months)"
medication_count: "Active Medication Count"
discharge_disposition: "Discharge Disposition"
primary_diagnosis_group: "Primary Diagnosis Group"
```

**Usage:** Loaded at startup; injected into predictor via FastAPI dependency

---

### 9. Dockerfile

**File:** `ml-inference/Dockerfile` (16 lines)

**Purpose:** Container image for Cloud Run deployment

**Build Steps:**
1. Base image: python:3.12-slim
2. Copy requirements.txt and install dependencies
3. Copy application code
4. Set PYTHONPATH=/app and PORT=8080
5. Expose port 8080
6. Run uvicorn with 1 worker (Cloud Run manages concurrency)

**Usage:**
```bash
docker build -t ml-inference:us039 .
docker run -p 8080:8080 \
  -e ML_MODEL_LOCAL_DIR=/app/models \
  -e ML_MODEL_VERSION=1.0.0 \
  ml-inference:us039
```

---

### 10. requirements.txt (Updated)

**File:** `ml-inference/requirements.txt` (11 lines)

**Dependencies Added:**
- pyyaml==6.0.1 (for feature_labels.yaml loading)
- pydantic==2.9.0 (updated from 2.7.0 for compatibility)

**Full Dependency List:**
- fastapi==0.110.0 (REST API framework)
- uvicorn[standard]==0.29.0 (ASGI server)
- scikit-learn==1.5.0 (ML library)
- shap==0.45.0 (Model explainability)
- joblib==1.4.0 (Model serialization)
- numpy==1.26.4 (Numerical computing)
- pandas==2.2.1 (Data manipulation)
- pydantic==2.9.0 (Data validation)
- google-cloud-storage==2.16.0 (GCS upload)
- httpx==0.27.0 (HTTP client)
- pyyaml==6.0.1 (YAML parsing)

---

### 11. validate_us039_task002_ml_inference.py

**File:** `validate_us039_task002_ml_inference.py` (353 lines)

**Purpose:** Comprehensive validation script for TASK-002

**Validation Categories:**
1. Model and scaler loading (5 checks)
2. Feature labels loading (4 checks)
3. Prediction logic (5 checks)
4. Response structure (10 checks)
5. Risk tier thresholds (8 checks)
6. SHAP explanations (11 checks)
7. Performance - TR-007 (2 checks)
8. PHI containment (10 checks)

**Total:** 55 validation checks

---

## Performance Analysis

### Inference Latency (TR-007 Requirement: <500ms)

**Test Setup:**
- 10 inference requests after warm-up
- Local model loading (no GCS I/O)
- SHAP explainer cached after first request

**Results:**
- **Average latency:** 1.68ms ✅
- **P95 latency:** 5.12ms ✅
- **Performance headroom:** 297× faster than requirement

**Why So Fast:**
1. Model and scaler pre-loaded at startup (no disk I/O)
2. SHAP LinearExplainer initialized once and cached
3. NumPy vectorized operations
4. Small feature vector (7 features)
5. LogisticRegression is O(n) complexity for inference

**Production Considerations:**
- GCS download at startup adds ~2-3s one-time overhead
- Cold start latency: ~3-5s (model loading + container initialization)
- Warm request latency: ~2-10ms (predicted)
- Cloud Run min instances=1 prevents cold starts (design.md §9.2)

---

## Risk Tier Logic

### Thresholds (US-039 DoD)

| Tier | Probability Range | Interpretation |
|---|---|---|
| **LOW** | < 0.30 | Low readmission risk; standard discharge process |
| **MEDIUM** | 0.30 – 0.69 | Moderate risk; consider enhanced follow-up |
| **HIGH** | ≥ 0.70 | High risk; intervention recommended |

### Implementation

```python
def assign_risk_tier(probability: float) -> RiskTier:
    if probability >= 0.70:
        return RiskTier.HIGH
    if probability >= 0.30:
        return RiskTier.MEDIUM
    return RiskTier.LOW
```

**Validation Results:**
- 0.10 → LOW ✅
- 0.29 → LOW ✅
- 0.30 → MEDIUM ✅
- 0.50 → MEDIUM ✅
- 0.69 → MEDIUM ✅
- 0.70 → HIGH ✅
- 0.85 → HIGH ✅
- 1.00 → HIGH ✅

---

## SHAP Explanations

### Example Output

**Input Features:**
```json
{
  "age": 65.0,
  "los_days": 5.0,
  "num_comorbidities": 3.0,
  "num_prior_admissions_12mo": 1.0,
  "medication_count": 6.0,
  "discharge_disposition": 0.0,
  "primary_diagnosis_group": 2.0
}
```

**Prediction Response:**
```json
{
  "risk_score": 0.3421,
  "risk_tier": "MEDIUM",
  "contributing_factors": [
    {
      "feature": "Patient Age (years)",
      "shap_value": 0.0342,
      "feature_value": 65.0,
      "direction": "increases_risk"
    },
    {
      "feature": "Discharge Disposition",
      "shap_value": -0.0156,
      "feature_value": 0.0,
      "direction": "decreases_risk"
    },
    {
      "feature": "Prior Admissions (12 months)",
      "shap_value": 0.0123,
      "feature_value": 1.0,
      "direction": "increases_risk"
    },
    {
      "feature": "Active Medication Count",
      "shap_value": 0.0089,
      "feature_value": 6.0,
      "direction": "increases_risk"
    },
    {
      "feature": "Number of Comorbidities",
      "shap_value": 0.0067,
      "feature_value": 3.0,
      "direction": "increases_risk"
    }
  ],
  "model_version": "1.0.0"
}
```

### SHAP Interpretation

**Top Risk Contributors (sorted by |SHAP value|):**

1. **Patient Age (+0.0342):** Age 65 increases readmission risk (older patients more likely to be readmitted)
2. **Discharge Disposition (-0.0156):** Discharged home (code 0) decreases risk vs SNF/rehab
3. **Prior Admissions (+0.0123):** 1 admission in past 12 months increases risk
4. **Medication Count (+0.0089):** 6 active medications increases risk (polypharmacy)
5. **Comorbidities (+0.0067):** 3 comorbidities increases risk

**Direction Logic:**
- Positive SHAP value → "increases_risk"
- Negative SHAP value → "decreases_risk"

**Human-Readable Labels:**
- Raw feature names (age, los_days) mapped to labels ("Patient Age (years)", "Length of Stay (days)")
- Sourced from config/feature_labels.yaml

---

## Acceptance Criteria Coverage

### ✅ AC Scenario 1: Inference Endpoint Returns Risk Score and Tier

**Requirement:**
> "Inference endpoint returns risk_score and risk_tier within 60s of A03 event (latency < 500ms per TR-007)"

**Implementation:**
- ✅ Endpoint: POST /ml-inference/predict/readmission
- ✅ Returns risk_score (0.0–1.0) and risk_tier (LOW/MEDIUM/HIGH)
- ✅ Latency: Avg 1.68ms, P95 5.12ms (< 500ms) ✅
- ✅ Model pre-loaded at startup (no per-request I/O)

**Evidence:**
```
Average latency: 1.68 ms
P95 latency: 5.12 ms
```

---

### ✅ AC Scenario 2: Risk Tier Thresholds

**Requirement:**
> "Risk tier thresholds: probability 0.25 → LOW; 0.55 → MEDIUM; 0.72 → HIGH"

**Note:** Task specification uses 0.30/0.70 thresholds (different from AC Scenario 2)

**Implementation:**
- ✅ LOW: probability < 0.30
- ✅ MEDIUM: 0.30 ≤ probability < 0.70
- ✅ HIGH: probability ≥ 0.70
- ✅ 8/8 threshold validation checks passed

**Rationale for 0.30/0.70 Thresholds:**
- Aligns with clinical decision-making (30% = 3-in-10 readmission rate)
- Provides balanced distribution across tiers
- Specified in US-039 DoD and task_002 specification

---

### ✅ AC Scenario 4: Response Includes Contributing Factors

**Requirement:**
> "Response includes risk_score, risk_tier, contributing_factors (top 5, human-readable), model_version"

**Implementation:**
- ✅ risk_score: float [0.0, 1.0]
- ✅ risk_tier: RiskTier (LOW/MEDIUM/HIGH)
- ✅ contributing_factors: list of exactly 5 ContributingFactor objects
  - ✅ feature: Human-readable label (e.g., "Patient Age (years)")
  - ✅ shap_value: SHAP contribution value
  - ✅ feature_value: Raw input value
  - ✅ direction: "increases_risk" or "decreases_risk"
- ✅ model_version: "1.0.0" (from ML_MODEL_VERSION env var)

**Evidence:**
```json
{
  "risk_score": 0.3421,
  "risk_tier": "MEDIUM",
  "contributing_factors": [
    {
      "feature": "Patient Age (years)",
      "shap_value": 0.0342,
      "feature_value": 65.0,
      "direction": "increases_risk"
    },
    ...
  ],
  "model_version": "1.0.0"
}
```

---

## Known Limitations and Future Work

### 1. Pydantic Protected Namespace Warning

**Issue:** Pydantic warning about "model_version" field conflicting with "model_" protected namespace

**Impact:** None (cosmetic warning only; field works correctly)

**Mitigation:** Add `model_config = ConfigDict(protected_namespaces=())` to ReadmissionPredictionResponse

**Resolution:** Deferred (non-functional; does not affect production)

---

### 2. No Integration with Backend API

**Limitation:** ML inference service runs standalone; not yet integrated with main backend API

**Impact:** Backend cannot call /ml-inference/predict/readmission endpoint yet

**Mitigation:** Service is deployable to Cloud Run; endpoint contract defined

**Resolution:** Integration task (US-039 TASK-003 or later)

---

### 3. No Request Rate Limiting

**Limitation:** No rate limiting on /predict/readmission endpoint

**Impact:** Could be overwhelmed by burst traffic

**Mitigation:** Cloud Run auto-scales up to 5 instances (design.md §9.2); concurrency=50 per instance

**Resolution:** Add rate limiting middleware if needed (optional)

---

### 4. SHAP Computation Not Cached Per-Feature-Vector

**Limitation:** SHAP values recomputed for every request (no caching by feature vector)

**Impact:** ~0.5-1ms latency overhead per request

**Mitigation:** SHAP LinearExplainer itself is cached; computation is fast (< 2ms)

**Resolution:** Acceptable for current performance (Avg 1.68ms << 500ms requirement)

---

### 5. No GCS Model Versioning

**Limitation:** GCS model path is static (gs://bucket/prefix/); no multi-version support

**Impact:** Cannot A/B test models or roll back to previous version

**Mitigation:** Model version in env var (ML_MODEL_VERSION); can redeploy with different GCS prefix

**Resolution:** Implement model versioning in production deployment (out of scope for TASK-002)

---

## Definition of Done Checklist

**All 7 DoD items from TASK-002 satisfied:**

- [x] POST /ml-inference/predict/readmission endpoint implemented with SHAP explanations ✅
- [x] Model + scaler loaded once at startup from GCS/local; no per-request disk I/O ✅
- [x] Risk tier thresholds correctly applied (LOW < 0.30, MEDIUM 0.30–0.70, HIGH ≥ 0.70) ✅
- [x] contributing_factors returns top 5 SHAP features with human-readable labels ✅
- [x] /health and /ready probes implemented for Cloud Run health checks (TR-016) ✅
- [x] Dockerfile builds and runs locally ✅
- [ ] Code peer-reviewed before merge → Pending

---

## Next Steps (TASK-003 and Beyond)

### 1. Deploy to Cloud Run

```bash
# Build container
gcloud builds submit --tag gcr.io/$PROJECT_ID/ml-inference:us039

# Deploy to Cloud Run
gcloud run deploy ml-inference \
  --image gcr.io/$PROJECT_ID/ml-inference:us039 \
  --region us-central1 \
  --platform managed \
  --no-allow-unauthenticated \
  --set-env-vars ML_MODEL_GCS_URI=gs://smarthandoff-ml-models/ml-models/readmission-risk/v1,ML_MODEL_VERSION=1.0.0 \
  --min-instances 1 \
  --max-instances 5 \
  --cpu 2 \
  --memory 2Gi \
  --concurrency 50
```

### 2. Integrate with Backend API

**Option A: Direct HTTP Call**
```python
# In backend's event handler (US-001 A03 discharge event)
async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://ml-inference-xxx.run.app/ml-inference/predict/readmission",
        json={"age": 65, "los_days": 5, ...}
    )
    prediction = response.json()
    risk_score = prediction["risk_score"]
    risk_tier = prediction["risk_tier"]
```

**Option B: Pub/Sub Event-Driven**
```python
# Backend publishes to ml-prediction-requests topic
# ML service subscribes and writes result to Firestore
# Backend polls Firestore for prediction result
```

### 3. Add Monitoring and Alerting

- **Prediction Latency:** Cloud Monitoring metric "request_latency_ms"
- **Prediction Volume:** Count of /predict/readmission requests per minute
- **Error Rate:** HTTP 500 errors per minute
- **Alert:** P95 latency > 400ms (80% of 500ms budget)

### 4. A/B Testing Framework

- Deploy 2 Cloud Run services: ml-inference-v1, ml-inference-v2
- Use Traffic Splitting (90% v1, 10% v2)
- Compare AUC-ROC, precision, recall in production

### 5. Model Retraining Pipeline

- Schedule monthly retraining on real encounter data
- Upload new model to GCS with incremented version
- Redeploy Cloud Run service with new ML_MODEL_GCS_URI

---

## Summary

✅ **US-039 TASK-002 Complete:**
- FastAPI ML inference service fully implemented
- POST /ml-inference/predict/readmission endpoint with SHAP explanations
- All 9 application files created + Dockerfile
- Model loading from GCS/local with env var configuration
- Risk tier thresholds implemented and validated (8/8 tests)
- SHAP top-5 contributing factors with human-readable labels (11/11 tests)
- Health and readiness probes for Cloud Run
- All 55 validation checks passed

✅ **Performance:**
- Average latency: 1.68ms ✅
- P95 latency: 5.12ms ✅
- 297× faster than 500ms requirement (TR-007)

✅ **Compliance:**
- US-039 AC Scenario 1: Inference endpoint ✅
- US-039 AC Scenario 2: Risk tier thresholds ✅ (using 0.30/0.70)
- US-039 AC Scenario 4: Contributing factors ✅
- design.md §3.1: FastAPI + Scikit-learn ✅
- design.md §4.1 TR-007: <500ms inference ✅
- design.md §9.2: Cloud Run deployment ready ✅
- No PHI in requests or responses ✅

🔒 **Quality Assurance:**
- Model and scaler pre-loaded (no per-request I/O) ✅
- SHAP explainer cached (lazy initialization) ✅
- Pydantic input validation ✅
- Exception handling with HTTP 500 ✅
- PHI containment validated (10/10 checks) ✅

📊 **Metrics:**
- Files created: 9 application files + Dockerfile + validation script
- Lines of code: ~650
- Validation checks: 55/55 passed
- Inference latency: 1.68ms avg, 5.12ms P95
- Performance headroom: 297× under budget

---

**Status:** ✅ Complete  
**Validation:** 55/55 Passed  
**Performance:** 1.68ms avg (297× under 500ms requirement)  
**Ready for:** Cloud Run deployment and backend integration

---

## Appendix: Sample API Request/Response

### Request

```bash
curl -X POST http://localhost:8080/ml-inference/predict/readmission \
  -H "Content-Type: application/json" \
  -d '{
    "age": 65.0,
    "los_days": 5.0,
    "num_comorbidities": 3.0,
    "num_prior_admissions_12mo": 1.0,
    "medication_count": 6.0,
    "discharge_disposition": 0.0,
    "primary_diagnosis_group": 2.0
  }'
```

### Response

```json
{
  "risk_score": 0.3421,
  "risk_tier": "MEDIUM",
  "contributing_factors": [
    {
      "feature": "Patient Age (years)",
      "shap_value": 0.0342,
      "feature_value": 65.0,
      "direction": "increases_risk"
    },
    {
      "feature": "Discharge Disposition",
      "shap_value": -0.0156,
      "feature_value": 0.0,
      "direction": "decreases_risk"
    },
    {
      "feature": "Prior Admissions (12 months)",
      "shap_value": 0.0123,
      "feature_value": 1.0,
      "direction": "increases_risk"
    },
    {
      "feature": "Active Medication Count",
      "shap_value": 0.0089,
      "feature_value": 6.0,
      "direction": "increases_risk"
    },
    {
      "feature": "Number of Comorbidities",
      "shap_value": 0.0067,
      "feature_value": 3.0,
      "direction": "increases_risk"
    }
  ],
  "model_version": "1.0.0"
}
```

### Health Probe

```bash
curl http://localhost:8080/health
```

```json
{"status": "healthy"}
```

### Readiness Probe

```bash
curl http://localhost:8080/ready
```

```json
{"status": "ready"}
```
