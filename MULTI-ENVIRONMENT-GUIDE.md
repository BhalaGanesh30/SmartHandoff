# SmartHandoff Multi-Environment Deployment Guide

Complete guide to set up and manage dev, staging, and production environments in GCP.

## 🎯 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      GCP Organization                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │  smarthandoff-   │  │  smarthandoff-   │  │ smarthandoff  │ │
│  │      dev         │  │    staging       │  │    (prod)     │ │
│  ├──────────────────┤  ├──────────────────┤  ├───────────────┤ │
│  │ • Backend (0-3)  │  │ • Backend (1-5)  │  │ • Backend (2) │ │
│  │ • Frontend (0-2) │  │ • Frontend (1-3) │  │ • Frontend (2)│ │
│  │ • Notification   │  │ • Notification   │  │ • Notification│ │
│  │ • Cloud SQL      │  │ • Cloud SQL      │  │ • Cloud SQL   │ │
│  │   (f1-micro)     │  │   (g1-small)     │  │   (custom)    │ │
│  │ • Pub/Sub        │  │ • Pub/Sub        │  │ • Pub/Sub     │ │
│  │ • Secrets        │  │ • Secrets        │  │ • Secrets     │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 📋 Environment Comparison

| Feature | Dev | Staging | Production |
|---------|-----|---------|------------|
| **Purpose** | Development & testing | Pre-production validation | Live users |
| **GCP Project** | `smarthandoff-dev` | `smarthandoff-staging` | `smarthandoff` |
| **Min Instances** | 0 (scale to zero) | 1 (always-on) | 2 (high availability) |
| **Max Instances** | 2-3 | 3-5 | 10+ |
| **Database Tier** | db-f1-micro ($7/mo) | db-g1-small ($25/mo) | db-custom-2-7680 ($150/mo) |
| **Memory** | 256-512Mi | 512Mi-1Gi | 1-2Gi |
| **Estimated Cost** | ~$20/month | ~$80/month | ~$250/month |
| **Data** | Mock/synthetic | Copy of prod (anonymized) | Real PHI |
| **Access** | All developers | QA + senior devs | Ops team only |

---

## 🚀 Quick Start

### Option 1: Use Existing Project for All (Simplest)

Deploy all environments to your existing `smarthandoff` project with service name suffixes:

```powershell
# Deploy dev environment
gcloud run deploy smarthandoff-backend-dev --source ./backend --project=smarthandoff
gcloud run deploy smarthandoff-frontend-dev --source ./frontend --project=smarthandoff

# Deploy prod environment
gcloud run deploy smarthandoff-backend --source ./backend --project=smarthandoff
gcloud run deploy smarthandoff-frontend --source ./frontend --project=smarthandoff
```

**Pros:** Simple, single project to manage, shared billing  
**Cons:** Less isolation, shared quotas, harder to control access

### Option 2: Separate GCP Projects (Recommended)

Create isolated projects for each environment:

```powershell
# 1. Setup dev environment
.\scripts\setup-environment.ps1 -Environment dev

# 2. Setup staging environment
.\scripts\setup-environment.ps1 -Environment staging

# 3. Production already exists (smarthandoff)
```

**Pros:** Complete isolation, separate billing, better security  
**Cons:** More complex, need to manage multiple projects

---

## 📦 Step-by-Step Setup

### Step 1: Create GCP Projects

```powershell
# Create dev project
gcloud projects create smarthandoff-dev --name="SmartHandoff Development"

# Create staging project
gcloud projects create smarthandoff-staging --name="SmartHandoff Staging"

# Link billing (required)
gcloud billing accounts list
gcloud billing projects link smarthandoff-dev --billing-account=YOUR_BILLING_ACCOUNT_ID
gcloud billing projects link smarthandoff-staging --billing-account=YOUR_BILLING_ACCOUNT_ID
```

### Step 2: Run Automated Setup

```powershell
# Setup dev environment (creates DB, Pub/Sub, secrets, service accounts)
.\scripts\setup-environment.ps1 -Environment dev

# Setup staging environment
.\scripts\setup-environment.ps1 -Environment staging
```

**What it does:**
- ✅ Creates GCP project (if needed)
- ✅ Enables required APIs (Cloud Run, SQL, Pub/Sub, Secrets)
- ✅ Creates Cloud SQL instance
- ✅ Creates Pub/Sub topics and subscriptions
- ✅ Creates Secret Manager secrets (placeholders)
- ✅ Creates service accounts with IAM permissions

### Step 3: Update Secrets with Real Values

```powershell
# Dev environment
gcloud secrets versions add jwt-secret-dev --data-file=jwt_key_dev.txt --project=smarthandoff-dev
gcloud secrets versions add twilio-account-sid-dev --data-file=- --project=smarthandoff-dev
# (paste SID, press Enter, then Ctrl+Z)

# Staging environment
gcloud secrets versions add jwt-secret-staging --data-file=jwt_key_staging.txt --project=smarthandoff-staging

# Production (already configured)
```

### Step 4: Run Database Migrations

