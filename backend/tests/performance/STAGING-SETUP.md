# Staging Environment Setup Guide for Performance Testing

This guide provides step-by-step instructions for configuring the staging environment to run TASK-007 performance tests.

---

## Prerequisites

- GCP project with Vertex AI API enabled
- Staging FHIR R4 server with OAuth 2.0 support
- Cloud SQL PostgreSQL instance (staging)
- `gcloud` CLI installed and authenticated
- Python 3.11+ with pytest installed

---

## 1. Enable Vertex AI API

```bash
# Set your staging project ID
export STAGING_PROJECT_ID="your-staging-project-id"

# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com \
    --project=${STAGING_PROJECT_ID}

# Verify API is enabled
gcloud services list --enabled \
    --project=${STAGING_PROJECT_ID} \
    --filter="name:aiplatform.googleapis.com"
```

---

## 2. Configure Vertex AI Quota

The performance test runs 10 concurrent Gemini API calls. Ensure your project has sufficient quota:

```bash
# Check current quota
gcloud alpha services quota list \
    --service=aiplatform.googleapis.com \
    --project=${STAGING_PROJECT_ID} \
    --filter="metric.name:aiplatform.googleapis.com/concurrent_requests"

# Request quota increase if needed (via Cloud Console)
# Navigate to: IAM & Admin > Quotas
# Search for: "Vertex AI Gemini concurrent requests"
# Request increase to at least: 10 concurrent requests
```

**Recommended Quota:**
- **Concurrent requests**: 10 minimum (50 recommended)
- **Requests per minute**: 300 minimum
- **Tokens per minute**: 1,000,000 minimum

---

## 3. Seed Staging FHIR Server

The performance test expects 100 test encounters with IDs `PERF-ENC-0001` through `PERF-ENC-0100`.

### Option A: Use Synthetic Data Script

```bash
cd backend/tests/performance/fixtures
python seed_staging_fhir.py \
    --fhir-url=${STAGING_FHIR_BASE_URL} \
    --client-id=${STAGING_FHIR_CLIENT_ID} \
    --client-secret=${STAGING_FHIR_CLIENT_SECRET} \
    --count=100
```

### Option B: Manual Seeding

Use the encounter factory to generate test data and POST to FHIR server:

```python
from tests.performance.fixtures.encounter_factory import build_test_encounters

encounters = build_test_encounters(count=100)
# POST each encounter to your FHIR server
```

**Required Resources per Encounter:**
- 1 × Patient resource
- 1 × Encounter resource (class: inpatient, status: finished)
- 1-8 × Condition resources (ICD-10 codes)
- 1-12 × MedicationStatement resources (RxNorm codes)

---

## 4. Configure Cloud SQL Staging Database

```bash
# Get Cloud SQL connection details
export STAGING_INSTANCE="your-staging-sql-instance"
export STAGING_DB="smarthandoff_staging"

# Run migrations
export DATABASE_URL="postgresql+asyncpg://user:pass@/cloudsql/${STAGING_PROJECT_ID}:us-central1:${STAGING_INSTANCE}/${STAGING_DB}"

cd backend
alembic upgrade head
```

---

## 5. Set Environment Variables

Create a `.env.staging` file in `backend/`:

```bash
# Vertex AI Configuration
STAGING_GCP_PROJECT_ID=your-staging-project-id
STAGING_GCP_REGION=us-central1

# FHIR Server Configuration
STAGING_FHIR_BASE_URL=https://fhir-staging.example.com/fhir
STAGING_FHIR_CLIENT_ID=smarthandoff-staging-client
STAGING_FHIR_CLIENT_SECRET=<from-secret-manager>

# Cloud SQL Configuration
STAGING_DATABASE_URL=postgresql+asyncpg://user:pass@<cloud-sql-proxy>/smarthandoff_staging

# Google Cloud Authentication
GOOGLE_APPLICATION_CREDENTIALS=/path/to/staging-service-account-key.json
```

**Security Note:** Never commit `.env.staging` to version control. Add to `.gitignore`.

---

## 6. Create Service Account for Tests

```bash
# Create service account
gcloud iam service-accounts create staging-perf-tests \
    --display-name="Staging Performance Tests" \
    --project=${STAGING_PROJECT_ID}

# Grant required roles
gcloud projects add-iam-policy-binding ${STAGING_PROJECT_ID} \
    --member="serviceAccount:staging-perf-tests@${STAGING_PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding ${STAGING_PROJECT_ID} \
    --member="serviceAccount:staging-perf-tests@${STAGING_PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

# Download key
gcloud iam service-accounts keys create staging-perf-tests-key.json \
    --iam-account=staging-perf-tests@${STAGING_PROJECT_ID}.iam.gserviceaccount.com \
    --project=${STAGING_PROJECT_ID}

# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/staging-perf-tests-key.json"
```

