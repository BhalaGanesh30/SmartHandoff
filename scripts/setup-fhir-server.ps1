# Setup HAPI FHIR Server with Docker
# This script runs a local HAPI FHIR R4 server for testing

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "HAPI FHIR Server Setup" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if Docker is running
Write-Host "Checking Docker status..." -ForegroundColor Yellow
$dockerRunning = docker info 2>&1 | Select-String "Server Version"
if (-not $dockerRunning) {
    Write-Host "ERROR: Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ Docker is running" -ForegroundColor Green

# Check if HAPI FHIR container already exists
Write-Host "`nChecking for existing HAPI FHIR container..." -ForegroundColor Yellow
$existingContainer = docker ps -a --filter "name=hapi-fhir" --format "{{.Names}}"
if ($existingContainer) {
    Write-Host "Found existing container: $existingContainer" -ForegroundColor Yellow
    $response = Read-Host "Remove and recreate? (y/N)"
    if ($response -eq 'y' -or $response -eq 'Y') {
        Write-Host "Stopping and removing existing container..." -ForegroundColor Yellow
        docker stop hapi-fhir 2>$null
        docker rm hapi-fhir 2>$null
        Write-Host "✓ Removed existing container" -ForegroundColor Green
    } else {
        Write-Host "Using existing container..." -ForegroundColor Yellow
        docker start hapi-fhir
        Write-Host "`n✓ HAPI FHIR Server started" -ForegroundColor Green
        Write-Host "`nServer URL: http://localhost:8090/fhir" -ForegroundColor Cyan
        Write-Host "Web UI: http://localhost:8090" -ForegroundColor Cyan
        exit 0
    }
}

# Pull HAPI FHIR image
Write-Host "`nPulling HAPI FHIR Docker image..." -ForegroundColor Yellow
docker pull hapiproject/hapi:latest

# Run HAPI FHIR container
Write-Host "`nStarting HAPI FHIR server on port 8090..." -ForegroundColor Yellow
docker run -d `
    --name hapi-fhir `
    -p 8090:8080 `
    -e hapi.fhir.fhir_version=R4 `
    -e hapi.fhir.subscription.resthook_enabled=true `
    -e hapi.fhir.allow_external_references=true `
    -e hapi.fhir.allow_multiple_delete=true `
    -e hapi.fhir.allow_placeholder_references=true `
    -e spring.jpa.properties.hibernate.search.enabled=false `
    hapiproject/hapi:latest

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ HAPI FHIR container started successfully" -ForegroundColor Green
    
    Write-Host "`nWaiting for HAPI FHIR to be ready..." -ForegroundColor Yellow
    $maxAttempts = 30
    $attempt = 0
    $ready = $false
    
    while ($attempt -lt $maxAttempts -and -not $ready) {
        $attempt++
        Start-Sleep -Seconds 2
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8090/fhir/metadata" -Method GET -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $ready = $true
            }
        } catch {
            Write-Host "." -NoNewline
        }
    }
    
    if ($ready) {
        Write-Host "`n`n✓ HAPI FHIR Server is ready!" -ForegroundColor Green
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "HAPI FHIR Server Details" -ForegroundColor Cyan
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Base URL:  http://localhost:8090/fhir" -ForegroundColor White
        Write-Host "Web UI:    http://localhost:8090" -ForegroundColor White
        Write-Host "Metadata:  http://localhost:8090/fhir/metadata" -ForegroundColor White
        Write-Host "Container: hapi-fhir (running)" -ForegroundColor White
        Write-Host "`nTo stop: docker stop hapi-fhir" -ForegroundColor Yellow
        Write-Host "To view logs: docker logs -f hapi-fhir" -ForegroundColor Yellow
        Write-Host "========================================`n" -ForegroundColor Cyan
    } else {
        Write-Host "`n`nWARNING: Server started but not responding yet" -ForegroundColor Yellow
        Write-Host "It may take a few more minutes to initialize" -ForegroundColor Yellow
        Write-Host "Check logs with: docker logs -f hapi-fhir" -ForegroundColor Yellow
    }
} else {
    Write-Host "ERROR: Failed to start HAPI FHIR container" -ForegroundColor Red
    exit 1
}
