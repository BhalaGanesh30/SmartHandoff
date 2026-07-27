# Quick script to enable public access via gcloud CLI
# Run this if you have gcloud permissions

Write-Host "Enabling public access to smarthandoff-frontend..." -ForegroundColor Yellow

gcloud run services add-iam-policy-binding smarthandoff-frontend `
  --region=us-central1 `
  --project=smarthandoff `
  --member="allUsers" `
  --role="roles/run.invoker"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Public access enabled successfully!" -ForegroundColor Green
    Write-Host "`nFrontend URL: https://smarthandoff-frontend-52528248131.us-central1.run.app" -ForegroundColor Cyan
    Write-Host "`nPlease refresh your browser to see the changes." -ForegroundColor Yellow
} else {
    Write-Host "`n❌ Failed to enable public access." -ForegroundColor Red
    Write-Host "Please follow the manual steps in FRONTEND-FIX-GUIDE.md" -ForegroundColor Yellow
}
