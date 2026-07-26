# Master Setup Script - Run All Notification Setup Steps
# This script orchestrates the entire notification service setup

param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "smarthandoff"
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SmartHandoff Notification Service" -ForegroundColor Cyan
Write-Host "Complete Setup Wizard" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "This wizard will guide you through:" -ForegroundColor Yellow
Write-Host "  1. Creating GCP secrets (Twilio & SendGrid credentials)" -ForegroundColor White
Write-Host "  2. Setting up Pub/Sub topics and subscriptions" -ForegroundColor White
Write-Host "  3. Creating service account and granting IAM permissions" -ForegroundColor White
Write-Host "  4. Deploying notification service to Cloud Run" -ForegroundColor White
Write-Host "  5. Testing the complete setup" -ForegroundColor White
Write-Host ""
Write-Host "Prerequisites:" -ForegroundColor Yellow
Write-Host "  ✓ Twilio account with SMS-enabled phone number" -ForegroundColor White
Write-Host "  ✓ SendGrid account with verified sender email" -ForegroundColor White
Write-Host "  ✓ GCP project '$ProjectId' with billing enabled" -ForegroundColor White
Write-Host "  ✓ gcloud CLI authenticated and configured" -ForegroundColor White
Write-Host ""

$proceed = Read-Host "Do you have all prerequisites? (y/N)"
if ($proceed -ne "y" -and $proceed -ne "Y") {
    Write-Host ""
    Write-Host "Setup cancelled. Please complete prerequisites first." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Quickstart Guide:" -ForegroundColor Cyan
    Write-Host "  1. Twilio: https://www.twilio.com/try-twilio" -ForegroundColor Gray
    Write-Host "  2. SendGrid: https://signup.sendgrid.com/" -ForegroundColor Gray
    Write-Host "  3. GCP Setup: gcloud auth login && gcloud config set project $ProjectId" -ForegroundColor Gray
    Write-Host ""
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Step 1: Secrets
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 1 of 5: GCP Secret Manager Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "You will be prompted for Twilio and SendGrid credentials." -ForegroundColor Yellow
Write-Host ""
$continue = Read-Host "Continue? (Y/n)"
if ($continue -eq "n" -or $continue -eq "N") {
    Write-Host "Setup cancelled" -ForegroundColor Red
    exit 1
}

& "$ScriptDir\setup-notifications-step1-secrets.ps1" -ProjectId $ProjectId
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ Step 1 failed. Please fix errors and re-run." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Press Enter to continue to Step 2..." -ForegroundColor Gray
Read-Host

# Step 2: Pub/Sub
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 2 of 5: Pub/Sub Topics & Subscriptions" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

& "$ScriptDir\setup-notifications-step2-pubsub.ps1" -ProjectId $ProjectId
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ Step 2 failed. Please fix errors and re-run." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Press Enter to continue to Step 3..." -ForegroundColor Gray
Read-Host

# Step 3: IAM
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 3 of 5: Service Account & IAM Permissions" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

& "$ScriptDir\setup-notifications-step3-iam.ps1" -ProjectId $ProjectId
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ Step 3 failed. Please fix errors and re-run." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Press Enter to continue to Step 4..." -ForegroundColor Gray
Read-Host

# Step 4: Deploy
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 4 of 5: Deploy to Cloud Run" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠ This step may take 5-10 minutes" -ForegroundColor Yellow
Write-Host ""

& "$ScriptDir\setup-notifications-step4-deploy.ps1" -ProjectId $ProjectId
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ Step 4 failed. Please fix errors and re-run." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Press Enter to continue to Step 5 (Testing)..." -ForegroundColor Gray
Read-Host

# Step 5: Test
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 5 of 5: End-to-End Testing" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

& "$ScriptDir\setup-notifications-step5-test.ps1" -ProjectId $ProjectId

# Final Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🎉 SETUP COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "What was configured:" -ForegroundColor Yellow
Write-Host "  ✓ GCP Secret Manager (5 secrets)" -ForegroundColor Green
Write-Host "  ✓ Pub/Sub (2 topics, 2 subscriptions)" -ForegroundColor Green
Write-Host "  ✓ Service Account with IAM permissions" -ForegroundColor Green
Write-Host "  ✓ Notification Service deployed to Cloud Run" -ForegroundColor Green
Write-Host "  ✓ End-to-end test executed" -ForegroundColor Green
Write-Host ""
Write-Host "⚠ ACTION REQUIRED: Configure Twilio Webhook" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming" -ForegroundColor White
Write-Host "2. Select your SMS-enabled phone number" -ForegroundColor White
Write-Host "3. Under 'Messaging Configuration' → 'A MESSAGE COMES IN':" -ForegroundColor White
Write-Host "   - Webhook URL: (check output above from Step 4)" -ForegroundColor Gray
Write-Host "   - HTTP Method: POST" -ForegroundColor Gray
Write-Host "4. Click Save" -ForegroundColor White
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "  - Complete guide: SETUP-NOTIFICATIONS-GUIDE.md" -ForegroundColor White
Write-Host "  - Service setup: services/notification-svc/SETUP.md" -ForegroundColor White
Write-Host "  - Testing guide: services/notification-svc/TESTING.md" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Configure Twilio webhook (see above)" -ForegroundColor White
Write-Host "  2. Upload SendGrid templates:" -ForegroundColor White
Write-Host "     cd services/notification-svc" -ForegroundColor Gray
Write-Host "     python notifications/upload_sendgrid_templates.py" -ForegroundColor Gray
Write-Host "  3. Set up monitoring alerts" -ForegroundColor White
Write-Host "  4. Integrate with backend API" -ForegroundColor White
Write-Host ""
