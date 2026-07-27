# SmartHandoff GCP Deployment Guide

Complete guide to deploy the SmartHandoff healthcare platform to Google Cloud Platform.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Google Cloud Platform                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐      ┌──────────────┐     ┌─────────────┐ │
│  │   Cloud     │      │    Cloud     │     │   Cloud SQL │ │
│  │   Run       │◄────►│     Run      │◄───►│  PostgreSQL │ │
│  │  (Frontend) │      │  (Backend)   │     │             │ │
│  │   Angular   │      │   FastAPI    │     └─────────────┘ │
│  └─────────────┘      └──────────────┘                      │
│                              │                               │
│                              ▼                               │
│                    ┌──────────────────┐                     │
│                    │   Cloud Run      │                     │
│                    │ (notification-   │                     │
│                    │  svc) ✅         │                     │
│                    └──────────────────┘                     │
│                              │                               │
│                              ▼                               │
│                    ┌──────────────────┐                     │
│                    │   Pub/Sub        │                     │
│                    │   Topics         │                     │
│                    └──────────────────┘                     │
│                              │                               │
│                              ▼                               │
│                    ┌──────────────────┐                     │
│                    │   Secret Manager │                     │
│                    │   (Credentials)  │                     │
│                    └──────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

## ✅ Prerequisites

- [x] GCP Project: `smarthandoff` 
- [x] Cloud SQL PostgreSQL instance running
- [x] Cloud SQL Proxy configured locally
- [x] notification-svc deployed ✅
- [x] gcloud CLI authenticated
- [ ] Backend deployment
- [ ] Frontend deployment

## 📦 What's Already Deployed

| Service | Status | URL |
|---------|--------|-----|
| notification-svc | ✅ Live | https://notification-service-h67r7fyswq-uc.a.run.app |
| backend | ⏳ Ready to deploy | TBD |
| frontend | ⏳ Ready to deploy | TBD |

---

## 🚀 Deployment Steps

### 1. Deploy Backend API

The backend is a FastAPI application with:
- PostgreSQL database (already configured)
- JWT authentication
- RBAC authorization
- FHIR R4 support
- LangChain + Vertex AI integration

**Deploy Command:**

```powershell
cd scripts
.\deploy-backend.ps1
```

**What it does:**
1. Builds Docker image from `backend/Dockerfile`
2. Pushes to Artifact Registry
3. Deploys to Cloud Run
4. Connects to Cloud SQL instance
5. Configures environment variables

**Expected Output:**
```
Service [smarthandoff-backend] revision [smarthandoff-backend-00001-xxx] has been deployed
Service URL: https://smarthandoff-backend-XXXXX-uc.a.run.app
```

**Environment Variables Set:**
- `DATABASE_URL`: PostgreSQL connection string (Cloud SQL Unix socket)
- Additional vars can be added via `--set-env-vars` flag

---

### 2. Deploy Frontend (Angular)

The frontend is built with Angular 17 and served via nginx.

**Before deploying**, update the backend API URL:

1. Edit `frontend/src/environments/environment.prod.ts`:
```typescript
export const environment = {
  production: true,
  apiUrl: 'https://smarthandoff-backend-XXXXX-uc.a.run.app/api/v1'
};
```

2. Deploy:
```powershell
cd scripts
.\deploy-frontend.ps1 -BackendUrl "https://smarthandoff-backend-XXXXX-uc.a.run.app"
```

**What it does:**
1. Builds Angular app (`ng build --configuration production`)
2. Creates nginx container with built artifacts
3. Deploys to Cloud Run
4. Serves on port 8080

**Expected Output:**
```
Service [smarthandoff-frontend] revision [smarthandoff-frontend-00001-xxx] has been deployed
Service URL: https://smarthandoff-frontend-XXXXX-uc.a.run.app
```

---

## 🔧 Post-Deployment Configuration

### 1. Configure CORS on Backend

Add frontend URL to CORS allowed origins in `backend/app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://smarthandoff-frontend-XXXXX-uc.a.run.app",
        "http://localhost:4200"  # For local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Redeploy backend after adding CORS:
```powershell
cd scripts
.\deploy-backend.ps1
```

### 2. Configure Environment Secrets

For production, move sensitive values to Secret Manager:

```powershell
# JWT secret
gcloud secrets create jwt-secret-key --data-file=jwt_key.txt --project=smarthandoff

# Update backend deployment to use secret
gcloud run services update smarthandoff-backend `
    --update-secrets=JWT_SECRET_KEY=jwt-secret-key:latest `
    --region=us-central1 `
    --project=smarthandoff
```

### 3. Run Database Migrations

```powershell
# Connect via Cloud SQL Proxy
cd backend
alembic upgrade head
```

### 4. Set Up Custom Domains (Optional)

**Backend:**
```powershell
gcloud run domain-mappings create --service smarthandoff-backend --domain api.smarthandoff.com --region us-central1
```

**Frontend:**
```powershell
gcloud run domain-mappings create --service smarthandoff-frontend --domain app.smarthandoff.com --region us-central1
```

---

## 🔍 Verification & Testing

### 1. Health Checks

**Backend:**
```powershell
curl https://smarthandoff-backend-XXXXX-uc.a.run.app/health
# Expected: {"status":"healthy"}
```

