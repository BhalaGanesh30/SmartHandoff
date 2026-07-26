# Notification Service Setup Scripts

Automated PowerShell scripts for setting up the SmartHandoff notification service infrastructure on Google Cloud Platform.

## Prerequisites

Before running these scripts:

1. **Twilio Account**
   - Sign up: https://www.twilio.com/try-twilio
   - Purchase SMS-enabled phone number
   - Create Verify service for OTP
   - Have ready: Account SID, Auth Token, Verify SID, Phone Number

2. **SendGrid Account**
   - Sign up: https://signup.sendgrid.com/
   - Create API key with Mail Send permissions
   - Verify sender email domain

3. **GCP Setup**
   - Project created with billing enabled
   - gcloud CLI installed and authenticated
   ```powershell
   gcloud auth login
   gcloud config set project smarthandoff
   ```

## Quick Start (Recommended)

Run the complete setup wizard:

```powershell
cd scripts
.\setup-notifications-complete.ps1
```

This will guide you through all 5 steps automatically.

## Individual Scripts (Manual Step-by-Step)

If you prefer to run each step manually:

### Step 1: Create GCP Secrets
```powershell
.\setup-notifications-step1-secrets.ps1 -ProjectId smarthandoff
```
- Prompts for Twilio and SendGrid credentials
- Creates 5 secrets in GCP Secret Manager
- Verifies secret creation

### Step 2: Set Up Pub/Sub
```powershell
.\setup-notifications-step2-pubsub.ps1 -ProjectId smarthandoff
```
- Creates `notification-requests` and `care-team-alerts` topics
- Creates subscriptions for both topics
- Configures message retention and ack deadlines

### Step 3: Configure IAM
```powershell
.\setup-notifications-step3-iam.ps1 -ProjectId smarthandoff
```
- Creates `notification-service` service account
- Grants Secret Manager access (5 secrets)
- Grants Pub/Sub subscriber and publisher roles
- Grants Cloud SQL client role

### Step 4: Deploy to Cloud Run
```powershell
.\setup-notifications-step4-deploy.ps1 -ProjectId smarthandoff -SendGridFromEmail "noreply@yourdomain.com"
```
- Builds Docker image from source
- Deploys notification service to Cloud Run
- Configures environment variables
- Connects to Cloud SQL
- Returns service URL for webhook configuration

### Step 5: Test End-to-End
```powershell
.\setup-notifications-step5-test.ps1 -ProjectId smarthandoff -TestPhoneNumber "+15551234567"
```
- Runs health check
- Publishes test SMS notification to Pub/Sub
- Checks service logs
- Verifies database record (optional)
- Displays troubleshooting tips

## Script Parameters

All scripts support these parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-ProjectId` | `smarthandoff` | GCP project ID |
| `-Region` | `us-central1` | GCP region for Cloud Run |
| `-SendGridFromEmail` | `noreply@smarthandoff.health` | Verified sender email |
| `-TestPhoneNumber` | (prompted) | Phone number for SMS test |

## What Gets Created

### GCP Secret Manager (5 secrets)
- `twilio-account-sid`
- `twilio-auth-token`
- `twilio-verify-service-sid`
- `twilio-phone-number`
- `sendgrid-api-key`

### Pub/Sub (2 topics, 2 subscriptions)
- Topic: `notification-requests` → Subscription: `notification-service-sub`
- Topic: `care-team-alerts` → Subscription: `care-team-alerts-sub`

### IAM (1 service account)
- Service Account: `notification-service@PROJECT_ID.iam.gserviceaccount.com`
- Roles:
  - `roles/secretmanager.secretAccessor` (5 secrets)
  - `roles/pubsub.subscriber` (notification-service-sub)
  - `roles/pubsub.publisher` (care-team-alerts)
  - `roles/cloudsql.client`

### Cloud Run (1 service)
- Service: `notification-service`
- Region: `us-central1`
- Min instances: 1
- Max instances: 10
- Memory: 512Mi
- CPU: 1
- Timeout: 300s

## Post-Setup Tasks

### 1. Configure Twilio Webhook (REQUIRED)

After deployment, you'll receive a service URL. Configure it in Twilio:

1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming
2. Select your SMS phone number
3. Under "Messaging Configuration" → "A MESSAGE COMES IN":
   - Webhook: `https://YOUR-SERVICE-URL/webhooks/twilio/status`
   - HTTP Method: `POST`
4. Save

### 2. Upload SendGrid Templates (Optional)

```powershell
cd ..\services\notification-svc
python notifications/upload_sendgrid_templates.py
```

This uploads HTML email templates to SendGrid and updates `config/sendgrid_templates.yaml`.

### 3. Set Up Monitoring (Recommended)

```powershell
# Create Cloud Monitoring dashboard
gcloud monitoring dashboards create --config-from-file=infra/monitoring/notification-dashboard.yaml

# Set up alerts
gcloud alpha monitoring policies create --notification-channels=CHANNEL_ID --config-from-file=infra/monitoring/alerts.yaml
```

