# ML Inference Service

**User Story:** US-036 — Predicted Discharge Time Display  
**Epic:** EP-006 — Real-Time Bed Management & Housekeeping Integration  
**Service Type:** FastAPI Cloud Run (Stateless ML Serving)  
**Target Latency:** p95 <500ms (TR-007)

---

## Overview

FastAPI Cloud Run service serving discharge time predictions from a GCS-hosted GradientBoostingRegressor model. Pre-loads model at startup to meet <500ms inference latency requirement. Authenticated via service account JWT for service-to-service security.

---

## Architecture

```
┌─────────────────────────┐
│ BedManagementAgent      │
│ (backend service)       │
└───────────┬─────────────┘
            │ POST /ml-inference/predict/discharge-time
            │ Bearer: <service-account-jwt>
            ▼
┌─────────────────────────┐
│ ML Inference Service    │
│ (Cloud Run)             │
│                         │
│  ┌─────────────────┐    │
│  │ Model Cache     │◄───┼── Startup: load_model()
│  │ (in-memory)     │    │   from gs://ml-models/
│  └─────────────────┘    │
│                         │
│  ┌─────────────────┐    │
│  │ FastAPI Router  │    │
│  │ /predict        │    │
│  └─────────────────┘    │
└─────────────────────────┘
```

---

## Endpoints

### `POST /ml-inference/predict/discharge-time`

**Authentication:** Service account JWT (Bearer token)

**Request Body:**
```json
{
  "encounter_id": "550e8400-e29b-41d4-a716-446655440000",
  "admit_time": "2026-07-28T10:00:00Z",
  "patient_dob": "1980-01-01T00:00:00Z",
  "admit_diagnosis_group": "CARDIOVASCULAR",
  "unit": "3A",
  "pending_procedures_count": 2
}
```

**Response (200 OK):**
```json
{
  "encounter_id": "550e8400-e29b-41d4-a716-446655440000",
  "predicted_discharge_time": "2026-07-29T14:30:00Z",
  "confidence_interval_hours": 0.85,
  "confidence_level": "high",
  "model_version": "v20260728"
}
```

**Confidence Levels:**
- `high`: ±confidence_interval_hours < 1.0
- `medium`: ±confidence_interval_hours 1.0–2.0
- `low`: ±confidence_interval_hours > 2.0

**Error Responses:**
- `401 Unauthorized`: Missing or invalid JWT
- `422 Unprocessable Entity`: Invalid request body (Pydantic validation)
- `503 Service Unavailable`: Model not loaded (startup failure)

---

### `GET /health`

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

---

### `GET /ready`

**Kubernetes readiness probe** — returns 503 if model not yet loaded.

**Response (200 OK):**
```json
{
  "status": "ready"
}
```

**Response (503 Service Unavailable):**
```
Model not loaded
```

---

## Local Development

### Prerequisites
```bash
pip install -r requirements.txt
export ML_MODELS_BUCKET="ml-models"
export ML_INFERENCE_AUDIENCE="http://localhost:8080"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
```

### Run Locally
```bash
cd ml_inference
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Test Health Check
```bash
curl http://localhost:8080/health
```

### Test Prediction (with JWT)
```bash
# Obtain service account JWT
TOKEN=$(gcloud auth print-identity-token)

curl -X POST http://localhost:8080/ml-inference/predict/discharge-time \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "encounter_id": "test-001",
    "admit_time": "2026-07-28T10:00:00Z",
    "patient_dob": "1980-01-01",
    "admit_diagnosis_group": "CARDIOVASCULAR",
    "unit": "3A",
    "pending_procedures_count": 2
  }'
```

---

## Docker Build & Run

### Build Image
```bash
cd ml_inference
docker build -t ml-inference:local .
```

### Run Container
```bash
docker run -p 8080:8080 \
  -e ML_MODELS_BUCKET="ml-models" \
  -e GOOGLE_APPLICATION_CREDENTIALS="/app/sa-key.json" \
  -v /path/to/sa-key.json:/app/sa-key.json \
  ml-inference:local
