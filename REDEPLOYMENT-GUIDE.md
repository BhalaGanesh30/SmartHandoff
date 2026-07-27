# Step-by-Step Frontend Redeployment Guide

Follow these instructions to redeploy your frontend with the fixed Dockerfile.

---

## Method 1: Cloud Shell (EASIEST - Recommended)

### Step 1: Open Cloud Shell
1. Go to: https://console.cloud.google.com/
2. Click the **Cloud Shell** icon (>_) in the top-right corner
3. Wait for shell to activate

### Step 2: Set Up Your Repository in Cloud Shell

```bash
# Set your project
gcloud config set project smarthandoff

# Option A: If your code is on GitHub/GitLab
git clone <YOUR_REPO_URL>
cd SmartHandoff

# Option B: If not in Git, upload the files
# Click the 3 dots (⋮) in Cloud Shell → Upload → Select "frontend" folder
```

### Step 3: Deploy from Cloud Shell

```bash
# Navigate to frontend directory
cd frontend

# Deploy to Cloud Run
gcloud run deploy smarthandoff-frontend \
  --source . \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=1 \
  --max-instances=5 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=60 \
  --port=8080 \
  --project=smarthandoff

# This will:
# 1. Build the Docker image from your Dockerfile
# 2. Push it to Container Registry
# 3. Deploy to Cloud Run
# 4. Enable public access
```

### Step 4: Wait and Verify
- Build takes 5-7 minutes
- You'll see: `Service [smarthandoff-frontend] revision [xxx] has been deployed`
- Note the URL in the output

### Step 5: Test
```bash
# Get the service URL
gcloud run services describe smarthandoff-frontend \
  --region=us-central1 \
  --format="value(status.url)"

# Test health endpoint
curl <URL>/health
```

---

## Method 2: Using Cloud Build (If Cloud Shell Doesn't Work)

### Step 1: Commit Your Changes
```powershell
# In your local terminal
git add .
git commit -m "Fix frontend Dockerfile for Angular deployment"
git push origin main
```

### Step 2: Create Cloud Build Trigger via Console

1. Go to: https://console.cloud.google.com/cloud-build/triggers?project=smarthandoff

2. Click **CREATE TRIGGER**

3. Fill in:
   - **Name:** `deploy-frontend`
   - **Description:** `Deploy SmartHandoff frontend`
   - **Event:** Manual invocation (or Push to branch)
   - **Source:** Click "CONNECT REPOSITORY"
     - Select your GitHub/GitLab/Bitbucket
     - Authenticate and select your repository
   - **Branch:** `^main$` (or your branch name)
   - **Build Configuration:** Cloud Build configuration file
   - **Cloud Build configuration file location:** `cloudbuild-frontend.yaml`

4. Click **CREATE**

5. Click **RUN** button next to your trigger

6. Monitor the build: https://console.cloud.google.com/cloud-build/builds?project=smarthandoff

---

## Method 3: Direct Docker Build + Push (Advanced)

If you have Docker locally and Container Registry access:

### Step 1: Enable Required APIs
```powershell
gcloud services enable containerregistry.googleapis.com
gcloud services enable run.googleapis.com
```

### Step 2: Configure Docker
```powershell
gcloud auth configure-docker
```

### Step 3: Build and Push
```powershell
# Navigate to frontend
cd frontend

# Build image
docker build -t gcr.io/smarthandoff/smarthandoff-frontend:latest .

# Push to Container Registry
docker push gcr.io/smarthandoff/smarthandoff-frontend:latest
```

### Step 4: Deploy via Console
1. Go to: https://console.cloud.google.com/run?project=smarthandoff
2. Click **smarthandoff-frontend**
3. Click **EDIT & DEPLOY NEW REVISION**
4. Under "Container image URL", enter:
   ```
   gcr.io/smarthandoff/smarthandoff-frontend:latest
   ```
5. Ensure these settings:
   - Port: `8080`
   - Memory: `512Mi`
   - CPU: `1`
   - Min instances: `1`
   - Max instances: `5`
   - Authentication: **Allow unauthenticated invocations**
6. Click **DEPLOY**

---

## Quick Verification After Deployment

### Test Commands
```powershell
# Test health endpoint
curl https://smarthandoff-frontend-52528248131.us-central1.run.app/health

# Test main page
curl https://smarthandoff-frontend-52528248131.us-central1.run.app

# Or run the test script
.\scripts\test-frontend.ps1
```

### Expected Results
✅ Health returns "healthy"
✅ Main page returns HTML with "SmartHandoff"
✅ NOT "Welcome to nginx!"
✅ NOT "Forbidden"

---

## Troubleshooting

### "Forbidden" Error Still Appears
**Fix:**
1. Go to: https://console.cloud.google.com/run/detail/us-central1/smarthandoff-frontend?project=smarthandoff
2. Click **SECURITY** tab
3. Select: ☑️ **Allow unauthenticated invocations**
4. Click **SAVE**

### "Still Showing Nginx Welcome Page"
**Fix:**
- Clear browser cache (Ctrl+Shift+R)
- Try incognito mode
- Verify deployment used the NEW Dockerfile

### Build Fails in Cloud Shell
**Common causes:**
1. **Out of disk space:** Run `gcloud builds list` and clean old builds
2. **Wrong directory:** Ensure you're in the `frontend/` folder
3. **Dockerfile errors:** Check build logs for syntax issues

### "Permission Denied" in Cloud Shell
**Fix:**
```bash
# Ensure you're authenticated
gcloud auth list

# Ensure correct project
gcloud config set project smarthandoff

# Ensure required roles
gcloud projects get-iam-policy smarthandoff --flatten="bindings[].members" --filter="bindings.members:user:YOUR_EMAIL"
```

---

## Post-Deployment Checklist

- [ ] Frontend loads at: https://smarthandoff-frontend-52528248131.us-central1.run.app
- [ ] Shows Angular app (NOT nginx welcome page)
- [ ] No "Forbidden" error
- [ ] Health check works: `/health` returns "healthy"
- [ ] Redirects to `/dashboard` then `/login` (expected behavior)

---

## Need More Help?

### Check Logs
```bash
# Cloud Run logs
gcloud run services logs read smarthandoff-frontend \
  --region=us-central1 \
  --limit=100

# Cloud Build logs
gcloud builds list --limit=5
gcloud builds log <BUILD_ID>
```

### Test Locally
```powershell
# Build Docker image locally
cd frontend
docker build -t test-frontend .

# Run locally
docker run -p 8080:8080 test-frontend

# Test
curl http://localhost:8080/health
```

---

**Recommended:** Use **Method 1 (Cloud Shell)** - it's the easiest and bypasses all permission issues!