```powershell
# Connect to dev database
cloud_sql_proxy smarthandoff-dev:us-central1:smarthandoff-dev --port=5434 &

# Run migrations
cd backend
$env:DATABASE_URL="postgresql://postgres:SmartHandoff@123@localhost:5434/smarthandoff_dev"
alembic upgrade head

# Repeat for staging (port 5435)
```

### Step 5: Deploy Services

```powershell
# Deploy all services to dev
.\scripts\deploy-to-env.ps1 -Environment dev -Service all

# Deploy only backend to staging
.\scripts\deploy-to-env.ps1 -Environment staging -Service backend

# Deploy to production
.\scripts\deploy-to-env.ps1 -Environment prod -Service all
```

---

## 🔧 Configuration Management

### Environment Variables by Environment

**Development:**
```bash
ENVIRONMENT=dev
DEBUG=true
LOG_LEVEL=DEBUG
ENABLE_SWAGGER=true
CORS_ORIGINS=http://localhost:4200,https://*-dev-*.run.app
```

**Staging:**
```bash
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
ENABLE_SWAGGER=true
CORS_ORIGINS=https://*-staging-*.run.app
```

**Production:**
```bash
ENVIRONMENT=prod
DEBUG=false
LOG_LEVEL=WARNING
ENABLE_SWAGGER=false
CORS_ORIGINS=https://app.smarthandoff.com
```

### Update Environment Variables

```powershell
# Update backend environment variable
gcloud run services update smarthandoff-backend-dev `
    --update-env-vars="DEBUG=true,LOG_LEVEL=DEBUG" `
    --project=smarthandoff-dev `
    --region=us-central1

# Update secrets
gcloud run services update smarthandoff-backend-dev `
    --update-secrets="JWT_SECRET_KEY=jwt-secret-dev:latest" `
    --project=smarthandoff-dev `
    --region=us-central1
```

---

## 🔄 Deployment Workflows

### Development Workflow

```powershell
# 1. Developer makes changes locally
git checkout -b feature/new-feature

# 2. Test locally
cd backend
uvicorn app.main:app --reload

# 3. Deploy to dev environment for integration testing
.\scripts\deploy-to-env.ps1 -Environment dev -Service backend

# 4. Run integration tests against dev
pytest tests/integration/

# 5. Create PR for review
git push origin feature/new-feature
```

### Staging Deployment (CI/CD)

```yaml
# .github/workflows/deploy-staging.yml
name: Deploy to Staging
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Staging
        run: |
          gcloud run deploy smarthandoff-backend-staging \
            --source ./backend \
            --project=smarthandoff-staging \
            --region=us-central1
```

### Production Deployment (Manual)

```powershell
# 1. Test in staging
curl https://smarthandoff-backend-staging-xxx.run.app/health

# 2. Create release tag
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0

# 3. Deploy to production (requires approval)
.\scripts\deploy-to-env.ps1 -Environment prod -Service all

# 4. Verify deployment
curl https://smarthandoff-backend-xxx.run.app/health

# 5. Monitor logs
gcloud logging tail "resource.labels.service_name=smarthandoff-backend" --project=smarthandoff
```

---

## 🔐 Access Control

### IAM Roles by Environment

**Development:**
- All developers: `roles/run.developer`
- All developers: `roles/cloudsql.client`
- All developers: `roles/viewer`

**Staging:**
- Senior developers: `roles/run.developer`
- QA team: `roles/run.viewer`
- All: `roles/logging.viewer`

**Production:**
- Ops team only: `roles/run.admin`
- Developers: `roles/logging.viewer`
- On-call: `roles/run.viewer`

### Grant Access

```powershell
# Grant developer access to dev environment
gcloud projects add-iam-policy-binding smarthandoff-dev `
    --member="user:developer@company.com" `
    --role="roles/run.developer"

# Grant read-only access to production logs
gcloud projects add-iam-policy-binding smarthandoff `
    --member="group:developers@company.com" `
    --role="roles/logging.viewer"
```

---

## 📊 Monitoring & Logging

### View Logs by Environment

```powershell
# Dev logs
gcloud logging tail "resource.labels.service_name=smarthandoff-backend-dev" --project=smarthandoff-dev

# Staging logs
gcloud logging tail "resource.labels.service_name=smarthandoff-backend-staging" --project=smarthandoff-staging

# Production logs
gcloud logging tail "resource.labels.service_name=smarthandoff-backend" --project=smarthandoff
```

### Set Up Alerts

```powershell
# Alert for production errors
gcloud alpha monitoring policies create `
    --notification-channels=YOUR_CHANNEL_ID `
    --display-name="Production Error Rate" `
    --condition-display-name="Error rate > 1%" `
    --condition-threshold-value=0.01 `
    --project=smarthandoff
