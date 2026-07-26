# SmartHandoff Notifications Setup Guide

**Date:** 2026-07-26  
**Status:** In Progress  
**Prerequisites:** ✅ Database migration complete

---

## Step 1: Twilio Account Setup

### 1.1 Sign Up for Twilio

1. Go to https://www.twilio.com/try-twilio
2. Click "Sign up" and complete registration
3. Verify your email address
4. Complete phone verification

### 1.2 Get Your Credentials

After login, go to [Twilio Console Dashboard](https://console.twilio.com/):

**Location:** Console Home → Account Info (top right)

Copy these values:
```
ACCOUNT SID: [Will look like ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx]
AUTH TOKEN: [Click "Show" to reveal - save securely!]
```

### 1.3 Purchase a Phone Number

1. In Console, go to **Phone Numbers** → **Manage** → **Buy a number**
2. Select your country (US recommended)
3. Check **SMS** capability
4. Search and purchase a number
5. Copy the number (format: +15551234567)

**Cost:** ~$1.15/month for US number + $0.0079 per SMS

### 1.4 Create Verify Service (for OTP)

1. Go to **Verify** → **Services** (left sidebar)
2. Click **Create Service**
3. Service Name: `SmartHandoff OTP`
4. Click **Create**
5. Copy the **Service SID** (starts with VA...)

### ✅ Checklist - You Should Now Have:
- [ ] Account SID (ACxxxxxxxx...)
- [ ] Auth Token (hidden - click show to reveal)
- [ ] Phone Number (+1555...)
- [ ] Verify Service SID (VAxxxxxxxx...)

---

## Step 2: SendGrid Account Setup

### 2.1 Sign Up for SendGrid

1. Go to https://signup.sendgrid.com/
2. Complete registration (Free tier: 100 emails/day)
3. Verify your email

### 2.2 Create API Key

1. Log in to [SendGrid Dashboard](https://app.sendgrid.com/)
2. Go to **Settings** → **API Keys** (left sidebar)
3. Click **Create API Key**
4. Name: `SmartHandoff Production`
5. Permissions: **Full Access** (or minimum: Mail Send)
6. Click **Create & View**
7. **COPY THE KEY NOW** - it won't be shown again!

### 2.3 Verify Sender Email

1. Go to **Settings** → **Sender Authentication**
2. Choose **Domain Authentication** (recommended) or **Single Sender Verification**

**Option A: Single Sender (Quick)**
- Add email: `noreply@yourdomain.com`
- Verify via email link

**Option B: Domain Authentication (Production)**
- Add your domain
- Add DNS records (TXT, CNAME)
- Wait for verification (~10 min)

### ✅ Checklist - You Should Now Have:
- [ ] SendGrid API Key (SG.xxxxxxxx...)
- [ ] Verified sender email address

---

## Step 3: GCP Secret Manager Setup

### 3.1 Enable Secret Manager API

```powershell
# Set your project
$env:GCP_PROJECT_ID = "smarthandoff"
gcloud config set project $env:GCP_PROJECT_ID

# Enable API
gcloud services enable secretmanager.googleapis.com --project=$env:GCP_PROJECT_ID
```

### 3.2 Create Secrets

Run these commands one by one, replacing the placeholder values:

```powershell
# Twilio Account SID
$TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Replace with your value
echo $TWILIO_ACCOUNT_SID | gcloud secrets create twilio-account-sid `
  --project=$env:GCP_PROJECT_ID `
  --replication-policy=automatic `
  --data-file=-

# Twilio Auth Token
$TWILIO_AUTH_TOKEN = "your_auth_token_here"  # Replace with your value
echo $TWILIO_AUTH_TOKEN | gcloud secrets create twilio-auth-token `
  --project=$env:GCP_PROJECT_ID `
  --replication-policy=automatic `
  --data-file=-

# Twilio Verify Service SID
$TWILIO_VERIFY_SID = "VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Replace with your value
echo $TWILIO_VERIFY_SID | gcloud secrets create twilio-verify-service-sid `
  --project=$env:GCP_PROJECT_ID `
  --replication-policy=automatic `
  --data-file=-

# Twilio Phone Number
$TWILIO_PHONE = "+15551234567"  # Replace with your purchased number
echo $TWILIO_PHONE | gcloud secrets create twilio-phone-number `
  --project=$env:GCP_PROJECT_ID `
  --replication-policy=automatic `
  --data-file=-

# SendGrid API Key
$SENDGRID_KEY = "SG.xxxxxxxxxxxxxxxx"  # Replace with your API key
echo $SENDGRID_KEY | gcloud secrets create sendgrid-api-key `
  --project=$env:GCP_PROJECT_ID `
  --replication-policy=automatic `
  --data-file=-
```

### 3.3 Verify Secrets Created

```powershell
gcloud secrets list --project=$env:GCP_PROJECT_ID --filter="name:(twilio OR sendgrid)"
```

Expected output:
```
NAME                          CREATED              REPLICATION_POLICY  LOCATIONS
sendgrid-api-key             2026-07-26T...       automatic           -
twilio-account-sid           2026-07-26T...       automatic           -
twilio-auth-token            2026-07-26T...       automatic           -
twilio-phone-number          2026-07-26T...       automatic           -
twilio-verify-service-sid    2026-07-26T...       automatic           -
```

### ✅ Checklist:
- [ ] Secret Manager API enabled
- [ ] 5 secrets created and verified

---

## Step 4: GCP Pub/Sub Setup

### 4.1 Enable Pub/Sub API

```powershell
gcloud services enable pubsub.googleapis.com --project=$env:GCP_PROJECT_ID
```

### 4.2 Create Topics

```powershell
# Create notification-requests topic
gcloud pubsub topics create notification-requests --project=$env:GCP_PROJECT_ID

# Create care-team-alerts topic (for failed delivery alerts)
gcloud pubsub topics create care-team-alerts --project=$env:GCP_PROJECT_ID
```

### 4.3 Create Subscriptions

```powershell
# Subscription for notification service to read from
gcloud pubsub subscriptions create notification-service-sub `
  --topic=notification-requests `
  --ack-deadline=60 `
  --message-retention-duration=7d `
  --project=$env:GCP_PROJECT_ID

# Subscription for care team alerts (for monitoring/alerting)
gcloud pubsub subscriptions create care-team-alerts-sub `
  --topic=care-team-alerts `
  --ack-deadline=60 `
  --project=$env:GCP_PROJECT_ID
```

### 4.4 Verify Setup

```powershell
# List topics
gcloud pubsub topics list --project=$env:GCP_PROJECT_ID

# List subscriptions
gcloud pubsub subscriptions list --project=$env:GCP_PROJECT_ID
```

### ✅ Checklist:
- [ ] Pub/Sub API enabled
- [ ] notification-requests topic created
- [ ] care-team-alerts topic created
- [ ] Subscriptions created

---

## Step 5: Service Account & IAM Permissions

### 5.1 Create Service Account

```powershell
gcloud iam service-accounts create notification-service `
  --display-name="Notification Service" `
  --description="Service account for notification-svc Cloud Run service" `
  --project=$env:GCP_PROJECT_ID
```

### 5.2 Grant Secret Manager Access

```powershell
$SERVICE_ACCOUNT = "notification-service@$($env:GCP_PROJECT_ID).iam.gserviceaccount.com"

# Grant access to each secret
$SECRETS = @(
  "twilio-account-sid",
  "twilio-auth-token",
  "twilio-verify-service-sid",
  "twilio-phone-number",
  "sendgrid-api-key"
)

foreach ($SECRET in $SECRETS) {
  gcloud secrets add-iam-policy-binding $SECRET `
    --project=$env:GCP_PROJECT_ID `
    --member="serviceAccount:$SERVICE_ACCOUNT" `
    --role="roles/secretmanager.secretAccessor"
}
```

### 5.3 Grant Pub/Sub Permissions

```powershell
# Subscriber permission on notification-requests
gcloud pubsub subscriptions add-iam-policy-binding notification-service-sub `
  --member="serviceAccount:$SERVICE_ACCOUNT" `
  --role="roles/pubsub.subscriber" `
  --project=$env:GCP_PROJECT_ID

# Publisher permission on care-team-alerts
gcloud pubsub topics add-iam-policy-binding care-team-alerts `
  --member="serviceAccount:$SERVICE_ACCOUNT" `
  --role="roles/pubsub.publisher" `
  --project=$env:GCP_PROJECT_ID
```

### 5.4 Grant Cloud SQL Access (for database connection)

```powershell
gcloud projects add-iam-policy-binding $env:GCP_PROJECT_ID `
  --member="serviceAccount:$SERVICE_ACCOUNT" `
  --role="roles/cloudsql.client"
```

### 5.5 Verify Permissions

```powershell
# Check service account
gcloud iam service-accounts describe $SERVICE_ACCOUNT --project=$env:GCP_PROJECT_ID

# Check secret access (example for one secret)
gcloud secrets get-iam-policy twilio-account-sid --project=$env:GCP_PROJECT_ID
```

### ✅ Checklist:
- [ ] Service account created
- [ ] Secret Manager access granted
- [ ] Pub/Sub subscriber access granted
- [ ] Pub/Sub publisher access granted
- [ ] Cloud SQL client role granted

---

## Step 6: Deploy Notification Service to Cloud Run

### 6.1 Enable Cloud Run API

```powershell
gcloud services enable run.googleapis.com --project=$env:GCP_PROJECT_ID
gcloud services enable cloudbuild.googleapis.com --project=$env:GCP_PROJECT_ID
```

### 6.2 Create .env for Cloud Run

Create environment variables (these will be passed to Cloud Run):

```powershell
cd $env:USERPROFILE\source\repos\SmartHandoff\services\notification-svc

# Set variables
$DATABASE_URL = "postgresql+asyncpg://postgres:SmartHandoff%40123@/smarthandoff?host=/cloudsql/smarthandoff:us-central1:smarthandoff"
$SENDGRID_FROM_EMAIL = "noreply@smarthandoff.health"  # Replace with your verified email
```

### 6.3 Deploy to Cloud Run

```powershell
cd $env:USERPROFILE\source\repos\SmartHandoff\services\notification-svc

gcloud run deploy notification-service `
  --source . `
  --project=$env:GCP_PROJECT_ID `
  --region=us-central1 `
  --platform=managed `
  --service-account=$SERVICE_ACCOUNT `
  --set-env-vars="DATABASE_URL=$DATABASE_URL,GCP_PROJECT_ID=$($env:GCP_PROJECT_ID),PUBSUB_SUBSCRIPTION_ID=notification-service-sub,SENDGRID_FROM_EMAIL=$SENDGRID_FROM_EMAIL,TWILIO_FROM_NUMBER=$TWILIO_PHONE" `
  --add-cloudsql-instances="smarthandoff:us-central1:smarthandoff" `
  --allow-unauthenticated `
  --min-instances=1 `
  --max-instances=10 `
  --memory=512Mi `
  --cpu=1 `
  --timeout=300
```

### 6.4 Get Service URL

```powershell
gcloud run services describe notification-service `
  --project=$env:GCP_PROJECT_ID `
  --region=us-central1 `
  --format='value(status.url)'
```

Save this URL - you'll need it for Twilio webhook configuration!

Example: `https://notification-service-abc123-uc.a.run.app`

### 6.5 Test the Service

```powershell
# Test health endpoint
$SERVICE_URL = "<your-service-url-from-above>"
curl "$SERVICE_URL/health"

# Expected: {"status": "healthy"}
```

### ✅ Checklist:
- [ ] Cloud Run API enabled
- [ ] Service deployed successfully
- [ ] Service URL obtained
- [ ] Health check passes

---

## Step 7: Configure Twilio Webhook

### 7.1 Configure Webhook URL in Twilio Console

1. Log in to [Twilio Console](https://console.twilio.com/)
2. Go to **Phone Numbers** → **Manage** → **Active numbers**
3. Click on your SMS-enabled phone number
4. Scroll to **Messaging Configuration** section

**Configure Webhook:**
- **A MESSAGE COMES IN:**
  - Webhook: `<YOUR-SERVICE-URL>/webhooks/twilio/status`
  - HTTP Method: `POST`
  
Example: `https://notification-service-abc123-uc.a.run.app/webhooks/twilio/status`

5. Click **Save**

### 7.2 Test Webhook (Optional)

```powershell
# Send test webhook (will return 403 due to missing signature - this is correct!)
curl -X POST "$SERVICE_URL/webhooks/twilio/status" `
  -d "MessageSid=SM123&MessageStatus=delivered" `
  -H "Content-Type: application/x-www-form-urlencoded"

# Expected: 403 Forbidden (webhook signature validation working)
```

### ✅ Checklist:
- [ ] Webhook URL configured in Twilio
- [ ] Webhook validation tested

---

## Step 8: Test End-to-End SMS Flow

### 8.1 Publish Test Message to Pub/Sub

```powershell
# Test SMS notification
gcloud pubsub topics publish notification-requests `
  --project=$env:GCP_PROJECT_ID `
  --message='{
    "idempotency_key": "TEST-SMS-001",
    "type": "SMS",
    "phone": "+15555551234",
    "template": "test_message",
    "substitutions": {"name": "Test User"},
    "urgency_override": false
  }'
```

**Note:** Replace `+15555551234` with your own phone number for testing!

### 8.2 Check Service Logs

```powershell
gcloud run services logs read notification-service `
  --project=$env:GCP_PROJECT_ID `
  --region=us-central1 `
  --limit=50
```

Look for:
- ✅ Message consumed from Pub/Sub
- ✅ SMS dispatched via Twilio
- ✅ Database record created

### 8.3 Verify in Database

```powershell
# Start Cloud SQL Proxy if not running
& "$env:USERPROFILE\cloud-sql-proxy.exe" smarthandoff:us-central1:smarthandoff --port 5433
```

In another terminal:
```powershell
psql "host=localhost port=5433 dbname=smarthandoff user=postgres password=SmartHandoff@123"

-- Check notification record
SELECT id, idempotency_key, delivery_status, twilio_message_sid, created_at 
FROM notification 
WHERE idempotency_key = 'TEST-SMS-001';
```

### 8.4 Test Email Notification (Optional)

```powershell
gcloud pubsub topics publish notification-requests `
  --project=$env:GCP_PROJECT_ID `
  --message='{
    "idempotency_key": "TEST-EMAIL-001",
    "type": "EMAIL",
    "email": "your.email@example.com",
    "template": "patient_portal_link",
    "substitutions": {"first_name": "John", "portal_link": "https://portal.smarthandoff.health/login?token=TEST"}
  }'
```

### ✅ Checklist:
- [ ] Test message published to Pub/Sub
- [ ] Service logs show message processing
- [ ] Database record created
- [ ] SMS received on test phone

---

## Summary: Setup Complete! 🎉

You should now have:
- ✅ Twilio account configured with SMS capability
- ✅ SendGrid account configured for email
- ✅ GCP Secret Manager storing credentials securely
- ✅ Pub/Sub topics and subscriptions created
- ✅ Service account with proper IAM permissions
- ✅ Notification service deployed to Cloud Run
- ✅ Twilio webhook configured
- ✅ End-to-end testing completed

---

## Next Steps

1. **Upload SendGrid Templates:**
   ```powershell
   cd $env:USERPROFILE\source\repos\SmartHandoff\services\notification-svc
   python notifications/upload_sendgrid_templates.py
   ```

2. **Set Up Monitoring:**
   - Create Cloud Monitoring dashboard for notification metrics
   - Set up alerts for failed deliveries
   - Monitor Pub/Sub message age

3. **Production Hardening:**
   - Enable VPC Service Controls
   - Set up Cloud Armor rules
   - Configure Cloud CDN for template assets
   - Implement rate limiting

4. **Integration Testing:**
   - Test with real patient workflows
   - Verify opt-out functionality
   - Test urgency override scenarios

---

## Troubleshooting

### Issue: Cloud Run deployment fails

**Check:**
```powershell
# View build logs
gcloud builds list --project=$env:GCP_PROJECT_ID --limit=5

# Get specific build log
gcloud builds log <BUILD_ID> --project=$env:GCP_PROJECT_ID
```

### Issue: Service can't connect to Cloud SQL

**Check:**
- Cloud SQL instance is running: `gcloud sql instances describe smarthandoff --project=$env:GCP_PROJECT_ID`
- Service account has `roles/cloudsql.client` role
- `--add-cloudsql-instances` flag included in deployment

### Issue: SMS not sending

**Check:**
1. Twilio credentials in Secret Manager are correct
2. Service logs for Twilio API errors: `gcloud run services logs read notification-service --limit=100`
3. Twilio account balance/trial limitations
4. Phone number format (must be E.164: +15551234567)

### Issue: Webhook signature validation fails

**Verify:**
- Webhook URL in Twilio exactly matches deployed URL
- Auth token in Secret Manager is correct
- No spaces or newlines in auth token secret

---

## Cost Estimate

**Monthly Costs (Production):**
- Cloud Run (1 service, low traffic): ~$5-10
- Pub/Sub (< 10K messages/day): ~$0.50
- Secret Manager (5 secrets, 100K accesses): ~$0.30
- Cloud SQL Proxy: Free
- Twilio SMS (1,000 messages): ~$7.90
- SendGrid (Free tier: 100 emails/day): $0
- **Total: ~$14-19/month**

**Trial/Free Tier Coverage:**
- Twilio: $15.50 trial credit
- SendGrid: 100 emails/day free forever
- GCP: $300 credit for 90 days

---

## Support Resources

- **Twilio Docs:** https://www.twilio.com/docs/sms
- **SendGrid Docs:** https://docs.sendgrid.com/
- **GCP Secret Manager:** https://cloud.google.com/secret-manager/docs
- **Cloud Run:** https://cloud.google.com/run/docs
- **Project Issues:** File issues in GitHub repo

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-26  
**Maintained By:** SmartHandoff DevOps Team