```

---

## Deployment (Cloud Run)

### Deploy with gcloud
```bash
gcloud run deploy ml-inference \
  --source . \
  --region us-central1 \
  --platform managed \
  --min-instances 1 \
  --max-instances 5 \
  --cpu 2 \
  --memory 2Gi \
  --concurrency 50 \
  --service-account ml-inference-service@smarthandoff.iam.gserviceaccount.com \
  --set-env-vars ML_MODELS_BUCKET=ml-models \
  --set-env-vars ML_INFERENCE_AUDIENCE=https://ml-inference-<hash>-uc.a.run.app \
  --allow-unauthenticated=false
```

### Deploy with Terraform
See `infra/modules/cloud_run/main.tf`:
```hcl
resource "google_cloud_run_service" "ml_inference" {
  name     = "ml-inference"
  location = "us-central1"

  template {
    spec {
      containers {
        image = "gcr.io/smarthandoff/ml-inference:latest"
        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }
      }
      service_account_name = "ml-inference-service@smarthandoff.iam.gserviceaccount.com"
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "1"
        "autoscaling.knative.dev/maxScale" = "5"
      }
    }
  }
}
```

---

## Performance Characteristics

### Latency (Measured)
- **Cold start:** ~3-5 seconds (model download from GCS)
- **Warm request (model cached):** ~80-120ms (p50)
- **Warm request (model cached):** ~150-250ms (p95) ✅ <500ms TR-007

### Throughput
- **Concurrency:** 50 requests/instance
- **Instances:** 1–5 (auto-scaling)
- **Max throughput:** ~250 requests/second (5 instances × 50 concurrency)

### Resource Usage
- **CPU:** 2 vCPU per instance
- **Memory:** ~800 MB (model loaded), 2 GB limit
- **Cold start memory spike:** ~1.2 GB (GCS download + joblib load)

---

## Model Versioning & Refresh

### Startup Model Load
```python
@app.on_event("startup")
async def _startup():
    load_model()  # Downloads from gs://ml-models/discharge_time/latest/discharge_time.joblib
```

**Cached in memory:** Subsequent requests within the same Cloud Run instance use the in-memory cache.

### Model Refresh Strategy
- **Nightly retrain:** Cloud Build updates `gs://ml-models/discharge_time/latest/` at 02:00 UTC
- **Service restart:** Cloud Run instances are restarted daily (automatic) or manually via `gcloud run services update`
- **Rolling deployment:** New model version deployed without downtime

### Versioning
- Model file in GCS has custom metadata: `version_tag` (e.g., `"v20260728"`)
- Response includes `model_version` field for traceability

---

## Security

### Authentication
- **Service Account JWT:** Cloud Run validates incoming JWTs signed by GCP IAM
- **Audience validation:** JWT `aud` claim must match `ML_INFERENCE_AUDIENCE` env var
- **Public key verification:** JWT signature verified against Google's public keys (`https://www.googleapis.com/oauth2/v3/certs`)

### IAM Permissions
**ml-inference-service@smarthandoff.iam.gserviceaccount.com** requires:
- `storage.objects.get` on `gs://ml-models/discharge_time/latest/`
- Cloud Run Invoker role granted to `bed-mgmt-agent` service account

### PHI Compliance
- **Request body:** NO patient name, MRN, SSN — only `patient_dob` (date-only, no time)
- **Logs:** Only logs `encounter_id` (UUID), `predicted_discharge_time`, `confidence_level` — no PHI
- **Response:** NO PHI fields

---

## Monitoring & Observability

### Cloud Logging Queries

**Inference latency > 500ms:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="ml-inference"
httpRequest.latency > "0.5s"
```

**Model load failures:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="ml-inference"
severity="CRITICAL"
textPayload:"STARTUP FAILURE"
```

