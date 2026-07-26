# FHIR Server Setup Guide

Complete guide to setting up synthetic patient data for SmartHandoff using Synthea and HAPI FHIR.

## Overview

SmartHandoff fetches patient data from an external FHIR R4 server. This guide shows you how to:

1. ✅ Run a local HAPI FHIR server
2. ✅ Generate synthetic patients with Synthea
3. ✅ Load patient data into HAPI FHIR
4. ✅ Configure SmartHandoff backend to use FHIR data

## Prerequisites

- **Docker Desktop** - For running HAPI FHIR server
- **Java 11+** - For running Synthea
- **Python 3.8+** - For data loading script
- **PowerShell 7+** - For automation scripts

## Quick Start (Recommended)

### Step 1: Start HAPI FHIR Server

```powershell
cd $env:USERPROFILE\source\repos\SmartHandoff
.\scripts\setup-fhir-server.ps1
```

**What this does:**
- Pulls `hapiproject/hapi:latest` Docker image
- Starts HAPI FHIR R4 server on port 8090
- Configures subscription and reference handling
- Waits for server to be ready

**Result:**
- FHIR Base URL: `http://localhost:8090/fhir`
- Web UI: `http://localhost:8090`
- Container: `hapi-fhir` (running)

---

### Step 2: Generate Synthetic Patients

```powershell
.\scripts\generate-synthea-data.ps1 -PatientCount 50
```

**What this does:**
- Downloads Synthea JAR (if not present)
- Generates 50 synthetic patients with realistic medical histories
- Creates FHIR R4 JSON bundles in `synthea/output/fhir/`

**Generated data includes:**
- Patient demographics (name, DOB, gender, address)
- Medical conditions (diagnoses, problems)
- Medications (current and historical)
- Observations (vital signs, lab results)
- Encounters (hospital visits, admissions)
- Procedures (surgeries, treatments)
- Care plans and clinical notes

**Processing time:** ~5-10 minutes for 50 patients

---

### Step 3: Load Data into HAPI FHIR

```powershell
python .\scripts\load-fhir-data.py
```

**What this does:**
- Validates HAPI FHIR server connection
- Uploads all FHIR JSON bundles
- Uses transaction bundles for atomic uploads
- Reports success/failure per file

**Expected output:**
```
✓ Successful: 50
Total uploaded: 50 patient bundles
```

**Verify data loaded:**
```powershell
# Count patients
curl http://localhost:8090/fhir/Patient?_summary=count

# Search patients
curl http://localhost:8090/fhir/Patient?name=Smith

# Get specific patient
curl http://localhost:8090/fhir/Patient/123
```

---

### Step 4: Configure SmartHandoff Backend

#### Option A: Use Public HAPI FHIR (Cloud Run Compatible)

```powershell
.\scripts\configure-backend-fhir.ps1 -UsePublicHapi
```

This updates your Cloud Run backend to use the public HAPI FHIR test server:
- URL: `https://hapi.fhir.org/baseR4`
- No authentication required
- Pre-loaded with test patients
- **Advantage:** Works immediately with Cloud Run (no localhost issue)

#### Option B: Local Development Only

```powershell
.\scripts\configure-backend-fhir.ps1
```

Creates `backend/.env` with local FHIR server URL:
- URL: `http://localhost:8090/fhir`
- **Limitation:** Cannot be accessed by Cloud Run (localhost)
- **Use for:** Local backend development and testing

---

## Testing the Integration

### 1. Test FHIR Server Directly

```powershell
# Get server metadata
Invoke-RestMethod -Uri "http://localhost:8090/fhir/metadata" | ConvertTo-Json

# Search all patients
Invoke-RestMethod -Uri "http://localhost:8090/fhir/Patient" | ConvertTo-Json

# Get patient by ID
Invoke-RestMethod -Uri "http://localhost:8090/fhir/Patient/example-patient-id" | ConvertTo-Json
```

### 2. Test SmartHandoff Backend (Local)

```powershell
cd backend
uvicorn app.main:app --reload --port 8000

# Test patient endpoint
curl http://localhost:8000/api/v1/patients?mrn=12345
```

### 3. Test SmartHandoff Backend (Cloud Run)

```powershell
# First, ensure backend is configured with public HAPI FHIR
.\scripts\configure-backend-fhir.ps1 -UsePublicHapi

# Test via deployed backend
curl https://smarthandoff-backend-h67r7fyswq-uc.a.run.app/api/v1/patients?mrn=example-mrn
```

---

## Architecture Details

### Data Flow