```

---

## 💰 Cost Management

### Monthly Cost Breakdown

**Development (scale-to-zero):**
- Cloud Run: $0-20/month
- Cloud SQL (f1-micro): $7/month
- Cloud Build: $5/month
- **Total: ~$20/month**

**Staging (always-on):**
- Cloud Run: $50/month
- Cloud SQL (g1-small): $25/month
- Cloud Build: $5/month
- **Total: ~$80/month**

**Production (high-availability):**
- Cloud Run: $150/month
- Cloud SQL (custom): $150/month
- Cloud Build: $10/month
- **Total: ~$310/month**

### Cost Optimization

```powershell
# Scale dev to zero when not in use
gcloud run services update smarthandoff-backend-dev --min-instances=0 --project=smarthandoff-dev

# Use committed use discounts for production
gcloud compute commitments create prod-commitment --resources=vcpu=4,memory=16 --plan=12-month

# Set up budget alerts
gcloud billing budgets create --billing-account=YOUR_ACCOUNT `
    --display-name="SmartHandoff Dev Budget" `
    --budget-amount=50
```

---

## 🧪 Testing Strategy

### Test Data by Environment

**Development:**
- Synthetic test data
- Mock patients: "Test Patient 001", "Test Patient 002"
- Phone numbers: Twilio test numbers (+15005550006)
- Email: yourname+dev@gmail.com

**Staging:**
- Sanitized copy of production data (PHI removed)
- Real phone numbers (dev team members)
- Real email addresses (dev team members)

**Production:**
- Real PHI (HIPAA-compliant)
- Real patient phone numbers
- Real email addresses

### Load Testing

```powershell
# Test dev environment
ab -n 1000 -c 10 https://smarthandoff-backend-dev-xxx.run.app/health

# Test staging with realistic load
artillery run load-test-staging.yml

# Production smoke test (after deployment)
curl -f https://smarthandoff-backend-xxx.run.app/health || echo "FAILED"
```

---

## 🛠️ Troubleshooting

### Common Issues

**Issue: "Permission denied" when deploying**
```powershell
# Grant yourself deployment permissions
gcloud projects add-iam-policy-binding smarthandoff-dev `
    --member="user:your-email@gmail.com" `
    --role="roles/run.admin"
```

**Issue: "Database connection timeout"**
```powershell
# Check Cloud SQL instance status
gcloud sql instances describe smarthandoff-dev --project=smarthandoff-dev

# Verify service account has cloudsql.client role
gcloud projects get-iam-policy smarthandoff-dev --flatten="bindings[].members" --filter="bindings.role:roles/cloudsql.client"
```

**Issue: "Secret not found"**
```powershell
# List secrets
gcloud secrets list --project=smarthandoff-dev

# Recreate secret
echo "your-secret-value" | gcloud secrets create jwt-secret-dev --data-file=- --project=smarthandoff-dev
```

---

## 📚 Reference

### Quick Commands

```powershell
# List all services across environments
gcloud run services list --project=smarthandoff-dev
gcloud run services list --project=smarthandoff-staging
gcloud run services list --project=smarthandoff

# Switch between projects
gcloud config set project smarthandoff-dev
gcloud config set project smarthandoff-staging
gcloud config set project smarthandoff

# View service details
gcloud run services describe smarthandoff-backend-dev --region=us-central1 --project=smarthandoff-dev

# Rollback deployment
gcloud run services update-traffic smarthandoff-backend-dev --to-revisions=PREVIOUS_REVISION=100 --project=smarthandoff-dev
```

### Configuration Files

- [config/environments.yaml](config/environments.yaml) - Environment definitions
- [scripts/setup-environment.ps1](scripts/setup-environment.ps1) - Setup automation
- [scripts/deploy-to-env.ps1](scripts/deploy-to-env.ps1) - Deployment script
- [.github/workflows/](. github/workflows/) - CI/CD pipelines

---

## 🎓 Best Practices

1. **Never deploy directly to production** - Always test in dev → staging → prod
2. **Use feature flags** - Enable/disable features without redeploying
3. **Tag releases** - Use semantic versioning (v1.2.3)
4. **Monitor costs** - Set up billing alerts for each environment
5. **Rotate secrets regularly** - Especially for production
6. **Use separate databases** - Never share databases across environments
7. **Automate everything** - Manual steps = human errors
8. **Document changes** - Keep changelog updated

---

## 🚨 Emergency Procedures

### Rollback Production Deployment

```powershell
# 1. List recent revisions
gcloud run revisions list --service=smarthandoff-backend --region=us-central1 --project=smarthandoff

# 2. Route all traffic to previous revision
gcloud run services update-traffic smarthandoff-backend `
    --to-revisions=smarthandoff-backend-00008=100 `
    --region=us-central1 `
    --project=smarthandoff

# 3. Verify
curl https://smarthandoff-backend-xxx.run.app/health
```

### Scale Up During Incident

```powershell
# Increase capacity immediately
gcloud run services update smarthandoff-backend `
    --min-instances=5 `
    --max-instances=20 `
    --region=us-central1 `
    --project=smarthandoff
```

---

**Questions?** Check the [DEPLOYMENT-GUIDE.md](DEPLOYMENT-GUIDE.md) for single-environment deployment or contact the DevOps team.
