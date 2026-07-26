# Configure SmartHandoff Backend with FHIR Server Connection
# Updates Cloud Run environment variables

param(
    [string]$FhirBaseUrl = "http://localhost:8090/fhir",
    [switch]$UsePublicHapi = $false
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Configure Backend FHIR Connection" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

if ($UsePublicHapi) {
    $FhirBaseUrl = "https://hapi.fhir.org/baseR4"
    Write-Host "Using public HAPI FHIR test server" -ForegroundColor Yellow
} else {
    Write-Host "Using local HAPI FHIR server" -ForegroundColor Yellow
}

Write-Host "FHIR Base URL: $FhirBaseUrl`n" -ForegroundColor Cyan

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "IMPORTANT: Local FHIR Server Limitation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Cloud Run cannot access localhost directly!" -ForegroundColor Red
Write-Host "`nOptions:" -ForegroundColor Yellow
Write-Host "1. Use public HAPI FHIR server (add -UsePublicHapi flag)" -ForegroundColor White
Write-Host "2. Deploy HAPI FHIR to Cloud Run (recommended for production)" -ForegroundColor White
Write-Host "3. Expose local FHIR server via ngrok/cloudflare tunnel" -ForegroundColor White
Write-Host "4. Test backend locally with FHIR_BASE_URL=$FhirBaseUrl" -ForegroundColor White
Write-Host "`n========================================`n" -ForegroundColor Cyan

$response = Read-Host "Continue with configuration? (y/N)"
if ($response -ne 'y' -and $response -ne 'Y') {
    Write-Host "Configuration cancelled." -ForegroundColor Yellow
    exit 0
}

# For local testing, update backend/.env
$backendDir = "$env:USERPROFILE\source\repos\SmartHandoff\backend"
$envFile = "$backendDir\.env"

Write-Host "`nUpdating local backend configuration..." -ForegroundColor Yellow

$envContent = @"
# FHIR Server Configuration
FHIR_BASE_URL=$FhirBaseUrl
FHIR_CLIENT_ID=public-client
FHIR_CLIENT_SECRET=not-required-for-public-servers
FHIR_SCOPE=system/*.read

# Note: For local development only
# HAPI FHIR public server does not require authentication
"@

Set-Content -Path $envFile -Value $envContent -Force
Write-Host "✓ Created $envFile" -ForegroundColor Green

# Update Cloud Run (if using public HAPI FHIR)
if ($UsePublicHapi) {
    Write-Host "`nUpdating Cloud Run service with public FHIR server..." -ForegroundColor Yellow
    
    gcloud run services update smarthandoff-backend `
        --update-env-vars="FHIR_BASE_URL=$FhirBaseUrl,FHIR_CLIENT_ID=public-client,FHIR_CLIENT_SECRET=not-required" `
        --project=smarthandoff `
        --region=us-central1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Cloud Run service updated successfully" -ForegroundColor Green
        Write-Host "`nBackend will now fetch patient data from public HAPI FHIR server" -ForegroundColor Cyan
    } else {
        Write-Host "ERROR: Failed to update Cloud Run service" -ForegroundColor Red
    }
} else {
    Write-Host "`nℹ Local FHIR server configured for development only" -ForegroundColor Yellow
    Write-Host "To use with Cloud Run, deploy HAPI FHIR to Cloud Run first" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Configuration Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FHIR Base URL: $FhirBaseUrl" -ForegroundColor White
Write-Host "Local .env:    $envFile" -ForegroundColor White

if ($UsePublicHapi) {
    Write-Host "Cloud Run:     Updated ✓" -ForegroundColor Green
    Write-Host "`nBackend URL:   https://smarthandoff-backend-h67r7fyswq-uc.a.run.app" -ForegroundColor Cyan
    Write-Host "Test endpoint: /api/v1/patients" -ForegroundColor Cyan
} else {
    Write-Host "Cloud Run:     Not updated (local FHIR only)" -ForegroundColor Yellow
    Write-Host "`nTo deploy HAPI FHIR to Cloud Run:" -ForegroundColor Yellow
    Write-Host "  .\\scripts\\deploy-hapi-fhir.ps1" -ForegroundColor Cyan
}

Write-Host "========================================`n" -ForegroundColor Cyan
