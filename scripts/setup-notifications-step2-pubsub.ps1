# Step 2: Create Pub/Sub Topics and Subscriptions

param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "smarthandoff"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SmartHandoff - Pub/Sub Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set project
gcloud config set project $ProjectId

# Enable Pub/Sub API
Write-Host "[1/5] Enabling Pub/Sub API..." -ForegroundColor Yellow
gcloud services enable pubsub.googleapis.com --project=$ProjectId
Write-Host "OK Pub/Sub API enabled" -ForegroundColor Green
Write-Host ""

# Create topics
Write-Host "[2/5] Creating Pub/Sub topics..." -ForegroundColor Yellow

Write-Host "  Creating notification-requests topic..." -ForegroundColor Gray
gcloud pubsub topics create notification-requests --project=$ProjectId 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK notification-requests topic created" -ForegroundColor Green
} else {
    Write-Host "  WARN notification-requests topic already exists" -ForegroundColor Yellow
}

Write-Host "  Creating care-team-alerts topic..." -ForegroundColor Gray
gcloud pubsub topics create care-team-alerts --project=$ProjectId 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK care-team-alerts topic created" -ForegroundColor Green
} else {
    Write-Host "  WARN care-team-alerts topic already exists" -ForegroundColor Yellow
}

# Create subscriptions
Write-Host ""
Write-Host "[3/5] Creating Pub/Sub subscriptions..." -ForegroundColor Yellow

Write-Host "  Creating notification-service-sub subscription..." -ForegroundColor Gray
gcloud pubsub subscriptions create notification-service-sub `
  --topic=notification-requests `
  --ack-deadline=60 `
  --message-retention-duration=7d `
  --project=$ProjectId 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK notification-service-sub subscription created" -ForegroundColor Green
} else {
    Write-Host "  WARN notification-service-sub subscription already exists" -ForegroundColor Yellow
}

Write-Host "  Creating care-team-alerts-sub subscription..." -ForegroundColor Gray
gcloud pubsub subscriptions create care-team-alerts-sub `
  --topic=care-team-alerts `
  --ack-deadline=60 `
  --message-retention-duration=7d `
  --project=$ProjectId 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK care-team-alerts-sub subscription created" -ForegroundColor Green
} else {
    Write-Host "  WARN care-team-alerts-sub subscription already exists" -ForegroundColor Yellow
}

# Verify setup
Write-Host ""
Write-Host "[4/5] Verifying topics..." -ForegroundColor Yellow
gcloud pubsub topics list --project=$ProjectId --filter="name:(notification OR care-team)" --format="table(name)"

Write-Host ""
Write-Host "[5/5] Verifying subscriptions..." -ForegroundColor Yellow
gcloud pubsub subscriptions list --project=$ProjectId --format="table(name,topic,ackDeadlineSeconds)"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "OK Pub/Sub Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Step: Run setup-notifications-step3-iam.ps1" -ForegroundColor Yellow
Write-Host ""
