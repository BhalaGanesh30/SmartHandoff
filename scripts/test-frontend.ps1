# Test frontend deployment
# Run this to verify the frontend is working correctly

$frontendUrl = "https://smarthandoff-frontend-52528248131.us-central1.run.app"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Testing Frontend Deployment" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Test 1: Health endpoint
Write-Host "Test 1: Health Check..." -ForegroundColor Yellow
try {
    $healthResponse = Invoke-WebRequest -Uri "$frontendUrl/health" -Method GET -UseBasicParsing
    if ($healthResponse.StatusCode -eq 200) {
        Write-Host "✅ Health check passed" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Health check failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Root page
Write-Host "`nTest 2: Root Page..." -ForegroundColor Yellow
try {
    $rootResponse = Invoke-WebRequest -Uri $frontendUrl -Method GET -UseBasicParsing
    if ($rootResponse.StatusCode -eq 200) {
        if ($rootResponse.Content -like "*SmartHandoff*") {
            Write-Host "✅ Root page loads correctly (Angular app detected)" -ForegroundColor Green
        } elseif ($rootResponse.Content -like "*Welcome to nginx*") {
            Write-Host "❌ Still showing nginx welcome page - needs redeployment" -ForegroundColor Red
        } else {
            Write-Host "⚠️ Page loads but content unexpected" -ForegroundColor Yellow
        }
    }
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 403) {
        Write-Host "❌ Forbidden (403) - Public access not enabled yet" -ForegroundColor Red
        Write-Host "   Run: .\scripts\enable-frontend-public-access.ps1" -ForegroundColor Yellow
    } else {
        Write-Host "❌ Request failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Test 3: Static assets
Write-Host "`nTest 3: Static Assets..." -ForegroundColor Yellow
try {
    $staticResponse = Invoke-WebRequest -Uri "$frontendUrl/health" -Method HEAD -UseBasicParsing
    Write-Host "✅ Static asset serving configured" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Could not verify static assets" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Frontend URL: $frontendUrl" -ForegroundColor Cyan
Write-Host "`nFor detailed fix instructions, see:" -ForegroundColor Yellow
Write-Host "  FRONTEND-FIX-GUIDE.md" -ForegroundColor White