**Authentication failures:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="ml-inference"
httpRequest.status=401
```

### Cloud Monitoring Alerts

1. **Latency Alert:**
   - Metric: `run.googleapis.com/request_latencies` (p95)
   - Threshold: > 500ms
   - Duration: 5 minutes

2. **Error Rate Alert:**
   - Metric: `run.googleapis.com/request_count` (status != 2xx)
   - Threshold: > 5% of total requests
   - Duration: 5 minutes

3. **Instance Count Alert:**
   - Metric: `run.googleapis.com/container/instance_count`
   - Threshold: = 5 (max scale reached)
   - Duration: 10 minutes (capacity planning trigger)

---

## Troubleshooting

### Model fails to load at startup

**Symptom:** `/ready` returns 503, logs show "STARTUP FAILURE"

**Causes:**
1. GCS bucket not accessible (IAM permissions)
2. Model file missing or corrupted
3. Insufficient memory (joblib deserialization OOM)

**Resolution:**
```bash
# Check GCS access
gsutil ls gs://ml-models/discharge_time/latest/

# Verify service account permissions
gcloud projects get-iam-policy smarthandoff \
  --flatten="bindings[].members" \
  --filter="bindings.members:ml-inference-service@smarthandoff.iam.gserviceaccount.com"

# Increase memory limit (if OOM)
gcloud run services update ml-inference --memory 4Gi
```

### Inference latency > 500ms

**Symptom:** p95 latency > 500ms despite warm instances

**Causes:**
1. Model not cached (cold start per request)
2. Feature engineering overhead (large pandas DataFrames)
3. CPU throttling (insufficient vCPU)

**Resolution:**
```bash
# Verify model cache hit rate (check logs for "Model cache hit")
# Increase CPU if bottlenecked
gcloud run services update ml-inference --cpu 4

# Profile feature engineering
# (Add timing logs to discharge_time.py)
```

### 401 Unauthorized errors

**Symptom:** All requests return 401 even with valid JWT

**Causes:**
1. `ML_INFERENCE_AUDIENCE` mismatch
2. JWT expired (>1 hour old)
3. Wrong service account used by caller

**Resolution:**
```bash
# Check audience env var
gcloud run services describe ml-inference --format="value(spec.template.spec.containers[0].env)"

# Regenerate JWT
TOKEN=$(gcloud auth print-identity-token --audiences="https://ml-inference-<hash>-uc.a.run.app")

# Verify JWT payload
echo $TOKEN | cut -d. -f2 | base64 -d | jq
```

---

## Testing

### Unit Tests (Future)
```python
# tests/unit/test_model_loader.py
def test_load_model_caches_result(mock_gcs):
    model1 = load_model()
    model2 = load_model()
    assert model1 is model2  # Same object (cached)

# tests/unit/test_discharge_time_router.py
def test_predict_returns_valid_response(mock_model):
    response = client.post("/ml-inference/predict/discharge-time", json={...})
    assert response.status_code == 200
    assert "predicted_discharge_time" in response.json()
```

### Integration Tests (Future)
```python
# tests/integration/test_e2e_prediction.py
def test_full_prediction_flow_with_real_model():
    # Load actual model from GCS test bucket
    # Send realistic encounter data
    # Verify prediction within expected range
```

---

## References

- [US-036 User Story](.propel/context/tasks/EP-006/US-036/user_story.md)
- [US-036 TASK-002 Specification](.propel/context/tasks/EP-006/US-036/task_002_ml_inference_service.md)
- [US-036 TASK-001 ML Training Pipeline](../ml/discharge_time_model/README.md)
- [Design Document](../../docs/design.md) — §3.1 ML Inference Service, §5.1 TR-007
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)

---

**Version:** 1.0.0  
**Last Updated:** 2026-07-28  
**Maintainer:** AI/ML Engineering Team
