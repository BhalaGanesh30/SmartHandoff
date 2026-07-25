# US-065 OTP Authentication - Secret Manager Setup Guide

> **User Story:** US-065 | **Epic:** EP-013 | **Sprint:** 2
> **Date:** 2026-07-25

## Overview

This guide provides step-by-step instructions for configuring GCP Secret Manager secrets required for the patient OTP authentication feature (US-065).

## Prerequisites

- GCP project with Secret Manager API enabled
- `gcloud` CLI authenticated with appropriate permissions
- Twilio account with Verify service configured
- Shared portal JWT secret from patient portal team

## Secrets to Create

| Secret Name | Description | Source |
|-------------|-------------|--------|
| `smarthandoff-otp-phone-salt` | 64-char salt for phone number hashing | Auto-generated (see below) |
| `twilio-account-sid` | Twilio Account SID | Twilio Console → Account Settings |
| `twilio-auth-token` | Twilio Auth Token | Twilio Console → Account Settings |
| `twilio-verify-sid` | Twilio Verify Service SID | Twilio Console → Verify → Services |
| `portal-jwt-secret` | JWT secret for portal token validation | Shared with patient portal |

---

## Step 1: Generate OTP Phone Salt

The salt is used to derive Redis rate-limit keys to prevent phone number enumeration (SEC-003).

**Generated Salt (64 characters):**
```
_VVjyogyckkADHLhsKIP_tn8WWX5B7KVQHjRpEVRlRbF6GTYdRvjrBeeasw35dhX
```

> **Security Note:** This salt should be unique per environment (dev/staging/prod). Generate a new salt for production using:
> ```bash
> python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits + '-_') for _ in range(64)))"
> ```

---

## Step 2: Create GCP Secrets

Replace `YOUR_GCP_PROJECT_ID` with your actual GCP project ID before running these commands.

### 2.1. OTP Phone Salt

```bash
echo -n "_VVjyogyckkADHLhsKIP_tn8WWX5B7KVQHjRpEVRlRbF6GTYdRvjrBeeasw35dhX" | \
  gcloud secrets create smarthandoff-otp-phone-salt \
  --data-file=- \
  --replication-policy=automatic \
  --project=YOUR_GCP_PROJECT_ID
```

### 2.2. Twilio Account SID

Obtain from: Twilio Console → Account → Account Info → Account SID

```bash
echo -n "YOUR_TWILIO_ACCOUNT_SID" | \
  gcloud secrets create twilio-account-sid \
  --data-file=- \
  --replication-policy=automatic \
  --project=YOUR_GCP_PROJECT_ID
```

### 2.3. Twilio Auth Token

Obtain from: Twilio Console → Account → Account Info → Auth Token

```bash
echo -n "YOUR_TWILIO_AUTH_TOKEN" | \
  gcloud secrets create twilio-auth-token \
  --data-file=- \
  --replication-policy=automatic \
  --project=YOUR_GCP_PROJECT_ID
```

### 2.4. Twilio Verify Service SID

Obtain from: Twilio Console → Verify → Services → [Your Service] → Service SID

> **Note:** Create a Verify Service first if you don't have one:
> 1. Go to Twilio Console → Verify → Services
> 2. Click "Create new Service"
> 3. Name it "SmartHandoff OTP"
> 4. Copy the Service SID

```bash
echo -n "YOUR_TWILIO_VERIFY_SID" | \
  gcloud secrets create twilio-verify-sid \
  --data-file=- \
  --replication-policy=automatic \
  --project=YOUR_GCP_PROJECT_ID
```

### 2.5. Portal JWT Secret

Coordinate with the patient portal team to obtain the shared JWT secret.

```bash
echo -n "YOUR_PORTAL_JWT_SECRET" | \
  gcloud secrets create portal-jwt-secret \
  --data-file=- \
  --replication-policy=automatic \
  --project=YOUR_GCP_PROJECT_ID
```

---

## Step 3: Grant IAM Permissions

Grant the Cloud Run service account access to read these secrets.

```bash
# Replace with your actual service account email
SERVICE_ACCOUNT="smarthandoff-backend@YOUR_PROJECT.iam.gserviceaccount.com"

# Grant access to all OTP-related secrets
for SECRET in smarthandoff-otp-phone-salt twilio-account-sid twilio-auth-token twilio-verify-sid portal-jwt-secret; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --project=YOUR_GCP_PROJECT_ID
done
```

---

## Step 4: Update Cloud Run Service Configuration

### Option A: Using Cloud Run YAML (service.yaml)