## Troubleshooting

### Deployment Fails

**View build logs:**
```powershell
gcloud builds list --project=smarthandoff --limit=5
gcloud builds log BUILD_ID
```

**Common issues:**
- Missing Dockerfile → Check `services/notification-svc/Dockerfile` exists
- Build timeout → Increase timeout with `--timeout=20m` flag
- Out of memory → Check dependencies in `requirements.txt`

### SMS Not Sending

**Check Twilio account:**
- Trial account limitations (verified numbers only)
- Account balance
- Phone number capabilities (SMS enabled?)

**Check service logs:**
```powershell
gcloud run services logs read notification-service --project=smarthandoff --limit=100
```

**Check Pub/Sub:**
```powershell
# Check for undelivered messages
gcloud pubsub subscriptions describe notification-service-sub --format="value(ackDeadlineSeconds,messageRetentionDuration)"

# Pull messages manually
gcloud pubsub subscriptions pull notification-service-sub --limit=10
```

### Webhook Signature Validation Fails

**Verify:**
- Twilio webhook URL exactly matches deployed service URL
- Auth token in Secret Manager is correct (no spaces/newlines)
- Service is receiving POST requests (check logs)

**Test webhook locally:**
```powershell
# Should return 403 (signature validation working)
curl -X POST "https://YOUR-SERVICE-URL/webhooks/twilio/status" `
  -d "MessageSid=SM123&MessageStatus=delivered" `
  -H "Content-Type: application/x-www-form-urlencoded"
```

### Can't Connect to Cloud SQL

**Check:**
```powershell
# Verify Cloud SQL instance is running
gcloud sql instances describe smarthandoff --project=smarthandoff

# Verify service account has cloudsql.client role
gcloud projects get-iam-policy smarthandoff --flatten="bindings[].members" --filter="bindings.members:notification-service@*"
```

**Start Cloud SQL Proxy locally:**
```powershell
& "$env:USERPROFILE\cloud-sql-proxy.exe" smarthandoff:us-central1:smarthandoff --port 5433
```

## Cost Breakdown

**Monthly estimates for low-traffic production:**

| Service | Usage | Cost |
|---------|-------|------|
| Cloud Run | ~1M requests, 1 min instance | $5-10 |
| Pub/Sub | ~10K messages/day | $0.50 |
| Secret Manager | 5 secrets, 100K accesses | $0.30 |
| Twilio SMS | 1,000 messages | $7.90 |
| SendGrid | 100 emails/day (free tier) | $0 |
| **Total** | | **~$14-19/month** |

**Free tier coverage:**
- Twilio: $15.50 trial credit
- SendGrid: 100 emails/day forever free
- GCP: $300 credit (90 days)

## Rollback

To remove all resources:

```powershell
# Delete Cloud Run service
gcloud run services delete notification-service --region=us-central1 --project=smarthandoff

# Delete Pub/Sub subscriptions
gcloud pubsub subscriptions delete notification-service-sub --project=smarthandoff
gcloud pubsub subscriptions delete care-team-alerts-sub --project=smarthandoff

# Delete Pub/Sub topics
gcloud pubsub topics delete notification-requests --project=smarthandoff
gcloud pubsub topics delete care-team-alerts --project=smarthandoff

# Delete secrets
gcloud secrets delete twilio-account-sid --project=smarthandoff
gcloud secrets delete twilio-auth-token --project=smarthandoff
gcloud secrets delete twilio-verify-service-sid --project=smarthandoff
gcloud secrets delete twilio-phone-number --project=smarthandoff
gcloud secrets delete sendgrid-api-key --project=smarthandoff

# Delete service account
gcloud iam service-accounts delete notification-service@smarthandoff.iam.gserviceaccount.com --project=smarthandoff
```

## Documentation

- **Complete Guide**: [../SETUP-NOTIFICATIONS-GUIDE.md](../SETUP-NOTIFICATIONS-GUIDE.md)
- **Service Documentation**: [../services/notification-svc/SETUP.md](../services/notification-svc/SETUP.md)
- **Testing Guide**: [../services/notification-svc/TESTING.md](../services/notification-svc/TESTING.md)
- **US-064 Requirements**: [../.propel/context/tasks/EP-013/US-064/US-064.md](../.propel/context/tasks/EP-013/US-064/US-064.md)

## Support

- **Twilio Docs**: https://www.twilio.com/docs/sms
- **SendGrid Docs**: https://docs.sendgrid.com/
- **GCP Cloud Run**: https://cloud.google.com/run/docs
- **Project Issues**: https://github.com/yourorg/smarthandoff/issues

---

**Version**: 1.0  
**Last Updated**: 2026-07-26  
**Maintained By**: SmartHandoff DevOps Team
