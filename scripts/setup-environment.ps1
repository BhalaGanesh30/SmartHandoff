# Setup a new GCP environment (dev, staging, or prod)
# Usage: .\setup-environment.ps1 -Environment dev

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment
)

# Load configuration
$configPath = Join-Path $PSScriptRoot "..\config\environments.yaml"
$config = Get-Content $configPath -Raw | ConvertFrom-Yaml
$envConfig = $config.environments.$Environment

$projectId = $envConfig.gcp_project
$region = $envConfig.region
$dbConfig = $envConfig.database

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Setting up $($Environment.ToUpper()) Environment" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Project ID: $projectId" -ForegroundColor White
Write-Host "Region: $region" -ForegroundColor White
Write-Host "Database Instance: $($dbConfig.instance_name)" -ForegroundColor White
Write-Host ""

# Step 1: Create GCP Project (if it doesn't exist)
Write-Host "Step 1: Checking GCP Project..." -ForegroundColor Green
$projectExists = gcloud projects list --filter="projectId:$projectId" --format="value(projectId)"

if (-not $projectExists) {
    Write-Host "Project doesn't exist. Creating..." -ForegroundColor Yellow
    gcloud projects create $projectId --name="SmartHandoff $($Environment.ToUpper())"
    
    Write-Host "Link billing account (required for Cloud Run):" -ForegroundColor Yellow
    Write-Host "  gcloud billing accounts list"
    Write-Host "  gcloud billing projects link $projectId --billing-account=BILLING_ACCOUNT_ID"
    Write-Host ""
    Read-Host "Press Enter after linking billing account"
} else {
    Write-Host "Project already exists: $projectId" -ForegroundColor Green
}

# Set active project
gcloud config set project $projectId

# Step 2: Enable required APIs
Write-Host "`nStep 2: Enabling required GCP APIs..." -ForegroundColor Green
$apis = @(
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
    "pubsub.googleapis.com",
    "artifactregistry.googleapis.com"
)

foreach ($api in $apis) {
    Write-Host "  Enabling $api..." -ForegroundColor Gray
    gcloud services enable $api --project=$projectId
}
Write-Host "APIs enabled successfully!" -ForegroundColor Green

# Step 3: Create Cloud SQL Instance
Write-Host "`nStep 3: Creating Cloud SQL Instance..." -ForegroundColor Green
$instanceExists = gcloud sql instances list --project=$projectId --filter="name:$($dbConfig.instance_name)" --format="value(name)"

if (-not $instanceExists) {
    Write-Host "Creating PostgreSQL instance (this takes 5-10 minutes)..." -ForegroundColor Yellow
    gcloud sql instances create $dbConfig.instance_name `
        --database-version=POSTGRES_15 `
        --tier=$dbConfig.tier `
        --region=$region `
        --root-password="SmartHandoff@123" `
        --storage-type=SSD `
        --storage-size=10GB `
        --backup `
        --project=$projectId
    
    Write-Host "Creating database: $($dbConfig.database_name)..." -ForegroundColor Yellow
    gcloud sql databases create $dbConfig.database_name `
        --instance=$dbConfig.instance_name `
        --project=$projectId
} else {
    Write-Host "Database instance already exists" -ForegroundColor Green
}

# Step 4: Create Pub/Sub Topics
Write-Host "`nStep 4: Creating Pub/Sub Topics..." -ForegroundColor Green
$topics = @("notification-requests", "care-team-alerts")
foreach ($topic in $topics) {
    $topicExists = gcloud pubsub topics list --project=$projectId --filter="name:$topic" --format="value(name)"
    if (-not $topicExists) {
        gcloud pubsub topics create $topic --project=$projectId
        Write-Host "  Created topic: $topic" -ForegroundColor Gray
    }
}

# Create subscriptions
gcloud pubsub subscriptions create notification-service-sub `
    --topic=notification-requests `
    --ack-deadline=300 `
    --project=$projectId 2>$null

Write-Host "Pub/Sub topics created!" -ForegroundColor Green

# Step 5: Create Secrets
Write-Host "`nStep 5: Setting up Secret Manager..." -ForegroundColor Green
Write-Host "Creating placeholder secrets (update these with real values later):" -ForegroundColor Yellow

$secrets = @{
    $envConfig.secrets.jwt_secret = "change-me-jwt-secret-$Environment"
    $envConfig.secrets.twilio_account_sid = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    $envConfig.secrets.twilio_auth_token = "your_twilio_token_here"
    $envConfig.secrets.sendgrid_api_key = "SG.xxxxxxxxxxxxxxxx"
}

foreach ($secretName in $secrets.Keys) {
    $secretValue = $secrets[$secretName]
    $secretExists = gcloud secrets list --project=$projectId --filter="name:$secretName" --format="value(name)"
    
    if (-not $secretExists) {
        echo $secretValue | gcloud secrets create $secretName --data-file=- --project=$projectId
        Write-Host "  Created secret: $secretName" -ForegroundColor Gray
    }
}

Write-Host "Secrets created! Remember to update with real values." -ForegroundColor Green

# Step 6: Create Service Accounts
Write-Host "`nStep 6: Creating Service Accounts..." -ForegroundColor Green

$serviceAccounts = @(
    @{name="backend-api"; display="SmartHandoff Backend API"},
    @{name="notification-service"; display="Notification Service"}
)

foreach ($sa in $serviceAccounts) {
    $saEmail = "$($sa.name)@$projectId.iam.gserviceaccount.com"
    $saExists = gcloud iam service-accounts list --project=$projectId --filter="email:$saEmail" --format="value(email)"
    
    if (-not $saExists) {
        gcloud iam service-accounts create $sa.name `
            --display-name="$($sa.display)" `
            --project=$projectId
        
        # Grant permissions
        $roles = @(
            "roles/cloudsql.client",
            "roles/secretmanager.secretAccessor",
            "roles/pubsub.publisher"
        )
        
        foreach ($role in $roles) {
            gcloud projects add-iam-policy-binding $projectId `
                --member="serviceAccount:$saEmail" `
                --role=$role
        }
        
        Write-Host "  Created service account: $($sa.name)" -ForegroundColor Gray
    }
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Environment Setup Complete!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Update secrets with real credentials:"
Write-Host "   gcloud secrets versions add $($envConfig.secrets.jwt_secret) --data-file=jwt_key.txt --project=$projectId"
Write-Host ""
Write-Host "2. Run database migrations:"
Write-Host "   cloud_sql_proxy $($projectId):$($region):$($dbConfig.instance_name) &"
Write-Host "   cd backend && alembic upgrade head"
Write-Host ""
Write-Host "3. Deploy services:"
Write-Host "   .\scripts\deploy-to-env.ps1 -Environment $Environment -Service all"
Write-Host ""