Add to your Cloud Run service configuration:

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: smarthandoff-backend
spec:
  template:
    spec:
      containers:
      - image: gcr.io/YOUR_PROJECT/smarthandoff-backend:latest
        env:
          # ... existing environment variables ...
          
          # OTP Authentication Secrets (US-065)
          - name: OTP_PHONE_SALT
            valueFrom:
              secretKeyRef:
                name: smarthandoff-otp-phone-salt
                key: latest
          - name: TWILIO_ACCOUNT_SID
            valueFrom:
              secretKeyRef:
                name: twilio-account-sid
                key: latest
          - name: TWILIO_AUTH_TOKEN
            valueFrom:
              secretKeyRef:
                name: twilio-auth-token
                key: latest
          - name: TWILIO_VERIFY_SID
            valueFrom:
              secretKeyRef:
                name: twilio-verify-sid
                key: latest
          - name: PORTAL_JWT_SECRET
            valueFrom:
              secretKeyRef:
                name: portal-jwt-secret
                key: latest
```

### Option B: Using gcloud CLI

```bash
gcloud run services update smarthandoff-backend \
  --update-secrets=OTP_PHONE_SALT=smarthandoff-otp-phone-salt:latest,TWILIO_ACCOUNT_SID=twilio-account-sid:latest,TWILIO_AUTH_TOKEN=twilio-auth-token:latest,TWILIO_VERIFY_SID=twilio-verify-sid:latest,PORTAL_JWT_SECRET=portal-jwt-secret:latest \
  --region=us-central1 \
  --project=YOUR_GCP_PROJECT_ID
```

---

## Step 5: Verify Secret Access

Test that the service account can access the secrets:

```bash
# From Cloud Shell or local with gcloud auth
gcloud secrets versions access latest --secret="smarthandoff-otp-phone-salt"
gcloud secrets versions access latest --secret="twilio-account-sid"
gcloud secrets versions access latest --secret="twilio-verify-sid"

# Should return the secret values
```

> **Warning:** Redact these values from logs in production environments!

---

## Step 6: Environment-Specific Configuration

For each environment (dev, staging, production):

1. **Generate unique salts** for each environment
2. **Use separate Twilio accounts** or sub-accounts per environment
3. **Rotate secrets regularly** (recommended: every 90 days)
4. **Audit secret access** via Cloud Logging

### Multi-Environment Example

```bash
# Development
gcloud secrets create smarthandoff-otp-phone-salt-dev --data-file=- --project=dev-project
gcloud secrets create twilio-account-sid-dev --data-file=- --project=dev-project

# Production
gcloud secrets create smarthandoff-otp-phone-salt-prod --data-file=- --project=prod-project
gcloud secrets create twilio-account-sid-prod --data-file=- --project=prod-project
```

---

## Security Compliance Checklist

- [x] All secrets use automatic replication for high availability
- [x] Service account has minimal required permissions (secretAccessor only)
- [x] Secrets are injected as environment variables (TR-021)
- [x] No secrets committed to version control
- [x] OTP phone salt is environment-specific and rotates independently
- [x] Twilio credentials follow least-privilege principle
- [x] Portal JWT secret is shared securely (not via email/Slack)

---

## Troubleshooting

### Secret Not Found

```bash
# List all secrets in the project
gcloud secrets list --project=YOUR_GCP_PROJECT_ID

# Verify secret exists
gcloud secrets describe smarthandoff-otp-phone-salt --project=YOUR_GCP_PROJECT_ID
```

### Permission Denied

```bash
# Check IAM policy for a secret
gcloud secrets get-iam-policy smarthandoff-otp-phone-salt --project=YOUR_GCP_PROJECT_ID

# Verify service account has access
gcloud projects get-iam-policy YOUR_GCP_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:smarthandoff-backend@*"
```

### Cloud Run Not Picking Up Secrets

1. Verify the service revision has the correct environment variable mappings
2. Check Cloud Run logs for secret mount errors
3. Ensure Secret Manager API is enabled in the project
4. Confirm the secret version is `latest` or a valid version number

---

## Secret Rotation Procedure

When rotating secrets (recommended every 90 days):

1. **Create new secret version:**
   ```bash
   echo -n "NEW_SECRET_VALUE" | gcloud secrets versions add SECRET_NAME --data-file=-
   ```

2. **Update Cloud Run** to use the new version (automatic with `latest`)

3. **Monitor** for any authentication failures

4. **Disable old versions** after confirming new version works:
   ```bash
   gcloud secrets versions disable VERSION_NUMBER --secret=SECRET_NAME
   ```

5. **Destroy old versions** after retention period:
   ```bash
   gcloud secrets versions destroy VERSION_NUMBER --secret=SECRET_NAME
   ```

---

## References

- **User Story:** [US-065 - Patient OTP Authentication](../US-065/US-065.md)
- **Task:** [TASK-001 - OTP Crypto Helpers](task_001_otp_crypto_helpers.md)
- **Task:** [TASK-002 - OTP Request Endpoint](task_002_otp_request_endpoint.md)
- **Design:** [design.md §7.5 - Patient Portal OTP Flow](../../../../docs/design.md)
- **Security:** SEC-003, AIR-043, TR-021

---

## Support

For issues or questions:
- **Twilio Support:** https://support.twilio.com
- **GCP Secret Manager:** https://cloud.google.com/secret-manager/docs
- **Internal:** #smarthandoff-dev Slack channel
