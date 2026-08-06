# Analytics Dashboard - Quick Start for Localhost

## Follow These Steps in Order

### Step 1: Apply Database Migration

Copy and run in a **PowerShell terminal**:

```powershell
cd c:\Users\BhalaganeshMadesh\source\repos\SmartHandoff\backend
$env:DATABASE_URL='postgresql+asyncpg://postgres:SmartHandoff@123@127.0.0.1:9432/smarthandoff'
python -m alembic upgrade head
```

✅ Wait for: `Running upgrade ... -> zc0k7i2f89a6`

---

### Step 2: Seed Test Data

In the **same terminal**:

```powershell
python seed_analytics_test_data.py
```

✅ Wait for: `✅ Refreshed mv_kpi_daily materialized view`

---

### Step 3: Start Backend Server

Open a **new PowerShell terminal** and run:

```powershell
cd c:\Users\BhalaganeshMadesh\source\repos\SmartHandoff\backend

$env:PYTHONPATH = '.'
$env:PHI_ENCRYPTION_KEY = 'peF3ahNpMuTZD6tm-B9tNA5YKZlxYSQNYVZd2x6Ou3A='
$env:PRIMARY_DATABASE_URL = 'postgresql+asyncpg://postgres:SmartHandoff@123@127.0.0.1:9432/smarthandoff'
$env:REPLICA_DATABASE_URL = 'postgresql+asyncpg://postgres:SmartHandoff@123@127.0.0.1:9432/smarthandoff'
$env:ALLOW_UNAUTHENTICATED_LOCALHOST = 'true'
$env:FHIR_BASE_URL = 'https://r4.smarthealthit.org'
$env:JWT_SIGNING_KEY = '<YOUR_JWT_SIGNING_KEY>'
$env:OIDC_CLIENT_ID = '<YOUR_GOOGLE_OAUTH_CLIENT_ID>'
$env:GOOGLE_OAUTH_CLIENT_SECRET = '<YOUR_GOOGLE_OAUTH_CLIENT_SECRET>'

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

✅ Wait for: `Uvicorn running on http://0.0.0.0:8000`

Keep this terminal open (don't close it)

---

### Step 4: Test Backend API

Open a **third PowerShell terminal** and run:

```powershell
curl -X GET 'http://localhost:8000/api/v1/analytics/kpis?from=2026-07-01&to=2026-08-06' | jq '.'
```

✅ Should see JSON response with `data` array

---

### Step 5: Start Frontend

Open a **fourth PowerShell terminal** and run:

```powershell
cd c:\Users\BhalaganeshMadesh\source\repos\SmartHandoff\frontend
npm install
npm start
```

✅ Wait for: `Compiled successfully` message

---

### Step 6: Open in Browser

**Open URL**: `http://localhost:4200`

1. Click "Sign In"
2. Login with Google account
3. Click menu → "Analytics"
4. **You should see 5 charts with data!**

---

## Expected Results

| Component | Status | Location |
|-----------|--------|----------|
| Database | ✅ Running | localhost:9432 |
| Backend API | ✅ Running | localhost:8000 |
| Frontend | ✅ Running | localhost:4200 |
| Charts | ✅ Rendering | http://localhost:4200/analytics |
| Data | ✅ Visible | In all 5 charts |

---

## Quick Verification Commands

**In any terminal, run these to verify everything is working:**

```powershell
# 1. Check if backend is responding
curl -I http://localhost:8000/docs

# 2. Check if API has data
curl 'http://localhost:8000/api/v1/analytics/kpis?from=2026-07-01&to=2026-08-06' | jq '.data | length'

# 3. Check if database has data
psql -h 127.0.0.1 -U postgres -d smarthandoff -c "SELECT COUNT(*) FROM mv_kpi_daily;"
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Cannot connect to database" | Verify PostgreSQL running: `psql -h 127.0.0.1 -U postgres` |
| "Permission denied" | Run PowerShell as Administrator |
| "Module not found" | Run `pip install -r requirements.txt` in backend folder |
| "Port 8000 already in use" | Kill existing: `taskkill /F /IM python.exe` |
| "npm not found" | Install Node.js from nodejs.org |
| "ERR: ENOENT" in frontend | Delete `node_modules`, run `npm install` again |

---

## Keep All 4 Terminals Open

Once everything is running, you'll have 4 terminals:

1. **Terminal 1**: Migration & data seeding (✅ Done)
2. **Terminal 2**: Backend server (🟢 Keep running)
3. **Terminal 3**: Test commands (Free to use)
4. **Terminal 4**: Frontend server (🟢 Keep running)

---

## Next: Test Features

Once dashboard loads, test these features:

✅ **Date Range Filter**: Pick different dates, charts update  
✅ **Unit Filter**: Select "4-West", charts filter  
✅ **CSV Export**: Download CSV file  
✅ **PDF Export**: Download PDF file  
✅ **Chart Interactions**: Hover over data points, tooltips show

---

**You're ready to go! Start with Step 1 above.** ⬆️
