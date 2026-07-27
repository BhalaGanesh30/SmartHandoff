# Step 3: Create Service Account and Grant IAM Permissions

param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "smarthandoff"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SmartHandoff - IAM Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set project
gcloud config set project $ProjectId

$SERVICE_ACCOUNT = "notification-service@$ProjectId.iam.gserviceaccount.com"

# Create service account
Write-Host "[1/5] Creating service account..." -ForegroundColor Yellow
gcloud iam service-accounts create notification-service `
  --display-name="Notification Service" `
  --description="Service account for notification-svc Cloud Run service" `
  --project=$ProjectId 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "OK Service account created: $SERVICE_ACCOUNT" -ForegroundColor Green
} else {
    Write-Host "WARN Service account already exists: $SERVICE_ACCOUNT" -ForegroundColor Yellow
}

# Grant Secret Manager access
Write-Host ""
Write-Host "[2/5] Granting Secret Manager access..." -ForegroundColor Yellow

$SECRETS = @(
    "twilio-account-sid",
    "twilio-auth-token",
    "twilio-verify-service-sid",
    "twilio-phone-number",
    "sendgrid-api-key"
)

foreach ($SECRET in $SECRETS) {
    Write-Host "  Granting access to $SECRET..." -ForegroundColor Gray
    gcloud secrets add-iam-policy-binding $SECRET `
        --project=$ProjectId `
        --member="serviceAccount:$SERVICE_ACCOUNT" `
        --role="roles/secretmanager.secretAccessor" `
        --condition=None 2>$null | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK Access granted to $SECRET" -ForegroundColor Green
    } else {
        Write-Host "  WARN Failed to grant access to $SECRET" -ForegroundColor Yellow
    }
}

# Grant Pub/Sub permissions
Write-Host ""
Write-Host "[3/5] Granting Pub/Sub permissions..." -ForegroundColor Yellow

Write-Host "  Granting subscriber role on notification-service-sub..." -ForegroundColor Gray
gcloud pubsub subscriptions add-iam-policy-binding notification-service-sub `
  --member="serviceAccount:$SERVICE_ACCOUNT" `
  --role="roles/pubsub.subscriber" `
  --project=$ProjectId 2>$null | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK Subscriber role granted" -ForegroundColor Green
} else {
    Write-Host "  WARN Failed to grant subscriber role" -ForegroundColor Yellow
}

Write-Host "  Granting publisher role on care-team-alerts..." -ForegroundColor Gray
gcloud pubsub topics add-iam-policy-binding care-team-alerts `
  --member="serviceAccount:$SERVICE_ACCOUNT" `
  --role="roles/pubsub.publisher" `
  --project=$ProjectId 2>$null | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK Publisher role granted" -ForegroundColor Green
} else {
    Write-Host "  WARN Failed to grant publisher role" -ForegroundColor Yellow
}

# Grant Cloud SQL access
Write-Host ""
Write-Host "[4/5] Granting Cloud SQL client access..." -ForegroundColor Yellow
gcloud projects add-iam-policy-binding $ProjectId `
  --member="serviceAccount:$SERVICE_ACCOUNT" `
  --role="roles/cloudsql.client" `
  --condition=None 2>$null | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "OK Cloud SQL client role granted" -ForegroundColor Green
} else {
    Write-Host "WARN Failed to grant Cloud SQL client role" -ForegroundColor Yellow
}

# Verify service account
Write-Host ""
Write-Host "[5/5] Verifying service account..." -ForegroundColor Yellow
gcloud iam service-accounts describe $SERVICE_ACCOUNT --project=$ProjectId --format="table(email,displayName)"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "OK IAM Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Service Account: $SERVICE_ACCOUNT" -ForegroundColor Cyan
Write-Host ""
Write-Host "Permissions Granted:" -ForegroundColor Cyan
Write-Host "  OK Secret Manager (5 secrets)" -ForegroundColor Green
Write-Host "  OK Pub/Sub Subscriber (notification-service-sub)" -ForegroundColor Green
Write-Host "  OK Pub/Sub Publisher (care-team-alerts)" -ForegroundColor Green
Write-Host "  OK Cloud SQL Client" -ForegroundColor Green
Write-Host ""
Write-Host "Next Step: Run setup-notifications-step4-deploy.ps1" -ForegroundColor Yellow
Write-Host ""
