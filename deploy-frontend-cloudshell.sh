#!/bin/bash
# Cloud Shell Deployment Script for SmartHandoff Frontend
# Copy and paste this entire script into Cloud Shell

set -e  # Exit on error

echo "=================================================="
echo "SmartHandoff Frontend Deployment"
echo "=================================================="
echo ""

# Set project
echo "Setting project to smarthandoff..."
gcloud config set project smarthandoff

# Get current user
CURRENT_USER=$(gcloud config get-value account)
echo "Deploying as: $CURRENT_USER"
echo ""

# Check if we're in the right directory
if [ ! -f "Dockerfile" ]; then
    echo "❌ Error: Dockerfile not found!"
    echo "Please ensure you're in the frontend/ directory"
    echo ""
    echo "If you cloned the repo, run:"
    echo "  cd SmartHandoff/frontend"
    echo ""
    echo "If you need to upload files, click the 3 dots (⋮) in Cloud Shell → Upload"
    exit 1
fi

echo "✅ Dockerfile found"
echo ""

# Deploy
echo "Starting deployment to Cloud Run..."
echo "This will take 5-7 minutes..."
echo ""

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

if [ $? -eq 0 ]; then
    echo ""
    echo "=================================================="
    echo "✅ Deployment Successful!"
    echo "=================================================="
    echo ""
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe smarthandoff-frontend \
      --region=us-central1 \
      --format="value(status.url)")
    
    echo "Frontend URL: $SERVICE_URL"
    echo ""
    
    # Test health endpoint
    echo "Testing health endpoint..."
    curl -s "$SERVICE_URL/health"
    echo ""
    
    echo ""
    echo "Next steps:"
    echo "1. Open in browser: $SERVICE_URL"
    echo "2. Should see Angular login page (NOT nginx welcome)"
    echo "3. Run local test: .\scripts\test-frontend.ps1"
    echo ""
else
    echo ""
    echo "=================================================="
    echo "❌ Deployment Failed"
    echo "=================================================="
    echo ""
    echo "Check the error message above."
    echo "Common issues:"
    echo "  - Not in frontend/ directory"
    echo "  - Missing permissions"
    echo "  - Dockerfile syntax error"
    echo ""
    echo "View build logs:"
    echo "  https://console.cloud.google.com/cloud-build/builds?project=smarthandoff"
fi
