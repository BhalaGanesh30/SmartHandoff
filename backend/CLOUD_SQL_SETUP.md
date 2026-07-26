# Cloud SQL Setup Guide — US-030 Medication Reconciliation

This guide shows how to connect to Cloud SQL for running Alembic migrations and testing the medication reconciliation schema.

---

## 📋 **Prerequisites**

- ✅ Cloud SQL instance: `smarthandoff:us-central1:smarthandoff`
- ✅ PostgreSQL 15 running on port 5432
- ✅ Database user credentials (DB_USER, DB_PASSWORD)
- ✅ Database name (DB_NAME)

---

## 🔧 **Option 1: Cloud SQL Proxy (Recommended for Local Development)**

### Step 1: Install Cloud SQL Proxy

**Windows (PowerShell):**
```powershell
# Download Cloud SQL Proxy
Invoke-WebRequest -Uri "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.x64.exe" -OutFile "cloud-sql-proxy.exe"

# Move to PATH (optional)
Move-Item cloud-sql-proxy.exe "$env:USERPROFILE\bin\cloud-sql-proxy.exe"
```

**macOS/Linux:**
```bash
# Download and install
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.darwin.amd64
chmod +x cloud-sql-proxy
sudo mv cloud-sql-proxy /usr/local/bin/
```

### Step 2: Authenticate with GCP

```bash
gcloud auth application-default login
gcloud config set project smarthandoff
```

### Step 3: Start Cloud SQL Proxy

**PowerShell:**
```powershell
# Start proxy in background
Start-Process -NoNewWindow cloud-sql-proxy `
  -ArgumentList "smarthandoff:us-central1:smarthandoff", "--port", "5432"

# Or run in foreground (recommended for debugging)
cloud-sql-proxy smarthandoff:us-central1:smarthandoff --port 5432
```

**Bash:**
```bash
# Start proxy in foreground
cloud-sql-proxy smarthandoff:us-central1:smarthandoff --port 5432

# Or run in background
cloud-sql-proxy smarthandoff:us-central1:smarthandoff --port 5432 &
```

**Expected output:**
```
Listening on 127.0.0.1:5432
Ready for new connections
```

### Step 4: Configure Environment Variables

Create `backend/.env` from `backend/.env.example`:

```bash
cd backend
cp .env.example .env
```

Edit `.env`:
```bash
# Cloud SQL via Proxy
CLOUD_SQL_CONNECTION_NAME=smarthandoff:us-central1:smarthandoff
DB_USER=postgres
DB_PASSWORD=YOUR_ACTUAL_PASSWORD
DB_NAME=smarthandoff
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
GCP_PROJECT_ID=smarthandoff
```

### Step 5: Test Connection

```bash
# Test with psql
psql "postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"

# Or test with Python
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test():
    engine = create_async_engine('postgresql+asyncpg://USER:PASS@localhost:5432/DB')
    async with engine.connect() as conn:
        result = await conn.execute('SELECT version();')
        print(result.fetchone())

asyncio.run(test())
"
```

### Step 6: Run Alembic Migrations

```bash
cd backend

# Check current migration status
alembic current

# Apply US-030 TASK-001 migration
alembic upgrade head

# Verify migration
alembic current
# Should show: n8k1j4f69i63 (head)

# Check medication table schema
psql "postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}" \
  -c "\d medication"
```

**Expected columns:**
```
 id                             | uuid                        
 encounter_id                   | uuid                        
 drug_name                      | character varying(255)      
 rxcui                          | character varying(32)       
 dose                           | character varying(64)       
 route                          | character varying(64)       
 frequency                      | character varying(64)       
 source                         | character varying(32)       
 interaction_severity           | character varying(16)       
 reconciliation_status          | character varying(32)       
 rxnorm_cui                     | character varying(20)       ← NEW
 reconciliation_category        | reconciliationcategory      ← NEW
 flags                          | reconciliationflag[]        ← NEW
 dose_value                     | double precision            ← NEW
 dose_unit                      | character varying(20)       ← NEW
 sources                        | medicationlistsource[]      ← NEW
 reconciliation_completed_at    | timestamp with time zone    ← NEW
 created_at                     | timestamp with time zone    
 updated_at                     | timestamp with time zone    
```

---

## 🌐 **Option 2: Cloud Run with Cloud SQL Connector**

For Cloud Run deployments, use Unix socket connections:

**`backend/.env` (Cloud Run):**
```bash
CLOUD_SQL_CONNECTION_NAME=smarthandoff:us-central1:smarthandoff
DB_USER=postgres
DB_PASSWORD=secret://smarthandoff/database-password
DB_NAME=smarthandoff
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@/cloudsql/${CLOUD_SQL_CONNECTION_NAME}/${DB_NAME}
```

**Cloud Run YAML:**
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: smarthandoff-backend
  annotations:
    run.googleapis.com/cloudsql-instances: smarthandoff:us-central1:smarthandoff
spec:
  template:
    spec:
      containers:
        - image: gcr.io/smarthandoff/backend:latest
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: database-url
                  key: latest
```

---

## 🔐 **Option 3: Private IP (VPC Peering)**

For GKE or services in the same VPC:

```bash
# Get private IP
gcloud sql instances describe smarthandoff \
  --format="value(ipAddresses[0].ipAddress)"
# Example output: 10.48.0.3

# Configure .env
DB_HOST=10.48.0.3
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@10.48.0.3:5432/${DB_NAME}
```

---

## ✅ **Validation Checklist**

After setup, verify:

- [ ] Cloud SQL Proxy is running (`Listening on 127.0.0.1:5432`)
- [ ] `.env` file exists with correct credentials
- [ ] `psql` can connect to database
- [ ] `alembic current` shows migration status
- [ ] `alembic upgrade head` applies without errors
- [ ] `medication` table has 8 new columns
- [ ] All 3 new ENUM types exist:
  - [ ] `reconciliationcategory`
  - [ ] `reconciliationflag`
  - [ ] `medicationlistsource`

---

## 🐛 **Troubleshooting**

### Error: "Connection refused"
```
psql: error: connection to server at "localhost" (127.0.0.1), port 5432 failed
```
**Solution:** Start Cloud SQL Proxy first

### Error: "password authentication failed"
```
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "postgres"
```
**Solution:** Check `DB_PASSWORD` in `.env`, retrieve from Secret Manager:
```bash
gcloud secrets versions access latest --secret="database-password"
```

### Error: "Database does not exist"
```
asyncpg.exceptions.InvalidCatalogNameError: database "smarthandoff" does not exist
```
**Solution:** Create database:
```bash
gcloud sql databases create smarthandoff --instance=smarthandoff
```

### Error: "Multiple heads are present"
```
FAILED: Multiple heads are present; please specify the head revision
```
**Solution:** Merge Alembic heads first (tracked in separate ticket)

---

## 📚 **References**

- [Cloud SQL Proxy Documentation](https://cloud.google.com/sql/docs/postgres/sql-proxy)
- [SQLAlchemy Async Engine](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- US-030 TASK-001: Medication ORM Models, Enums, and Alembic Migration

---

**Last Updated:** 2026-07-26  
**Migration Version:** n8k1j4f69i63
