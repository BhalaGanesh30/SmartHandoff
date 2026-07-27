# Frontend Deployment Fix Guide

## Current Issues

1. ✅ **Dockerfile Fixed** - Updated to properly serve Angular app (not nginx welcome page)
2. ⚠️ **Forbidden Error** - Cloud Run service needs public access enabled
3. ⚠️ **Deployment** - Needs redeployment with fixed Dockerfile

---

## Quick Fix via GCP Console

### Step 1: Enable Public Access (Fix "Forbidden" Error)

1. Open [Cloud Run Console](https://console.cloud.google.com/run/detail/us-central1/smarthandoff-frontend?project=smarthandoff)

2. Click the **SECURITY** tab

3. Under **Authentication**, select:
   - ☑️ **Allow unauthenticated invocations**

4. Click **SAVE**

5. Wait 10-15 seconds, then refresh your browser at:
   ```
   https://smarthandoff-frontend-52528248131.us-central1.run.app
   ```

---

### Step 2: Redeploy with Fixed Dockerfile

#### Option A: Via Cloud Build (Recommended)

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers?project=smarthandoff)

2. Click **CREATE TRIGGER**

3. Configure:
   - **Name**: `deploy-frontend`
   - **Event**: Manual invocation
   - **Source**: Repository (link your GitHub/GitLab)
   - **Branch**: `main` or your current branch
   - **Build Configuration**: Dockerfile
   - **Dockerfile location**: `frontend/Dockerfile`
   - **Substitution variables**:
     - `_SERVICE_NAME` = `smarthandoff-frontend`
     - `_REGION` = `us-central1`

4. Add inline build config:

```yaml
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/smarthandoff-frontend:$SHORT_SHA'
      - '-f'
      - 'frontend/Dockerfile'
      - './frontend'

  # Push the container image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/smarthandoff-frontend:$SHORT_SHA'

  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'gcloud'
      - 'run'
      - 'deploy'
      - 'smarthandoff-frontend'
      - '--image'
      - 'gcr.io/$PROJECT_ID/smarthandoff-frontend:$SHORT_SHA'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
```

5. Click **RUN TRIGGER**

#### Option B: Via Cloud Console UI

1. Go to [Cloud Run Services](https://console.cloud.google.com/run?project=smarthandoff)

2. Click **smarthandoff-frontend**

3. Click **EDIT & DEPLOY NEW REVISION**

4. Under **Container image URL**, click **SELECT**

5. Click **SOURCE REPOSITORY** tab

6. Connect your repository and select:
   - **Branch**: `main`
   - **Build Type**: Dockerfile
   - **Dockerfile path**: `/frontend/Dockerfile`
   - **Build context directory**: `/frontend`

7. Click **BUILD**

8. Wait for build to complete (5-7 minutes)

9. Click **DEPLOY**

#### Option C: Via Cloud Shell (If permissions allow)

Open Cloud Shell and run:

```bash
# Set project
gcloud config set project smarthandoff

# Navigate to frontend
cd /path/to/SmartHandoff/frontend

# Deploy
gcloud run deploy smarthandoff-frontend \
  --source . \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=1 \
  --max-instances=5 \
  --memory=512Mi \
  --cpu=1 \
  --port=8080
```

---

## What Was Fixed in the Dockerfile

The updated Dockerfile now:

1. ✅ Removes default nginx config that was causing conflicts
2. ✅ Clears the default nginx HTML folder
3. ✅ Properly copies Angular build artifacts from correct path
4. ✅ Verifies files were copied correctly
5. ✅ Tests nginx configuration before starting

**Before:**
```dockerfile
# Stage 2: Serve with nginx
FROM nginx:alpine
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist/smarthandoff-frontend/browser /usr/share/nginx/html
```

**After:**
```dockerfile
# Stage 2: Serve with nginx
FROM nginx:alpine

# Remove default nginx config and default html
RUN rm -rf /etc/nginx/conf.d/default.conf
RUN rm -rf /usr/share/nginx/html/*

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built artifacts from builder
COPY --from=builder /app/dist/smarthandoff-frontend/browser /usr/share/nginx/html

# Verify files were copied
RUN ls -la /usr/share/nginx/html/

# Create a simple test to ensure nginx can start
RUN nginx -t
```

---

## Verification Steps

After redeployment:

1. **Check Service Status**
   ```bash
   gcloud run services describe smarthandoff-frontend \
     --region=us-central1 \
     --format="value(status.conditions)"
   ```

2. **Open in Browser**
   ```
   https://smarthandoff-frontend-52528248131.us-central1.run.app
   ```

3. **Expected Behavior:**
   - ✅ Should redirect to `/dashboard`
   - ✅ Since authGuard is active, should redirect to `/login`
   - ✅ Should show SmartHandoff login page (NOT nginx welcome page)
   - ✅ Should NOT show "Forbidden" error

4. **Check Logs**
   ```bash
   gcloud run services logs read smarthandoff-frontend \
     --region=us-central1 \
     --limit=50
   ```

---

## Backend Configuration Needed

Once frontend is working, ensure backend CORS allows the frontend URL:

**File:** `backend/app/main.py`

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://smarthandoff-frontend-52528248131.us-central1.run.app",
        "http://localhost:4200"  # For local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Redeploy backend after adding CORS.

---

## Troubleshooting

### Issue: Still seeing nginx welcome page
- **Solution**: Clear browser cache (Ctrl+Shift+R) or try incognito mode

### Issue: "Forbidden" error persists
- **Solution**: Ensure "Allow unauthenticated invocations" is enabled in Security tab

### Issue: 404 errors on refresh
- **Solution**: nginx.conf already has `try_files $uri $uri/ /index.html;` - this is correct

### Issue: Can't access Cloud Console
- **Solution**: Contact your GCP admin and request these roles:
  - `roles/run.admin` or `roles/run.developer`
  - `roles/cloudbuild.builds.editor`

---

## Next Steps

After frontend is working:

1. ✅ Deploy backend API
2. ✅ Configure CORS on backend
3. ✅ Update frontend environment with backend URL
4. ✅ Test end-to-end authentication flow
5. ✅ Set up custom domain (optional)

---

## Support

If you encounter issues:

1. Check [Cloud Run Logs](https://console.cloud.google.com/run/detail/us-central1/smarthandoff-frontend/logs?project=smarthandoff)
2. Review [Cloud Build History](https://console.cloud.google.com/cloud-build/builds?project=smarthandoff)
3. Verify [IAM Permissions](https://console.cloud.google.com/iam-admin/iam?project=smarthandoff)

---

**Updated:** 2026-07-27  
**Status:** Ready to deploy
