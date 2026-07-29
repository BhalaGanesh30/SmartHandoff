# Discharge Time Prediction ML Model

**User Story:** US-036 — Predicted Discharge Time Display  
**Epic:** EP-006 — Real-Time Bed Management & Housekeeping Integration  
**Model Type:** GradientBoostingRegressor (Scikit-learn 1.5+)  
**Target:** Predict discharge time within ±2 hours for 80% of encounters (MAE ≤2h)

---

## Overview

This module implements the full ML training pipeline for predicting patient discharge times based on encounter features at admission. The trained model is serialised to `joblib` format and uploaded to GCS (`ml-models` bucket) for use by the ML Inference Service (US-036 TASK-002).

---

## Features

The model uses 6 features engineered from encounter and patient data:

| Feature | Type | Description |
|---------|------|-------------|
| `admit_diagnosis_group` | Categorical | ICD-10 diagnosis category (e.g., "CARDIOVASCULAR", "RESPIRATORY") |
| `patient_age` | Numeric | Age in years at admission |
| `los_so_far_hours` | Numeric | Elapsed hours since admission (0.0 at training time) |
| `pending_procedures` | Numeric | Count of scheduled procedures not yet completed |
| `unit` | Categorical | Hospital unit code (e.g., "3A", "ICU") |
| `day_of_week` | Numeric | 0=Monday … 6=Sunday |

**Train-Serve Symmetry:** The same `features.py` module is used at training time and inference time to ensure feature engineering consistency.

---

## Training Pipeline

### 1. Data Loading
```python
from train import load_training_data

X, y = load_training_data(db_url="postgresql://read_replica_url")
# X: Feature DataFrame (6 columns)
# y: Target Series (hours_to_discharge)
```

**SQL Query:**
- Joins `encounter` and `patient` tables
- Filters: `discharge_time IS NOT NULL`, `deleted_at IS NULL`
- Computes target: `(discharge_time - admit_time).total_seconds() / 3600`

### 2. Preprocessing Pipeline
```python
from train import build_pipeline

pipeline = build_pipeline()
# Numeric features: median imputation → StandardScaler
# Categorical features: constant imputation ("UNKNOWN") → OneHotEncoder
# Estimator: GradientBoostingRegressor (n_estimators=200, max_depth=4)
```

### 3. Training
```bash
python train.py --db-url "postgresql://user:pass@host/db" --output models/discharge_time_v1.joblib
```

**Output:**
- `models/discharge_time_v1.joblib` — Serialised Scikit-learn Pipeline (preprocessor + regressor)

### 4. Evaluation
```python
from evaluate import evaluate

result = evaluate(
    pipeline_path=Path("models/discharge_time_v1.joblib"),
    X_test=X_test,
    y_test=y_test,
)
# Metrics: MAE, RMSE, % within ±2h
# Quality Gates: MAE ≤2.0h, ≥80% within ±2h
```

**Quality Gates (CI/CD Integration):**
- **MAE ≤ 2.0 hours** — Mean Absolute Error threshold
- **≥80% within ±2 hours** — Prediction accuracy requirement
- **Exit Code 1** if gates fail (blocks deployment)

### 5. GCS Upload
```python
from upload import upload_model

gcs_uri = upload_model(
    local_path=Path("models/discharge_time_v1.joblib"),
    version_tag="v20260728",
    bucket_name="ml-models",
)
# Uploads to:
# - gs://ml-models/discharge_time/v20260728/discharge_time.joblib (versioned)
# - gs://ml-models/discharge_time/latest/discharge_time.joblib (inference pointer)
```

---

## Model Versioning

### Version Tagging Strategy
- **Date-based:** `v20260728` (YYYYMMDD) for nightly retrains
- **Semantic:** `v1`, `v2` for major model architecture changes

### GCS Bucket Structure
```
gs://ml-models/
├── discharge_time/
│   ├── v1/
│   │   └── discharge_time.joblib
│   ├── v20260728/
│   │   └── discharge_time.joblib
│   └── latest/
│       └── discharge_time.joblib  ← Inference service loads this
```