```
┌─────────────────┐
│  Hospital EHR   │
│  (Epic/Cerner)  │
└────────┬────────┘
         │ HL7 ADT Messages
         │ (Admission/Discharge/Transfer)
         ▼
┌─────────────────┐
│  SmartHandoff   │
│  ADT Listener   │
└────────┬────────┘
         │ Trigger: New Admission
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  SmartHandoff   │─────▶│   FHIR Server    │
│  Backend API    │      │  (HAPI FHIR R4)  │
└────────┬────────┘      └──────────────────┘
         │                     │
         │ Fetch Patient Data  │
         │ - Demographics      │
         │ - Medications       │
         │ - Conditions        │
         │ - Observations      │
         │                     │
         ▼                     │
┌─────────────────┐           │
│  AI Agents      │           │
│  (LangChain)    │           │
│                 │           │
│  1. Transition  │           │
│     Coordinator │           │
│  2. Medication  │           │
│     Reconcile   │           │
│  3. Documentation│          │
│  4. Follow-up   │           │
└─────────────────┘           │
         │                     │
         │ Generate Outputs    │
         ▼                     │
┌─────────────────┐           │
│  SmartHandoff   │           │
│  Database       │           │
│  (Metadata Only)│           │
└─────────────────┘           │
                              │
         ┌────────────────────┘
         │
         │ Data NOT Persisted
         │ (HIPAA Compliance)
         │
         ▼
    In-Memory Only
```

### Key Principles

1. **No Patient Data Storage**
   - SmartHandoff does NOT persist patient PHI
   - All patient data fetched on-demand from FHIR
   - Only encounter metadata stored (status, timestamps)

2. **HIPAA Compliance**
   - Minimum necessary data principle
   - In-memory processing only
   - Encrypted transmission (HTTPS)
   - Audit logging for all access

3. **FHIR R4 Standard**
   - Uses standard FHIR resources (Patient, Medication, Observation)
   - OAuth 2.0 authentication
   - Circuit breaker for resilience
   - Rate limiting (100 req/min)

---

## Advanced Configuration

### Deploy HAPI FHIR to Cloud Run

To make your local FHIR data accessible from Cloud Run:

```powershell
# 1. Create Dockerfile for HAPI FHIR
# 2. Deploy to Cloud Run
.\scripts\deploy-hapi-fhir.ps1

# 3. Update backend with deployed FHIR URL
gcloud run services update smarthandoff-backend \
  --update-env-vars="FHIR_BASE_URL=https://hapi-fhir-xxx.run.app/fhir" \
  --region=us-central1
```

### Use Real EHR FHIR Endpoint

For production with Epic/Cerner:

```powershell
# Add to Cloud Run environment variables
FHIR_BASE_URL=https://fhir.your-hospital.org/r4
FHIR_CLIENT_ID=your-client-id
FHIR_CLIENT_SECRET=your-client-secret
FHIR_SCOPE=system/*.read
```

### Generate More Patients

```powershell
# Generate 500 patients (takes ~1 hour)
.\scripts\generate-synthea-data.ps1 -PatientCount 500

# Generate for specific demographics
.\scripts\generate-synthea-data.ps1 -PatientCount 100 -State "California" -City "Los Angeles"
```

---

## Troubleshooting

### HAPI FHIR Server Won't Start

```powershell
# Check Docker status
docker info

# View container logs
docker logs hapi-fhir

# Restart container
docker restart hapi-fhir

# Remove and recreate
docker stop hapi-fhir
docker rm hapi-fhir
.\scripts\setup-fhir-server.ps1
```

### Synthea Generation Fails

```powershell
# Check Java version (need 11+)
java -version

# Download manually if automatic download fails
# https://github.com/synthetichealth/synthea/releases
```

### Data Upload Fails

```powershell
# Check FHIR server is running
curl http://localhost:8090/fhir/metadata

# Check bundle file format
Get-Content .\synthea\output\fhir\Patient-123.json | ConvertFrom-Json

# Upload single file manually
Invoke-RestMethod -Uri "http://localhost:8090/fhir" `
  -Method POST `
  -ContentType "application/fhir+json" `
  -InFile ".\synthea\output\fhir\Patient-123.json"
```

### Cloud Run Can't Access Local FHIR

**Problem:** Cloud Run services cannot access `localhost`

**Solutions:**
1. Use `-UsePublicHapi` flag (easiest)
2. Deploy HAPI FHIR to Cloud Run
3. Use ngrok: `ngrok http 8090`
4. Use Cloudflare Tunnel

---

## Summary Commands

```powershell
# Complete setup (4 steps)
cd $env:USERPROFILE\source\repos\SmartHandoff

# 1. Start HAPI FHIR
.\scripts\setup-fhir-server.ps1

# 2. Generate patients (5-10 min)
.\scripts\generate-synthea-data.ps1 -PatientCount 50

# 3. Load data
python .\scripts\load-fhir-data.py

# 4. Configure backend (Cloud Run compatible)
.\scripts\configure-backend-fhir.ps1 -UsePublicHapi

# Verify
curl https://smarthandoff-backend-h67r7fyswq-uc.a.run.app/api/v1/patients
```

---

## Next Steps

1. ✅ FHIR server running with patient data
2. ✅ Backend configured to fetch from FHIR
3. 🔄 **Deploy frontend** - See [DEPLOYMENT-GUIDE.md](DEPLOYMENT-GUIDE.md)
4. 🔄 **Configure AI agents** - Set up Vertex AI/Gemini credentials
5. 🔄 **Test end-to-end** - Trigger ADT message → AI processing → notification

---

## Resources

- **Synthea:** https://github.com/synthetichealth/synthea
- **HAPI FHIR:** https://hapifhir.io/
- **FHIR R4 Spec:** https://hl7.org/fhir/R4/
- **Public HAPI Server:** https://hapi.fhir.org/baseR4
- **SMART Health IT:** https://launch.smarthealthit.org/
