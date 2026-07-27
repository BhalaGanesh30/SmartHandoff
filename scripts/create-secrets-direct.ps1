# Creates notification-service secrets in Google Secret Manager.
#
# Set these environment variables before running this script. Do not place
# credential values in this file or commit them to source control:
#   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_VERIFY_SERVICE_SID,
#   TWILIO_PHONE_NUMBER, SENDGRID_API_KEY

param(
    [string]$ProjectId = "smarthandoff"
)

$ErrorActionPreference = "Stop"

$secrets = @{
    "twilio-account-sid"          = $env:TWILIO_ACCOUNT_SID
    "twilio-auth-token"           = $env:TWILIO_AUTH_TOKEN
    "twilio-verify-service-sid"   = $env:TWILIO_VERIFY_SERVICE_SID
    "twilio-phone-number"         = $env:TWILIO_PHONE_NUMBER
    "sendgrid-api-key"            = $env:SENDGRID_API_KEY
}

$missing = $secrets.GetEnumerator() | Where-Object { [string]::IsNullOrWhiteSpace($_.Value) } | ForEach-Object Key
if ($missing) {
    throw "Set the required environment variables before running this script: $($missing -join ', ')"
}

gcloud config set project $ProjectId
gcloud services enable secretmanager.googleapis.com --project=$ProjectId

foreach ($secret in $secrets.GetEnumerator()) {
    $name = $secret.Key
    $value = $secret.Value

    # Adding a version works for both new and existing secrets once the
    # secret resource exists.
    gcloud secrets describe $name --project=$ProjectId 2>$null
    if ($LASTEXITCODE -ne 0) {
        gcloud secrets create $name --project=$ProjectId --replication-policy=automatic
    }

    $value | gcloud secrets versions add $name --project=$ProjectId --data-file=-
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to store the $name secret."
    }
    Write-Host "Stored $name" -ForegroundColor Green
}

Write-Host "Notification secrets are configured for $ProjectId." -ForegroundColor Green
