# Notification Service Setup Guide

## Prerequisites

- Google Cloud SDK installed and configured
- Python 3.11+
- PostgreSQL database
- SendGrid account with API key
- Twilio account with Programmable SMS enabled

## 1. Environment Variables

Copy the environment template and configure:

```bash
cp .env.example .env
```

Edit `.env` and set:

```bash
# Required for TASK-004 (SendGrid Email)
SENDGRID_FROM_EMAIL=noreply@yourdomain.com

# Required for TASK-003 (Twilio SMS)
TWILIO_FROM_NUMBER=+15551234567

# GCP Configuration
GCP_PROJECT_ID=your-gcp-project-id
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/smarthandoff
```

## 2. Create GCP Secret Manager Secrets

### Prerequisites
- GCP project with Secret Manager API enabled
- Appropriate IAM permissions (`roles/secretmanager.admin` or `roles/secretmanager.secretAccessor`)

### Create Secrets

```bash
# Set your project ID
export GCP_PROJECT_ID=your-gcp-project-id

# Create Twilio secrets (TASK-003)
echo -n "YOUR_TWILIO_ACCOUNT_SID" | gcloud secrets create twilio-account-sid \
  --project=$GCP_PROJECT_ID \
  --replication-policy="automatic" \
  --data-file=-

echo -n "YOUR_TWILIO_AUTH_TOKEN" | gcloud secrets create twilio-auth-token \
  --project=$GCP_PROJECT_ID \
  --replication-policy="automatic" \
  --data-file=-

# Create SendGrid secret (TASK-004)
echo -n "YOUR_SENDGRID_API_KEY" | gcloud secrets create sendgrid-api-key \
  --project=$GCP_PROJECT_ID \
  --replication-policy="automatic" \
  --data-file=-
```

### Verify Secrets

```bash
gcloud secrets list --project=$GCP_PROJECT_ID --filter="name:twilio OR name:sendgrid"
```

### Grant Service Account Access

If running on Cloud Run, grant the service account access to secrets:

```bash
export SERVICE_ACCOUNT=notification-service@${GCP_PROJECT_ID}.iam.gserviceaccount.com

for SECRET in twilio-account-sid twilio-auth-token sendgrid-api-key; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --project=$GCP_PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done
```

## 3. Configure Twilio Webhook URL

### Get Your Service URL

After deploying to Cloud Run:

```bash
gcloud run services describe notification-service \
  --project=$GCP_PROJECT_ID \
  --region=us-central1 \
  --format='value(status.url)'
```

Example output: `https://notification-service-abc123-uc.a.run.app`

### Configure in Twilio Console

1. Log in to [Twilio Console](https://console.twilio.com/)
2. Navigate to **Phone Numbers** → **Manage** → **Active numbers**
3. Select your SMS-enabled phone number
4. Scroll to **Messaging Configuration**
5. Under **A MESSAGE COMES IN**, set:
   - **Webhook URL**: `https://notification-service-abc123-uc.a.run.app/webhooks/twilio/status`
   - **HTTP Method**: `POST`
6. Click **Save**

### Test Webhook Signature Validation

```bash
# Send a test webhook (will fail signature validation as expected)
curl -X POST https://your-service-url.run.app/webhooks/twilio/status \
  -d 'MessageSid=SM123&MessageStatus=delivered' \
  -H 'Content-Type: application/x-www-form-urlencoded'

# Expected: HTTP 403 Forbidden (Missing X-Twilio-Signature header)
```

### Validate Webhook with Twilio Signature

Use [Twilio's webhook testing tool](https://www.twilio.com/docs/usage/webhooks/webhooks-security#validating-signatures-locally) or send a real SMS to trigger a delivery callback.

## 4. Run Integration Tests with Pub/Sub Emulator

### Start Pub/Sub Emulator

```bash
# Install the emulator (if not already installed)
gcloud components install pubsub-emulator

# Start the emulator
gcloud beta emulators pubsub start --project=$GCP_PROJECT_ID
```

In a new terminal, set the emulator environment:

```bash
$(gcloud beta emulators pubsub env-init)
```

### Create Topic and Subscription

```bash
export GCP_PROJECT_ID=your-gcp-project-id

# Create topic
gcloud pubsub topics create notification-requests \
  --project=$GCP_PROJECT_ID

# Create subscription
gcloud pubsub subscriptions create notification-service-sub \
  --topic=notification-requests \
  --project=$GCP_PROJECT_ID

# Create care-team-alerts topic (for failure notifications)
gcloud pubsub topics create care-team-alerts \
  --project=$GCP_PROJECT_ID
```

### Run Integration Tests

```bash
cd services/notification-svc

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run the service with emulator
export PUBSUB_EMULATOR_HOST=localhost:8085
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

In another terminal, publish a test message:

```bash
export PUBSUB_EMULATOR_HOST=localhost:8085

# Test SMS notification
gcloud pubsub topics publish notification-requests \
  --project=$GCP_PROJECT_ID \
  --message='{
    "idempotency_key": "TEST-SMS-001",
    "type": "SMS",
    "phone": "+15555551234",
    "template": "test_message",
    "substitutions": {"name": "Test User"}
  }'

# Test EMAIL notification
gcloud pubsub topics publish notification-requests \
  --project=$GCP_PROJECT_ID \
  --message='{
    "idempotency_key": "TEST-EMAIL-001",
    "type": "EMAIL",
    "email": "test@example.com",
    "template": "d-test-template-id",
    "substitutions": {"name": "Test User"}
  }'
