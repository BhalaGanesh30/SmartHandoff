# Analytics Dashboard - Local Development & Testing Guide

**Goal**: Get everything working on localhost before deployment to Cloud Run

---

## Prerequisites Check

Ensure you have these running locally:

```bash
# Check PostgreSQL is running on 127.0.0.1:9432
psql -h 127.0.0.1 -U postgres -d smarthandoff -c "SELECT 1"

# Check Node.js is available
node --version  # Should be 20+

# Check Python is available
python --version  # Should be 3.11+
```

---

## Step 1: Apply Database Migration Locally

```bash
cd c:\Users\BhalaganeshMadesh\source\repos\SmartHandoff\backend

# Set environment variable
$env:DATABASE_URL='postgresql+asyncpg://postgres:SmartHandoff@123@127.0.0.1:9432/smarthandoff'

# Apply migration (this will update the mv_kpi_daily view)
python -m alembic upgrade head

# Verify migration was applied
python -m alembic current
```

**Expected Output**:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl with table alembic_version
INFO  [alembic.runtime.migration] Will assume transactional DDL is supported
INFO  [alembic.runtime.migration] Running upgrade ... -> zc0k7i2f89a6
```

---

## Step 2: Seed Test Data

```bash
cd c:\Users\BhalaganeshMadesh\source\repos\SmartHandoff\backend

# Run the test data seeding script
$env:DATABASE_URL='postgresql+asyncpg://postgres:SmartHandoff@123@127.0.0.1:9432/smarthandoff'
python seed_analytics_test_data.py
```

**Expected Output**:
```
✅ Inserted 30 test encounters
✅ Inserted test documents
✅ Inserted test agent tasks
✅ Refreshed mv_kpi_daily materialized view

📊 Analytics Data Summary:
   Total rows in mv_kpi_daily: 30
   Unique dates: 30
   Unique units: 4

   Sample rows:
     2026-08-06 | 4-West       | Discharge: 45.3min | Readmit: 23.33% | ...
```

---

## Step 3: Start Backend Server

**Terminal 1: Backend**

```bash
cd c:\Users\BhalaganeshMadesh\source\repos\SmartHandoff\backend

# Set all required environment variables
$env:PYTHONPATH = '.'
$env:PHI_ENCRYPTION_KEY = 'peF3ahNpMuTZD6tm-B9tNA5YKZlxYSQNYVZd2x6Ou3A='
$env:PRIMARY_DATABASE_URL = 'postgresql+asyncpg://postgres:SmartHandoff@123@127.0.0.1:9432/smarthandoff'
$env:REPLICA_DATABASE_URL = 'postgresql+asyncpg://postgres:SmartHandoff@123@127.0.0.1:9432/smarthandoff'
$env:ALLOW_UNAUTHENTICATED_LOCALHOST = 'true'
$env:FHIR_BASE_URL = 'https://r4.smarthealthit.org'
$env:JWT_SIGNING_KEY = '<YOUR_JWT_SIGNING_KEY>'
$env:OIDC_CLIENT_ID = '<YOUR_GOOGLE_OAUTH_CLIENT_ID>'
$env:GOOGLE_OAUTH_CLIENT_SECRET = '<YOUR_GOOGLE_OAUTH_CLIENT_SECRET>'

# Start the backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected Output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

✅ Backend ready at: `http://localhost:8000`

---

## Step 4: Test Backend API Endpoint

**Terminal 2: Test API**

```bash
# Test 1: Check if endpoint exists (no auth required on localhost)
curl -X GET 'http://localhost:8000/api/v1/analytics/kpis?from=2026-07-01&to=2026-08-06'

# Test 2: With unit filter
curl -X GET 'http://localhost:8000/api/v1/analytics/kpis?from=2026-07-01&to=2026-08-06&unit=4-West'

# Test 3: Check response structure
curl -X GET 'http://localhost:8000/api/v1/analytics/kpis?from=2026-07-01&to=2026-08-06' | jq '.'
```

**Expected Response** (200 OK):
```json
{
  "from_date": "2026-07-01",
  "to_date": "2026-08-06",
  "unit": null,
  "data": [
    {
      "date": "2026-07-01",
      "unit": "4-West",
      "avg_discharge_doc_time_min": 45.3,
      "readmission_rate_30d": 0.233,
      "med_recon_completion_rate": 0.8,
      "bed_utilisation_pct": 75.5,
      "agent_task_success_rate": 0.8
    },
    ...
  ],
  "total_rows": 30
}
```

✅ **Key Checks**:
- [ ] Response status is **200**
- [ ] `data` array has entries
- [ ] All 5 metrics are present (not null)
- [ ] `total_rows` matches number of entries

---

## Step 5: Start Frontend

**Terminal 3: Frontend**

```bash
cd c:\Users\BhalaganeshMadesh\source\repos\SmartHandoff\frontend

# Install dependencies (if needed)
npm install

# Start development server
npm start
```

**Expected Output**:
```
✔ Compiled successfully.

Application is running at:

  Local:            http://localhost:4200/
```

✅ Frontend ready at: `http://localhost:4200`

---

## Step 6: Test Frontend UI

**Open Browser**: Navigate to `http://localhost:4200`

