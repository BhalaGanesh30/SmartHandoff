#!/bin/bash
# Quick script to enable public access via gcloud CLI
# Run this if you have gcloud permissions

echo "Enabling public access to smarthandoff-frontend..."

gcloud run services add-iam-policy-binding smarthandoff-frontend \
  --region=us-central1 \
  --project=smarthandoff \
  --member="allUsers" \
  --role="roles/run.invoker"

if [ $? -eq 0 ]; then
    echo "✅ Public access enabled successfully!"
    echo ""
    echo "Frontend URL: https://smarthandoff-frontend-52528248131.us-central1.run.app"
    echo ""
    echo "Please refresh your browser to see the changes."
else
    echo "❌ Failed to enable public access."
    echo "Please follow the manual steps in FRONTEND-FIX-GUIDE.md"
fi