---

## 7. Verify Staging Environment

Run the environment validation script:

```bash
cd backend
python tests/performance/validate_staging_env.py
```

Expected output:
```
✓ STAGING_GCP_PROJECT_ID set
✓ STAGING_GCP_REGION set
✓ Vertex AI API enabled
✓ STAGING_FHIR_BASE_URL reachable
✓ FHIR OAuth 2.0 authentication successful
✓ STAGING_DATABASE_URL accessible
✓ Cloud SQL connection successful
✓ 100 test encounters seeded (PERF-ENC-0001 to PERF-ENC-0100)
```

---

## 8. Run Performance Test

```bash
# Load environment variables
set -a
source .env.staging
set +a

# Run performance test
pytest tests/performance/test_discharge_summary_p95.py \
    -v \
    --timeout=600 \
    --tb=short

# Expected runtime: 5-10 minutes
```

---

## 9. Interpret Results

### Success Output

```
tests/performance/test_discharge_summary_p95.py::test_p95_discharge_summary_latency
  [10/100] running p95 = 12345 ms
  [20/100] running p95 = 13456 ms
  ...
  [100/100] running p95 = 14567 ms

=== Discharge Summary Generation Latency Report ===
  Samples : 100
  p50     : 12000 ms
  p95     : 14567 ms  (threshold: 30000 ms)
  mean    : 12500 ms
  min     : 8000 ms
  max     : 18000 ms
  fallback count: 0

PASSED [100%]
```

### Failure Output

If p95 > 30 seconds:

```
AssertionError: p95 latency 32567 ms exceeds threshold 30000 ms.
Histogram: min=8000ms, p50=15000ms, p95=32567ms, max=45000ms
```

**Troubleshooting:**
- Check Vertex AI quota limits
- Verify FHIR server response times
- Review Gemini API rate limiting
- Check network latency to GCP services

---

## 10. CI/CD Integration

See `.github/workflows/staging-performance-gate.yml` for automated CI/CD configuration.

---

## Cleanup

After testing:

```bash
# Revoke service account key
gcloud iam service-accounts keys delete <KEY_ID> \
    --iam-account=staging-perf-tests@${STAGING_PROJECT_ID}.iam.gserviceaccount.com \
    --project=${STAGING_PROJECT_ID}

# Delete synthetic test encounters (optional)
python tests/performance/fixtures/cleanup_staging_fhir.py \
    --fhir-url=${STAGING_FHIR_BASE_URL} \
    --encounter-prefix=PERF-ENC
```

---

## Troubleshooting

### "STAGING_GCP_PROJECT_ID not set"

```bash
# Verify environment variables are loaded
echo $STAGING_GCP_PROJECT_ID

# If empty, reload .env.staging
set -a
source .env.staging
set +a
```

### "Vertex AI quota exceeded"

```bash
# Check quota usage
gcloud monitoring time-series list \
    --filter='metric.type="aiplatform.googleapis.com/quota/concurrent_requests/usage"' \
    --project=${STAGING_PROJECT_ID}

# Wait for quota to reset or request increase
```

### "FHIR authentication failed"

```bash
# Test FHIR OAuth flow manually
curl -X POST ${STAGING_FHIR_BASE_URL}/oauth2/token \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=client_credentials" \
    -d "client_id=${STAGING_FHIR_CLIENT_ID}" \
    -d "client_secret=${STAGING_FHIR_CLIENT_SECRET}"
```

### "Cloud SQL connection timeout"

```bash
# Use Cloud SQL Proxy for local testing
cloud_sql_proxy -instances=${STAGING_PROJECT_ID}:us-central1:${STAGING_INSTANCE}=tcp:5432 &

# Update DATABASE_URL to use localhost:5432
export STAGING_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/smarthandoff_staging"
```

---

## Security Best Practices

1. **Never commit credentials** to version control
2. **Rotate service account keys** every 90 days
3. **Use Secret Manager** for production credentials
4. **Restrict service account permissions** to minimum required
5. **Enable audit logging** for all API calls
6. **Use VPC Service Controls** for production FHIR servers

---

## Next Steps

1. **Baseline Metrics**: Run test 5 times to establish baseline p95 latency
2. **Performance Monitoring**: Set up Cloud Monitoring alerts for p95 > 30s
3. **Load Testing**: Scale test to 1000 concurrent cases
4. **Optimization**: Profile slow cases and optimize prompts

---

For questions or issues, contact the Platform Engineering team or file an issue in the repo.
