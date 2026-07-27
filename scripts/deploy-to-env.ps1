# Universal deployment script for all environments
# Usage: .\deploy-to-env.ps1 -Environment dev -Service backend

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("backend", "frontend", "notification-svc", "all")]
    [string]$Service
)

# Load environment configuration
$configPath = Join-Path $PSScriptRoot "..\config\environments.yaml"
$config = Get-Content $configPath -Raw | ConvertFrom-Yaml

$envConfig = $config.environments.$Environment

if (-not $envConfig) {
    Write-Host "Error: Environment '$Environment' not found in configuration" -ForegroundColor Red
    exit 1
}

$projectId = $envConfig.gcp_project
$region = $envConfig.region

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Deploying to: $($Environment.ToUpper())" -ForegroundColor Cyan
Write-Host "Service: $Service" -ForegroundColor Cyan
Write-Host "Project: $projectId" -ForegroundColor Cyan
Write-Host "Region: $region" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Set active project
Write-Host "Setting active GCP project..." -ForegroundColor Yellow
gcloud config set project $projectId

function Deploy-Backend {
    $backendConfig = $envConfig.backend
    $dbInstance = "$($projectId):$($region):$($envConfig.database.instance_name)"
    $dbName = $envConfig.database.database_name
    
    Write-Host "`nDeploying Backend API..." -ForegroundColor Green
    
    Set-Location "$env:USERPROFILE\source\repos\SmartHandoff\backend"
    
    gcloud run deploy $backendConfig.service_name `
        --source . `
        --project=$projectId `
        --region=$region `
        --platform=managed `
        --allow-unauthenticated `
        --min-instances=$backendConfig.min_instances `
        --max-instances=$backendConfig.max_instances `
        --memory=$backendConfig.memory `
        --cpu=$backendConfig.cpu `
        --concurrency=$backendConfig.concurrency `
        --timeout=300 `
        --port=8080 `
        --add-cloudsql-instances=$dbInstance `
        --set-env-vars="DATABASE_URL=postgresql+asyncpg://postgres:SmartHandoff%40123@/$dbName?host=/cloudsql/$dbInstance,ENVIRONMENT=$Environment" `
        --update-secrets="JWT_SECRET_KEY=$($envConfig.secrets.jwt_secret):latest"
}

function Deploy-Frontend {
    $frontendConfig = $envConfig.frontend
    $backendUrl = "https://$($envConfig.backend.service_name)-XXXXX-uc.a.run.app"
    
    Write-Host "`nDeploying Frontend..." -ForegroundColor Green
    
    Set-Location "$env:USERPROFILE\source\repos\SmartHandoff\frontend"
    
    gcloud run deploy $frontendConfig.service_name `
        --source . `
        --project=$projectId `
        --region=$region `
        --platform=managed `
        --allow-unauthenticated `
        --min-instances=$frontendConfig.min_instances `
        --max-instances=$frontendConfig.max_instances `
        --memory=$frontendConfig.memory `
        --cpu=$frontendConfig.cpu `
        --timeout=60 `
        --port=8080 `
        --set-env-vars="API_BASE_URL=$backendUrl,ENVIRONMENT=$Environment"
}

function Deploy-NotificationService {
    $notifConfig = $envConfig.notification_svc
    $dbInstance = "$($projectId):$($region):$($envConfig.database.instance_name)"
    $dbName = $envConfig.database.database_name
    
    Write-Host "`nDeploying Notification Service..." -ForegroundColor Green
    
    Set-Location "$env:USERPROFILE\source\repos\SmartHandoff\services\notification-svc"
    
    gcloud run deploy $notifConfig.service_name `
        --source . `
        --project=$projectId `
        --region=$region `
        --platform=managed `
        --allow-unauthenticated `
        --min-instances=$notifConfig.min_instances `
        --max-instances=$notifConfig.max_instances `
        --memory=$notifConfig.memory `
        --cpu=$notifConfig.cpu `
        --timeout=300 `
        --port=8080 `
        --add-cloudsql-instances=$dbInstance `
        --set-env-vars="DATABASE_URL=postgresql+asyncpg://postgres:SmartHandoff%40123@/$dbName?host=/cloudsql/$dbInstance,GCP_PROJECT_ID=$projectId,PUBSUB_SUBSCRIPTION_ID=notification-service-sub,ENVIRONMENT=$Environment" `
        --update-secrets="TWILIO_ACCOUNT_SID=$($envConfig.secrets.twilio_account_sid):latest,TWILIO_AUTH_TOKEN=$($envConfig.secrets.twilio_auth_token):latest,SENDGRID_API_KEY=$($envConfig.secrets.sendgrid_api_key):latest"
}

# Deploy based on service parameter
switch ($Service) {
    "backend" {
        Deploy-Backend
    }
    "frontend" {
        Deploy-Frontend
    }
    "notification-svc" {
        Deploy-NotificationService
    }
    "all" {
        Deploy-Backend
        Deploy-Frontend
        Deploy-NotificationService
    }
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "View services:" -ForegroundColor Yellow
Write-Host "  gcloud run services list --project=$projectId --region=$region"
Write-Host ""