---

## Nightly Retrain (Cloud Build)

**Scheduled Trigger:** Daily at 02:00 UTC

```yaml
steps:
  - name: 'python:3.12-slim'
    entrypoint: bash
    args:
      - '-c'
      - |
        pip install -r ml/discharge_time_model/requirements.txt
        python ml/discharge_time_model/train.py \
          --db-url $$DB_READ_URL \
          --output models/discharge_time_v1.joblib
        python -c "
        from ml.discharge_time_model.upload import upload_model
        from pathlib import Path
        import datetime
        tag = 'v' + datetime.date.today().strftime('%Y%m%d')
        upload_model(Path('models/discharge_time_v1.joblib'), tag)
        "
    secretEnv: ['DB_READ_URL']
```

**Rollback Strategy:**
If quality gates fail, Cloud Build exits with code 1 and the previous day's model (`latest/`) remains unchanged.

---

## Local Development

### Setup
```bash
cd ml/discharge_time_model
pip install -r requirements.txt
```

### Training (Local)
```bash
export DB_URL="postgresql://localhost:5432/smarthandoff_dev"
python train.py --db-url "$DB_URL" --output models/discharge_time_v1.joblib
```

### Evaluation (Holdout Set)
```python
import pandas as pd
from sklearn.model_selection import train_test_split
from train import load_training_data
from evaluate import evaluate

X, y = load_training_data(db_url=DB_URL)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)

# Train model first (train.py outputs models/discharge_time_v1.joblib)
# Then evaluate:
result = evaluate(
    pipeline_path=Path("models/discharge_time_v1.joblib"),
    X_test=X_test,
    y_test=y_test,
)
print(f"MAE: {result.mae_hours:.2f}h | Within ±2h: {result.pct_within_2h:.1%}")
```

---

## Model Monitoring

### Drift Detection (Future Enhancement)
- **Feature Drift:** Monitor distribution of `admit_diagnosis_group`, `unit` over 30-day windows
- **Target Drift:** Track MAE trend on daily predictions vs actual discharge times
- **Data Quality:** Alert if `pending_procedures_count > 10` (outlier guard)

### Performance Metrics (Production)
- **Inference Latency:** p95 < 500ms (TR-007 requirement)
- **Prediction Error:** Weekly MAE report sent to AI/ML team
- **Coverage:** % of encounters with predictions (should be ~100% for admitted patients)

---

## Security & PHI Compliance

**PHI Exclusion:**
- Feature vectors contain **NO** patient name, MRN, DOB, or SSN
- Only aggregate identifiers: `patient_age` (derived), `unit`, `admit_diagnosis_group`
- Model artefact metadata contains **NO** PHI

**Access Control:**
- GCS bucket `ml-models` restricted to service account `ml-inference-service@smarthandoff.iam.gserviceaccount.com`
- Training DB read replica uses least-privilege IAM role (SELECT only on `encounter`, `patient`)

---

## Dependencies

See [requirements.txt](requirements.txt):
- `scikit-learn>=1.5.0` — GradientBoostingRegressor, Pipeline, ColumnTransformer
- `pandas>=2.0.0` — DataFrame operations
- `numpy>=1.26.0` — Numerical operations
- `joblib>=1.3.0` — Model serialisation
- `sqlalchemy>=2.0.0` — DB connectivity
- `google-cloud-storage>=2.14.0` — GCS upload
- `psycopg2-binary>=2.9.0` — PostgreSQL driver

---

## References

- [US-036 User Story](.propel/context/tasks/EP-006/US-036/user_story.md)
- [US-036 TASK-001 Specification](.propel/context/tasks/EP-006/US-036/task_001_ml_training_pipeline.md)
- [Design Document](../../docs/design.md) — §3.1 ML Inference Service, §4.1 Tech Stack
- [Scikit-learn GradientBoostingRegressor Docs](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.GradientBoostingRegressor.html)

---

**Version:** 1.0.0  
**Last Updated:** 2026-07-28  
**Maintainer:** AI/ML Engineering Team