```

### Run Automated Integration Tests

```bash
# Run integration test suite
pytest tests/integration/ -v
```

## 5. Deploy to Cloud Run

### Build and Deploy

```bash
cd services/notification-svc

# Set variables
export GCP_PROJECT_ID=your-gcp-project-id
export REGION=us-central1
export SERVICE_NAME=notification-service

# Build container
gcloud builds submit \
  --project=$GCP_PROJECT_ID \
  --config=cloudbuild.yaml

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --project=$GCP_PROJECT_ID \
  --region=$REGION \
  --image=gcr.io/$GCP_PROJECT_ID/notification-service:latest \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,SENDGRID_FROM_EMAIL=noreply@yourdomain.com,TWILIO_FROM_NUMBER=+15551234567" \
  --set-secrets="DATABASE_URL=database-url:latest" \
  --min-instances=1 \
  --max-instances=10 \
  --memory=512Mi \
  --cpu=1
```

### Verify Deployment

```bash
# Check service status
gcloud run services describe $SERVICE_NAME \
  --project=$GCP_PROJECT_ID \
  --region=$REGION

# Test health endpoint
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --project=$GCP_PROJECT_ID \
  --region=$REGION \
  --format='value(status.url)')

curl $SERVICE_URL/health
# Expected: {"status":"ok"}

curl $SERVICE_URL/ready
# Expected: {"status":"ready"}
```

### Configure Pub/Sub Push Subscription

After deployment, update the subscription to push to Cloud Run:

```bash
gcloud pubsub subscriptions update notification-service-sub \
  --project=$GCP_PROJECT_ID \
  --push-endpoint="${SERVICE_URL}/pubsub/consume" \
  --push-auth-service-account=$SERVICE_ACCOUNT
```

## Troubleshooting

### Secret Access Denied

If you see "Permission denied" errors for secrets:

```bash
# Grant yourself access temporarily
gcloud secrets add-iam-policy-binding SECRET_NAME \
  --project=$GCP_PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Twilio Webhook Failures

Check Cloud Run logs:

```bash
gcloud run services logs read $SERVICE_NAME \
  --project=$GCP_PROJECT_ID \
  --region=$REGION \
  --limit=50
```

Look for:
- `twilio_webhook.invalid_signature` — Check Twilio auth token in Secret Manager
- `twilio_webhook.sid_not_found` — Check `twilio_message_sid` correlation

### SendGrid Failures

Check for:
- `email_dispatcher.sendgrid_error` — Verify API key and from email
- Status code 401 — Invalid API key
- Status code 403 — Sender email not verified in SendGrid

### Database Connection Issues

```bash
# Test database connectivity from Cloud Run
gcloud run services update $SERVICE_NAME \
  --project=$GCP_PROJECT_ID \
  --region=$REGION \
  --set-env-vars="DATABASE_URL=postgresql+asyncpg://..." \
  --clear-vpc-connector  # If using Cloud SQL Proxy
```

## Production Checklist

- [ ] All secrets created in Secret Manager
- [ ] Service account has `roles/secretmanager.secretAccessor`
- [ ] `SENDGRID_FROM_EMAIL` verified in SendGrid
- [ ] Twilio webhook URL configured with HTTPS
- [ ] Pub/Sub subscription created with push endpoint
- [ ] Cloud Run service deployed with correct environment variables
- [ ] Health and ready endpoints return 200 OK
- [ ] Integration tests pass against emulator
- [ ] End-to-end SMS test successful
- [ ] End-to-end email test successful
- [ ] Twilio webhook signature validation working
- [ ] Monitoring and alerting configured

## Next Steps

After successful deployment:

1. Set up monitoring dashboards for notification delivery rates
2. Configure alerting for failed dispatches (via `care-team-alerts` topic)
3. Review and tune retry backoff timings based on observed patterns
4. Implement unit tests for dispatcher logic (TASK-005)
5. Add integration tests for webhook endpoints
