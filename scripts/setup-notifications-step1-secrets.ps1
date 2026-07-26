# Step 1: Create GCP Secrets for Notification Service
# Run this AFTER you have obtained credentials from Twilio and SendGrid

param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "smarthandoff"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SmartHandoff - Notification Secrets Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set project
$env:GCP_PROJECT_ID = $ProjectId
gcloud config set project $ProjectId

# Enable Secret Manager API
Write-Host "[1/6] Enabling Secret Manager API..." -ForegroundColor Yellow
gcloud services enable secretmanager.googleapis.com --project=$ProjectId
Write-Host "✓ Secret Manager API enabled" -ForegroundColor Green
Write-Host ""

# Collect credentials from user
Write-Host "[2/6] Collecting Twilio Credentials..." -ForegroundColor Yellow
Write-Host "Get these from: https://console.twilio.com/" -ForegroundColor Gray
Write-Host ""

$TWILIO_ACCOUNT_SID = Read-Host "Enter Twilio Account SID (starts with AC...)"
$TWILIO_AUTH_TOKEN_PLAIN = Read-Host "Enter Twilio Auth Token"
$TWILIO_VERIFY_SID = Read-Host "Enter Twilio Verify Service SID (starts with VA...)"
$TWILIO_PHONE = Read-Host "Enter Twilio Phone Number (format: +15551234567)"

Write-Host ""
Write-Host "[3/6] Collecting SendGrid Credentials..." -ForegroundColor Yellow
Write-Host "Get these from: https://app.sendgrid.com/settings/api_keys" -ForegroundColor Gray
Write-Host ""

$SENDGRID_KEY_PLAIN = Read-Host "Enter SendGrid API Key (starts with SG.)"

# Create secrets
Write-Host ""
Write-Host "[4/6] Creating secrets in GCP Secret Manager..." -ForegroundColor Yellow

# Twilio Account SID
Write-Host "  Creating twilio-account-sid..." -ForegroundColor Gray
echo $TWILIO_ACCOUNT_SID | gcloud secrets create twilio-account-sid `
  --project=$ProjectId `
  --replication-policy=automatic `
  --data-file=- 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ twilio-account-sid created" -ForegroundColor Green
} else {
    Write-Host "  ⚠ twilio-account-sid already exists, updating version..." -ForegroundColor Yellow
    echo $TWILIO_ACCOUNT_SID | gcloud secrets versions add twilio-account-sid --data-file=- --project=$ProjectId
}

# Twilio Auth Token
Write-Host "  Creating twilio-auth-token..." -ForegroundColor Gray
echo $TWILIO_AUTH_TOKEN_PLAIN | gcloud secrets create twilio-auth-token `
  --project=$ProjectId `
  --replication-policy=automatic `
  --data-file=- 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ twilio-auth-token created" -ForegroundColor Green
} else {
    Write-Host "  ⚠ twilio-auth-token already exists, updating version..." -ForegroundColor Yellow
    echo $TWILIO_AUTH_TOKEN_PLAIN | gcloud secrets versions add twilio-auth-token --data-file=- --project=$ProjectId
}

# Twilio Verify SID
Write-Host "  Creating twilio-verify-service-sid..." -ForegroundColor Gray
echo $TWILIO_VERIFY_SID | gcloud secrets create twilio-verify-service-sid `
  --project=$ProjectId `
  --replication-policy=automatic `
  --data-file=- 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ twilio-verify-service-sid created" -ForegroundColor Green
} else {
    Write-Host "  ⚠ twilio-verify-service-sid already exists, updating version..." -ForegroundColor Yellow
    echo $TWILIO_VERIFY_SID | gcloud secrets versions add twilio-verify-service-sid --data-file=- --project=$ProjectId
}

# Twilio Phone Number
Write-Host "  Creating twilio-phone-number..." -ForegroundColor Gray
echo $TWILIO_PHONE | gcloud secrets create twilio-phone-number `
  --project=$ProjectId `
  --replication-policy=automatic `
  --data-file=- 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ twilio-phone-number created" -ForegroundColor Green
} else {
    Write-Host "  ⚠ twilio-phone-number already exists, updating version..." -ForegroundColor Yellow
    echo $TWILIO_PHONE | gcloud secrets versions add twilio-phone-number --data-file=- --project=$ProjectId
}

# SendGrid API Key
Write-Host "  Creating sendgrid-api-key..." -ForegroundColor Gray
echo $SENDGRID_KEY_PLAIN | gcloud secrets create sendgrid-api-key `
  --project=$ProjectId `
  --replication-policy=automatic `
  --data-file=- 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ sendgrid-api-key created" -ForegroundColor Green
} else {
    Write-Host "  ⚠ sendgrid-api-key already exists, updating version..." -ForegroundColor Yellow
    echo $SENDGRID_KEY_PLAIN | gcloud secrets versions add sendgrid-api-key --data-file=- --project=$ProjectId
}

# Verify secrets
Write-Host ""
Write-Host "[5/6] Verifying secrets..." -ForegroundColor Yellow
gcloud secrets list --project=$ProjectId --filter="name:(twilio OR sendgrid)" --format="table(name,createTime)"

Write-Host ""
Write-Host "[6/6] Testing secret access..." -ForegroundColor Yellow
Write-Host "  Testing twilio-account-sid access..." -ForegroundColor Gray
$testValue = gcloud secrets versions access latest --secret=twilio-account-sid --project=$ProjectId
if ($testValue) {
    Write-Host "  ✓ Secret access verified" -ForegroundColor Green
} else {
    Write-Host "  ✗ Secret access failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✓ Secrets Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Step: Run setup-notifications-step2-pubsub.ps1" -ForegroundColor Yellow
Write-Host ""
