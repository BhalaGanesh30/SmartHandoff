# Step 4: Deploy Notification Service to Cloud Run

param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "smarthandoff",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-central1",
    
    [Parameter(Mandatory=$false)]
    [string]$SendGridFromEmail = "noreply@smarthandoff.health"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SmartHandoff - Deploy Notification Service" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get Twilio phone number from secret
Write-Host "[1/6] Retrieving Twilio phone number from Secret Manager..." -ForegroundColor Yellow
$TWILIO_PHONE = gcloud secrets versions access latest --secret=twilio-phone-number --project=$ProjectId
Write-Host "OK Twilio phone: $TWILIO_PHONE" -ForegroundColor Green
Write-Host ""

# Prompt for SendGrid sender email if not provided
if ($SendGridFromEmail -eq "noreply@smarthandoff.health") {
    Write-Host "Current SendGrid sender email: $SendGridFromEmail" -ForegroundColor Yellow
    $customEmail = Read-Host "Press Enter to use this email, or type a different verified email"
    if ($customEmail) {
        $SendGridFromEmail = $customEmail
    }
}

# Set project
gcloud config set project $ProjectId

$SERVICE_ACCOUNT = "notification-service@$ProjectId.iam.gserviceaccount.com"
$DATABASE_URL = "postgresql+asyncpg://postgres:SmartHandoff%40123@/smarthandoff?host=/cloudsql/$ProjectId`:$Region`:smarthandoff"

# Enable required APIs
Write-Host ""
Write-Host "[2/6] Enabling required APIs..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com --project=$ProjectId
gcloud services enable cloudbuild.googleapis.com --project=$ProjectId
Write-Host "OK APIs enabled" -ForegroundColor Green

# Navigate to service directory
Write-Host ""
Write-Host "[3/6] Preparing service directory..." -ForegroundColor Yellow
$ServiceDir = "$env:USERPROFILE\source\repos\SmartHandoff\services\notification-svc"
if (Test-Path $ServiceDir) {
    Set-Location $ServiceDir
    Write-Host "OK Service directory: $ServiceDir" -ForegroundColor Green
} else {
    Write-Host "ERROR Service directory not found: $ServiceDir" -ForegroundColor Red
    exit 1
}

# Deploy to Cloud Run
Write-Host ""
Write-Host "[4/6] Deploying to Cloud Run..." -ForegroundColor Yellow
Write-Host "This may take 5-10 minutes..." -ForegroundColor Gray
Write-Host ""

gcloud run deploy notification-service `
  --source . `
  --project=$ProjectId `
  --region=$Region `
  --platform=managed `
  --service-account=$SERVICE_ACCOUNT `
  --set-env-vars="DATABASE_URL=$DATABASE_URL,GCP_PROJECT_ID=$ProjectId,PUBSUB_SUBSCRIPTION_ID=notification-service-sub,SENDGRID_FROM_EMAIL=$SendGridFromEmail,TWILIO_FROM_NUMBER=$TWILIO_PHONE" `
  --add-cloudsql-instances="$ProjectId`:$Region`:smarthandoff" `
  --allow-unauthenticated `
  --min-instances=1 `
  --max-instances=10 `
  --memory=512Mi `
  --cpu=1 `
  --timeout=300 `
  --port=8080

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR Deployment failed!" -ForegroundColor Red
    Write-Host "Check build logs with:" -ForegroundColor Yellow
    Write-Host "  gcloud builds list --project=$ProjectId --limit=5" -ForegroundColor Gray
    exit 1
}

# Get service URL
Write-Host ""
Write-Host "[5/6] Retrieving service URL..." -ForegroundColor Yellow
$SERVICE_URL = gcloud run services describe notification-service `
  --project=$ProjectId `
  --region=$Region `
  --format='value(status.url)'

Write-Host "OK Service URL: $SERVICE_URL" -ForegroundColor Green

# Test health endpoint
Write-Host ""
Write-Host "[6/6] Testing service health..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$SERVICE_URL/health" -Method Get -ErrorAction Stop
    if ($response.status -eq "healthy") {
        Write-Host "OK Health check passed" -ForegroundColor Green
    } else {
        Write-Host "WARN Health check returned unexpected response" -ForegroundColor Yellow
    }
} catch {
    Write-Host "WARN Health check failed (this might be normal on first deploy)" -ForegroundColor Yellow
}

# Display summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "OK Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Service Details:" -ForegroundColor Cyan
Write-Host "  Name:           notification-service" -ForegroundColor White
Write-Host "  Region:         $Region" -ForegroundColor White
Write-Host "  Project:        $ProjectId" -ForegroundColor White
Write-Host "  Service Account: $SERVICE_ACCOUNT" -ForegroundColor White
Write-Host "  URL:            $SERVICE_URL" -ForegroundColor White
Write-Host ""
Write-Host "Twilio Webhook Configuration:" -ForegroundColor Cyan
Write-Host "  URL: $SERVICE_URL/webhooks/twilio/status" -ForegroundColor Yellow
Write-Host "  Method: POST" -ForegroundColor Yellow
Write-Host ""
Write-Host "Configure this webhook in Twilio Console:" -ForegroundColor Yellow
Write-Host "  https://console.twilio.com/us1/develop/phone-numbers/manage/incoming" -ForegroundColor Gray
Write-Host ""
Write-Host "Next Step:" -ForegroundColor Cyan
Write-Host "  1. Configure Twilio webhook (see URL above)" -ForegroundColor White
Write-Host "  2. Test with: .\scripts\setup-notifications-step5-test.ps1" -ForegroundColor White
Write-Host ""

# Save URL to file for next script
$SERVICE_URL | Out-File -FilePath "$env:TEMP\notification-service-url.txt" -Encoding UTF8
