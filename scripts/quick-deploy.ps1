# Quick Deploy Script - Single Project with Environment Suffixes
# Usage: .\quick-deploy.ps1 -Environment dev -Service backend

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("backend", "frontend", "notification-svc", "all")]
    [string]$Service
)

$projectId = "smarthandoff"
$region = "us-central1"

# Environment-specific settings
$envSettings = @{
    dev = @{
        suffix = "-dev"
        minInstances = 0
        maxInstances = 3
        memory = "512Mi"
        cpu = 1
    }
    staging = @{
        suffix = "-staging"
        minInstances = 1
        maxInstances = 5
        memory = "1Gi"
        cpu = 2
    }
    prod = @{
        suffix = ""
        minInstances = 2
        maxInstances = 10
        memory = "2Gi"
        cpu = 2
    }
}

$config = $envSettings[$Environment]

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Quick Deploy to: $($Environment.ToUpper())" -ForegroundColor Cyan
Write-Host "Project: $projectId (shared)" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

function Deploy-Backend {
    $serviceName = "smarthandoff-backend$($config.suffix)"
    
    Write-Host "Deploying Backend: $serviceName..." -ForegroundColor Green
    
    cd "$env:USERPROFILE\source\repos\SmartHandoff\backend"
    
    gcloud run deploy $serviceName `
        --source . `
        --project=$projectId `
        --region=$region `
        --platform=managed `
        --allow-unauthenticated `
        --min-instances=$config.minInstances `
        --max-instances=$config.maxInstances `
        --memory=$config.memory `
        --cpu=$config.cpu `
        --timeout=300 `
        --port=8080 `
        --add-cloudsql-instances="smarthandoff:us-central1:smarthandoff" `
        --set-env-vars="DATABASE_URL=postgresql+asyncpg://postgres:SmartHandoff%40123@/smarthandoff?host=/cloudsql/smarthandoff:us-central1:smarthandoff,ENVIRONMENT=$Environment"
    
    if ($LASTEXITCODE -eq 0) {
        $url = gcloud run services describe $serviceName --region=$region --project=$projectId --format="value(status.url)"
        Write-Host "`nBackend URL: $url" -ForegroundColor Green
    }
}

function Deploy-Frontend {
    $serviceName = "smarthandoff-frontend$($config.suffix)"
    
    Write-Host "Deploying Frontend: $serviceName..." -ForegroundColor Green
    
    cd "$env:USERPROFILE\source\repos\SmartHandoff\frontend"
    
    gcloud run deploy $serviceName `
        --source . `
        --project=$projectId `
        --region=$region `
        --platform=managed `
        --allow-unauthenticated `
        --min-instances=$config.minInstances `
        --max-instances=($config.maxInstances / 2) `
        --memory="512Mi" `
        --cpu=1 `
        --timeout=60 `
        --port=8080 `
        --set-env-vars="ENVIRONMENT=$Environment"
    
    if ($LASTEXITCODE -eq 0) {
        $url = gcloud run services describe $serviceName --region=$region --project=$projectId --format="value(status.url)"
        Write-Host "`nFrontend URL: $url" -ForegroundColor Green
    }
}

function Deploy-NotificationService {
    $serviceName = "notification-service$($config.suffix)"
    
    Write-Host "Deploying Notification Service: $serviceName..." -ForegroundColor Green
    
    cd "$env:USERPROFILE\source\repos\SmartHandoff\services\notification-svc"
    
    gcloud run deploy $serviceName `
        --source . `
        --project=$projectId `
        --region=$region `
        --platform=managed `
        --allow-unauthenticated `
        --min-instances=$config.minInstances `
        --max-instances=$config.maxInstances `
        --memory="512Mi" `
        --cpu=1 `
        --timeout=300 `
        --port=8080 `
        --add-cloudsql-instances="smarthandoff:us-central1:smarthandoff" `
        --set-env-vars="DATABASE_URL=postgresql+asyncpg://postgres:SmartHandoff%40123@/smarthandoff?host=/cloudsql/smarthandoff:us-central1:smarthandoff,GCP_PROJECT_ID=$projectId,PUBSUB_SUBSCRIPTION_ID=notification-service-sub,SENDGRID_FROM_EMAIL=balaganesh272@gmail.com,TWILIO_FROM_NUMBER=+13507772699,ENVIRONMENT=$Environment"
    
    if ($LASTEXITCODE -eq 0) {
        $url = gcloud run services describe $serviceName --region=$region --project=$projectId --format="value(status.url)"
        Write-Host "`nNotification Service URL: $url" -ForegroundColor Green
    }
}

# Deploy based on service parameter
switch ($Service) {
    "backend" { Deploy-Backend }
    "frontend" { Deploy-Frontend }
    "notification-svc" { Deploy-NotificationService }
    "all" {
        Deploy-Backend
        Start-Sleep -Seconds 5
        Deploy-Frontend
        Start-Sleep -Seconds 5
        Deploy-NotificationService
    }
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "View all services:" -ForegroundColor Yellow
Write-Host "  gcloud run services list --project=$projectId --region=$region"
Write-Host ""