### Login Flow
1. Click "Sign In" button
2. Google OAuth popup appears
3. Sign in with test account
4. Redirected back to dashboard

### Navigate to Analytics
1. Click menu → "Analytics" (or navigate to `http://localhost:4200/analytics`)
2. Should see 5 charts loading with data

### Verify Charts Display

**Chart 1: Discharge Time (Line Chart)**
- X-axis: Dates (2026-07-01 to 2026-08-06)
- Y-axis: Minutes (should be 40-50 range)
- ✅ Should show upward/downward trend line

**Chart 2: Readmission Rate (Bar Chart)**
- X-axis: Units (4-West, 3-North, ICU, 5-East)
- Y-axis: Percentage (0-100%)
- ✅ Should show bars for each unit

**Chart 3: Med Reconciliation (Gauge Chart)**
- Circular gauge showing percentage
- ✅ Should be in 70-90% range

**Chart 4: Bed Utilisation (Doughnut Chart)**
- Shows percentage distribution
- ✅ Should show colored segments

**Chart 5: Agent Success Rate (Stacked Bar Chart)**
- Shows success rate by unit
- ✅ Should show stacked bars

### Test Filter Controls
1. **Date Range Picker**:
   - Click date range selector
   - Change dates to different range
   - Charts should update automatically

2. **Unit Filter Dropdown**:
   - Select a specific unit (e.g., "4-West")
   - Charts should filter to show only that unit

### Test Export Buttons
1. **CSV Export**:
   - Click "Export CSV" button
   - Should start download within 5 seconds
   - Open downloaded file to verify data

2. **PDF Export**:
   - Click "Export PDF" button
   - Shows "Processing..." message
   - After 10-15 seconds, PDF download starts
   - Open PDF to verify charts rendered

---

## Troubleshooting

### Issue: "Cannot GET /analytics"

**Cause**: Route not registered

**Fix**:
```bash
# Check frontend/src/app/app.routes.ts contains:
# {
#   path: 'analytics',
#   loadChildren: () =>
#     import('./features/analytics/analytics.routes').then(m => m.ANALYTICS_ROUTES)
# }
```

### Issue: API returns 403 Forbidden

**Cause**: Authentication required (not on localhost)

**Fix**:
- Make sure `ALLOW_UNAUTHENTICATED_LOCALHOST=true` is set
- Restart backend

### Issue: Charts show "No data"

**Cause**: Database is empty

**Fix**:
```bash
# Verify test data exists
psql -h 127.0.0.1 -U postgres -d smarthandoff \
  -c "SELECT COUNT(*) FROM mv_kpi_daily;"

# If 0, re-run seeding
python seed_analytics_test_data.py
```

### Issue: API returns wrong metrics

**Cause**: Old view schema still active

**Fix**:
```bash
# Check current view schema
psql -h 127.0.0.1 -U postgres -d smarthandoff \
  -c "SELECT column_name FROM information_schema.columns WHERE table_name='mv_kpi_daily' ORDER BY ordinal_position;"

# Should show: date, unit, avg_discharge_doc_time_min, readmission_rate_30d, ...
# If showing old columns, migration didn't apply - run it again

cd backend && python -m alembic upgrade head
```

### Issue: npm start fails with "ERR! ENOENT: no such file or directory"

**Fix**:
```bash
cd frontend
rm -r node_modules
npm install
npm start
```

---

## Complete Test Checklist

- [ ] **Database**
  - [ ] Migration applied (`alembic current` shows correct version)
  - [ ] Test data inserted (`SELECT COUNT(*) FROM mv_kpi_daily;` shows 30)
  - [ ] View has correct schema (5 columns: date, unit, avg_discharge_doc_time_min, ...)

- [ ] **Backend API**
  - [ ] Server running at `http://localhost:8000`
  - [ ] Health check: `curl http://localhost:8000/docs` loads Swagger
  - [ ] API endpoint returns 200 OK
  - [ ] Response has all 5 metrics
  - [ ] Response total_rows > 0

- [ ] **Frontend**
  - [ ] Server running at `http://localhost:4200`
  - [ ] Can navigate to `/analytics` route
  - [ ] All 5 charts render (not blank)
  - [ ] Charts show data points (not flat lines)
  - [ ] Filter controls work (date picker, unit dropdown)

- [ ] **Export**
  - [ ] CSV download works (file size > 100 bytes)
  - [ ] PDF export triggers and downloads
  - [ ] Both files have data (not empty)

---

## Performance Baseline

Record these for comparison after optimization:

```bash
# API response time
time curl -s 'http://localhost:8000/api/v1/analytics/kpis?from=2026-07-01&to=2026-08-06' > /dev/null

# Expected: < 500ms
```

**Example Output**:
```
real    0m0.234s
user    0m0.031s
sys     0m0.015s
```

---

## Next Steps (After Local Testing)

Once everything works locally:

1. ✅ Commit changes to git
2. ✅ Create feature branch: `git checkout -b feature/analytics-dashboard-fix`
3. ✅ Push to remote: `git push origin feature/analytics-dashboard-fix`
4. ✅ Deploy to Cloud Run (see DEPLOYMENT-GUIDE.md)
5. ✅ Test on staging environment
6. ✅ Merge to main and deploy to production

---

**Status**: 🟢 Ready for Local Testing
