# Step 5: Test Notification Service End-to-End

param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "smarthandoff",
    
    [Parameter(Mandatory=$false)]
    [string]$TestPhoneNumber = ""
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SmartHandoff - Test Notification Service" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get service URL
$urlFile = "$env:TEMP\notification-service-url.txt"
if (Test-Path $urlFile) {
    $SERVICE_URL = Get-Content $urlFile -Raw
    $SERVICE_URL = $SERVICE_URL.Trim()
} else {
    $SERVICE_URL = gcloud run services describe notification-service `
        --project=$ProjectId `
        --region=us-central1 `
        --format='value(status.url)'
}

Write-Host "Service URL: $SERVICE_URL" -ForegroundColor Cyan
Write-Host ""

# Get test phone number
if (-not $TestPhoneNumber) {
    Write-Host "⚠ IMPORTANT: SMS will be sent to a real phone number!" -ForegroundColor Yellow
    Write-Host ""
    $TestPhoneNumber = Read-Host "Enter your phone number for testing (format: +15551234567)"
    
    if (-not $TestPhoneNumber) {
        Write-Host "✗ Phone number required for SMS test" -ForegroundColor Red
        exit 1
    }
}

# Confirm before sending
Write-Host ""
Write-Host "Ready to test:" -ForegroundColor Yellow
Write-Host "  ✓ Send SMS to: $TestPhoneNumber" -ForegroundColor White
Write-Host "  ✓ Publish message to Pub/Sub" -ForegroundColor White
Write-Host "  ✓ Check service logs" -ForegroundColor White
Write-Host "  ✓ Verify database record" -ForegroundColor White
Write-Host ""
$confirm = Read-Host "Continue with test? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Test cancelled" -ForegroundColor Yellow
    exit 0
}

# Test 1: Health check
Write-Host ""
Write-Host "[Test 1/5] Health Check..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$SERVICE_URL/health" -Method Get
    if ($response.status -eq "healthy") {
        Write-Host "✓ Health check passed" -ForegroundColor Green
    } else {
        Write-Host "⚠ Health check returned: $($response.status)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "✗ Health check failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Metrics endpoint
Write-Host ""
Write-Host "[Test 2/5] Metrics Endpoint..." -ForegroundColor Yellow
try {
    $metrics = Invoke-WebRequest -Uri "$SERVICE_URL/metrics" -Method Get
    if ($metrics.StatusCode -eq 200) {
        Write-Host "✓ Metrics endpoint accessible" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠ Metrics endpoint failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Test 3: Publish SMS notification
Write-Host ""
Write-Host "[Test 3/5] Publishing SMS Notification to Pub/Sub..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$testKey = "TEST-SMS-$timestamp"

$message = @{
    idempotency_key = $testKey
    type = "SMS"
    phone = $TestPhoneNumber
    template = "test_message"
    substitutions = @{
        name = "Test User"
        message = "This is a test SMS from SmartHandoff notification service."
    }
    urgency_override = $false
} | ConvertTo-Json -Compress

Write-Host "Publishing message with key: $testKey" -ForegroundColor Gray
gcloud pubsub topics publish notification-requests `
  --project=$ProjectId `
  --message=$message

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Message published to Pub/Sub" -ForegroundColor Green
    Write-Host "  Idempotency Key: $testKey" -ForegroundColor Gray
} else {
    Write-Host "✗ Failed to publish message" -ForegroundColor Red
}

# Wait for processing
Write-Host ""
Write-Host "Waiting 10 seconds for message processing..." -ForegroundColor Gray
Start-Sleep -Seconds 10

# Test 4: Check service logs
Write-Host ""
Write-Host "[Test 4/5] Checking Service Logs..." -ForegroundColor Yellow
Write-Host "Last 20 log entries:" -ForegroundColor Gray
Write-Host ""

gcloud run services logs read notification-service `
  --project=$ProjectId `
  --region=us-central1 `
  --limit=20 `
  --format="table(timestamp,severity,textPayload.substr(0,100))"

# Test 5: Verify database record (optional - requires Cloud SQL Proxy)
Write-Host ""
Write-Host "[Test 5/5] Verifying Database Record..." -ForegroundColor Yellow
Write-Host "⚠ This requires Cloud SQL Proxy running on port 5433" -ForegroundColor Yellow
Write-Host ""
$verifyDb = Read-Host "Verify database record? (y/N)"

if ($verifyDb -eq "y" -or $verifyDb -eq "Y") {
    $query = "SELECT id, idempotency_key, delivery_status, twilio_message_sid, created_at FROM notification WHERE idempotency_key = '$testKey';"
    
    try {
        $env:PGPASSWORD = "SmartHandoff@123"
        $result = psql -h localhost -p 5433 -U postgres -d smarthandoff -c $query -t
        
        if ($result) {
            Write-Host "✓ Database record found:" -ForegroundColor Green
            Write-Host $result -ForegroundColor Gray
        } else {
            Write-Host "⚠ No database record found (message may still be processing)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠ Could not connect to database: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "Make sure Cloud SQL Proxy is running:" -ForegroundColor Gray
        Write-Host "  & `"`$env:USERPROFILE\cloud-sql-proxy.exe`" smarthandoff:us-central1:smarthandoff --port 5433" -ForegroundColor Gray
    }
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "✓ Tests completed" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Check if you received the SMS on $TestPhoneNumber" -ForegroundColor White
Write-Host "  2. Review service logs above for any errors" -ForegroundColor White
Write-Host "  3. Configure Twilio webhook in console:" -ForegroundColor White
Write-Host "     https://console.twilio.com/us1/develop/phone-numbers/manage/incoming" -ForegroundColor Gray
Write-Host ""
Write-Host "Webhook URL to configure in Twilio:" -ForegroundColor Cyan
Write-Host "  $SERVICE_URL/webhooks/twilio/status" -ForegroundColor Yellow
Write-Host ""
Write-Host "Troubleshooting:" -ForegroundColor Cyan
Write-Host "  - If no SMS received, check Twilio account balance/trial status" -ForegroundColor White
Write-Host "  - View full logs: gcloud run services logs read notification-service --limit=100" -ForegroundColor White
Write-Host "  - Check Pub/Sub subscription: gcloud pubsub subscriptions describe notification-service-sub" -ForegroundColor White
Write-Host ""