**Frontend:**
```powershell
curl https://smarthandoff-frontend-XXXXX-uc.a.run.app/health
# Expected: healthy
```

**Notification Service:**
```powershell
curl https://notification-service-h67r7fyswq-uc.a.run.app/health
# Expected: {"status":"ok"}
```

### 2. Test API Endpoints

```powershell
# Get API docs
curl https://smarthandoff-backend-XXXXX-uc.a.run.app/docs

# Test authentication
curl -X POST https://smarthandoff-backend-XXXXX-uc.a.run.app/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"test","password":"test"}'
```

### 3. View Logs

**Backend:**
```powershell
gcloud logging tail "resource.labels.service_name=smarthandoff-backend" --project=smarthandoff
```

**Frontend:**
```powershell
gcloud logging tail "resource.labels.service_name=smarthandoff-frontend" --project=smarthandoff
```

---

## 📊 Monitoring & Observability

### Cloud Monitoring Dashboard

1. Go to: https://console.cloud.google.com/monitoring
2. Create dashboard with widgets for:
   - Request latency (p50, p95, p99)
   - Error rate
   - Request count
   - Container CPU/Memory usage
   - Database connection pool

### Set Up Alerts

```powershell
# High error rate alert
gcloud alpha monitoring policies create --notification-channels=YOUR_CHANNEL_ID `
  --display-name="High Error Rate - Backend" `
  --condition-display-name="Error rate > 5%" `
  --condition-threshold-value=0.05 `
  --condition-resource-type="cloud_run_revision"
```

---

## 💰 Cost Optimization

**Current Configuration:**

| Service | Pricing | Estimated Cost/Month |
|---------|---------|---------------------|
| Frontend (512Mi, 1 CPU, min=1) | $0.00002400/vCPU-sec | ~$50 |
| Backend (1Gi, 2 CPU, min=1) | $0.00002400/vCPU-sec | ~$100 |
| notification-svc (512Mi, 1 CPU, min=1) | $0.00002400/vCPU-sec | ~$50 |
| Cloud SQL (db-f1-micro) | $7/month + storage | ~$15 |
| **Total** | | **~$215/month** |

**To Reduce Costs:**

1. **Use min-instances=0** during development:
```powershell
gcloud run services update smarthandoff-frontend --min-instances=0 --region=us-central1
```

2. **Scale down to smaller instance** for frontend:
```powershell
gcloud run services update smarthandoff-frontend --memory=256Mi --region=us-central1
```

3. **Use Cloud Storage + CDN** for frontend (lower cost for static sites):
```powershell
# Build Angular app
cd frontend
npm run build:prod

# Upload to Cloud Storage
gsutil -m cp -r dist/smarthandoff-frontend/* gs://smarthandoff-frontend/

# Enable Cloud CDN
gcloud compute backend-buckets add-backend --global --enable-cdn
```

---

## 🔒 Security Checklist

- [ ] Enable Identity-Aware Proxy (IAP) for backend
- [ ] Restrict Cloud Run ingress to internal & Cloud Load Balancing
- [ ] Enable VPC Service Controls
- [ ] Use Secret Manager for all credentials
- [ ] Enable Cloud Armor for DDoS protection
- [ ] Set up audit logging
- [ ] Configure Binary Authorization for container signing
- [ ] Enable HTTPS-only (enforced by default on Cloud Run)
- [ ] Implement rate limiting on API Gateway

---

## 🛠️ Troubleshooting

### Issue: "Permission Denied" during deployment

**Solution:** Grant necessary IAM roles
```powershell
gcloud projects add-iam-policy-binding smarthandoff `
    --member="user:YOUR_EMAIL@gmail.com" `
    --role="roles/run.admin"
```

### Issue: Frontend can't connect to backend

**Solution:** Check CORS configuration and ensure backend URL is correct in environment files.

### Issue: Database connection timeout

**Solution:** Ensure Cloud SQL instance is running and connection string uses Unix socket path for Cloud Run:
```
postgresql+asyncpg://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE
```

### Issue: Container fails to start

**Solution:** Check logs for specific error:
```powershell
gcloud logging read "resource.labels.service_name=SERVICE_NAME" --limit=50 --format=json
```

---

## 📚 Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud SQL Connections from Cloud Run](https://cloud.google.com/sql/docs/postgres/connect-run)
- [FastAPI Deployment Best Practices](https://fastapi.tiangolo.com/deployment/)
- [Angular Production Build Guide](https://angular.io/guide/deployment)
- [GCP Well-Architected Framework](https://cloud.google.com/architecture/framework)

---

## 🎯 Next Steps

1. **Deploy Backend**: Run `.\scripts\deploy-backend.ps1`
2. **Deploy Frontend**: Run `.\scripts\deploy-frontend.ps1`
3. **Configure CORS**: Update backend CORS origins
4. **Run Migrations**: Apply database schema
5. **Test End-to-End**: Verify full application flow
6. **Set Up Monitoring**: Create Cloud Monitoring dashboard
7. **Configure CI/CD**: Automate deployments via Cloud Build

---

**Need Help?** Check the troubleshooting section or review deployment logs:
```powershell
gcloud logging read "resource.type=cloud_run_revision" --limit=100 --project=smarthandoff
```
