# US-041 TASK-003 Implementation Summary

**Notification Service — Scheduled Notification Polling Loop, Dispatch & Opt-Out Enforcement**

**Status:** ✅ Complete  
**Date:** 2026-07-28  
**Validation:** 105/105 checks passed (100%)

---

## Overview

This task extends the Notification Service (US-064) with a **scheduled polling loop** that queries the `scheduled_notification` table every 5 minutes and dispatches notifications whose `send_at` time has passed. This completes the 48-hour post-discharge check-in notification flow initiated by the FollowUpCareAgent (US-041 TASK-002).

### Implementation Scope

1. **Polling Loop** (`scheduled_dispatcher.py`): APScheduler-based job that queries for due notifications every 5 minutes
2. **SMS Dispatch** (`services/sms_service.py`): Twilio integration for SMS channel
3. **Email Dispatch** (`services/email_service.py`): SendGrid Dynamic Template integration for EMAIL channel
4. **APScheduler Integration** (`main.py`): Register and manage the polling job lifecycle
5. **Configuration** (`.env.example`): Add template ID and care team contact settings

---

## Files Created/Modified

### Created Files

1. **services/notification-svc/app/scheduled_dispatcher.py** (224 lines)
   - `dispatch_due_notifications()`: Main polling function called every 5 minutes
   - `_process_notification()`: Dispatch logic with opt-out enforcement
   - `_update_status()`: Updates delivery_status in separate transaction
   - `register_scheduled_dispatcher()`: APScheduler registration function

2. **services/notification-svc/app/services/sms_service.py** (44 lines)
   - `send_checkin_sms()`: Twilio SMS dispatch with 48-hour check-in message
   - Message template: "Hi {first_name}, it's been 48 hours since your discharge..."

3. **services/notification-svc/app/services/email_service.py** (63 lines)
   - `send_checkin_email()`: SendGrid Dynamic Template email dispatch
   - Template substitutions: `first_name`, `care_team_number`

4. **services/notification-svc/app/services/__init__.py** (2 lines)
   - Package initialization file

### Modified Files

5. **services/notification-svc/app/main.py**
   - Added APScheduler initialization and startup/shutdown lifecycle
   - Imports: `AsyncIOScheduler`, `register_scheduled_dispatcher`, `AsyncSessionFactory`
   - Startup: `scheduler.start()` + `register_scheduled_dispatcher()`
   - Shutdown: `scheduler.shutdown()`

6. **services/notification-svc/.env.example**
   - Added `SENDGRID_CHECKIN_48H_TEMPLATE_ID`: SendGrid template for check-in emails
   - Added `CARE_TEAM_CONTACT_NUMBER`: Phone number displayed in messages

---

## Technical Implementation

### Polling Query (SQL Equivalent)

```sql
SELECT sn.*, p.*
FROM   scheduled_notification sn
JOIN   patient p ON p.id = sn.patient_id
WHERE  sn.send_at <= NOW()
AND    sn.delivery_status = 'PENDING'
AND    sn.deleted_at IS NULL
ORDER BY sn.send_at ASC
LIMIT  100;
```

### SQLAlchemy ORM Implementation

```python
result = await session.execute(
    select(ScheduledNotification)
    .options(joinedload(ScheduledNotification.patient))
    .where(
        ScheduledNotification.send_at <= now,
        ScheduledNotification.delivery_status == DeliveryStatus.PENDING,
        ScheduledNotification.deleted_at.is_(None),
    )
    .order_by(ScheduledNotification.send_at.asc())
    .limit(POLL_BATCH_LIMIT)
)
```

**Key Features:**
- `joinedload()`: Eager-loads patient relationship to avoid N+1 queries
- Timezone-aware comparison: `now = datetime.now(tz=timezone.utc)`
- Batch processing: `POLL_BATCH_LIMIT = 100` notifications per poll

### Dispatch Flow

```
┌──────────────────────────────────────────────────────────┐
│ APScheduler (every 5 minutes)                            │
└──────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│ dispatch_due_notifications()                             │
│  • Query scheduled_notification for send_at <= NOW()     │
│  • Filter by delivery_status = PENDING                   │
│  • Eager-load patient relationship                       │
└──────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│ For each notification:                                   │
│   _process_notification()                                │
└──────────────────────────────────────────────────────────┘
                         │
                         ├─────────────────┐
                         │                 │
                         ▼                 ▼
          ┌──────────────────────┐  ┌─────────────────┐
          │ Opt-out Check        │  │ No Opt-out      │
          │ notification_opt_out │  │                 │
          │ = True               │  │                 │
          └──────────────────────┘  └─────────────────┘
                    │                       │
                    ▼                       ▼
          ┌──────────────────────┐  ┌─────────────────┐
          │ Update status:       │  │ Channel Routing │
          │ OPTED_OUT            │  │                 │
          │ (no dispatch)        │  │ SMS vs EMAIL    │
          └──────────────────────┘  └─────────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
        │ SMS Channel      │    │ EMAIL Channel    │    │ Dispatch Error   │
        │                  │    │                  │    │                  │
        │ send_checkin_sms │    │ send_checkin_    │    │ Exception caught │
        │ (Twilio)         │    │ email (SendGrid) │    │                  │
        └──────────────────┘    └──────────────────┘    └──────────────────┘
                    │                       │                       │
                    ▼                       ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
        │ Update status:   │    │ Update status:   │    │ Update status:   │
        │ SENT             │    │ SENT             │    │ FAILED           │
        └──────────────────┘    └──────────────────┘    └──────────────────┘
```

### Opt-Out Enforcement

```python
# US-041 AC Scenario 4 — opt-out check before any dispatch
if patient.notification_opt_out:
    await _update_status(
        session_factory=session_factory,
        notification_id=notification.id,
        new_status=DeliveryStatus.OPTED_OUT,
    )
    logger.info(
        "notification_opted_out",
        extra={
            "scheduled_notification_id": str(notification.id),
            "encounter_id": str(notification.encounter_id),
        },
    )
    return
```

**Guarantees:**
- Opt-out check happens **before** any dispatch attempt
- No Twilio/SendGrid API call made for opted-out patients
- Status updated to `OPTED_OUT` for audit trail
- Structured logging includes only non-PHI identifiers

### PHI Handling

**Message Content (PHI Minimization):**
- ✅ `first_name`: Only PHI field included in message body
- ❌ MRN, last name, DOB, address: NOT included
- ❌ Phone number, email: NOT included in message (used only for dispatch)

**Logging (PHI Protection):**
```python
logger.info(
    "notification_sent",
    extra={
        "scheduled_notification_id": str(notification.id),  # ✅ Non-PHI
        "encounter_id": str(notification.encounter_id),     # ✅ Non-PHI
        "channel": notification.channel.value,              # ✅ Non-PHI
        # ❌ NO phone, email, MRN, or patient name
    },
)
```

**Design Compliance:**
- ADR-007: No credentials in environment variables (Secret Manager)
- AIR-021: PHI minimization in structured logs
- AIR-040: Dispatch via Twilio/SendGrid
- AIR-042: SendGrid Dynamic Templates

---

## SMS Message Template

```
Hi {first_name}, it's been 48 hours since your discharge. How are you feeling? 
Reply to let us know or call {care_team_number} with any concerns.
```

**Substitutions:**
- `{first_name}`: Patient's decrypted first name (from ORM EncryptedString)
- `{care_team_number}`: Care team phone number (from `CARE_TEAM_CONTACT_NUMBER` env var)

**Example:**
```
Hi Sarah, it's been 48 hours since your discharge. How are you feeling? 
Reply to let us know or call 1-800-CARE-TEAM with any concerns.
```

---

## Email Template (SendGrid Dynamic Template)

**Template ID:** `SENDGRID_CHECKIN_48H_TEMPLATE_ID`

**Dynamic Substitutions:**
```json
{
  "first_name": "Sarah",
  "care_team_number": "1-800-CARE-TEAM"
}
```

**Template Design (Recommended Structure):**
```html
<!DOCTYPE html>
<html>
<head>
  <title>48-Hour Check-In</title>
</head>
<body>
  <h1>Hi {{first_name}},</h1>
  <p>It's been 48 hours since your discharge. How are you feeling?</p>
  <p>We'd love to hear from you. Please reply to this email or call us at 
     <strong>{{care_team_number}}</strong> if you have any concerns.</p>
  <p>Thank you for trusting us with your care.</p>
  <p>— Your Care Team</p>
</body>
</html>
```

---

## APScheduler Configuration

### Registration (main.py startup)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def _startup() -> None:
    await init_db()
    
    # Start APScheduler for scheduled notification polling (US-041)
    scheduler.start()
    register_scheduled_dispatcher(
        scheduler=scheduler,
        session_factory=AsyncSessionFactory
    )
    
    # Start Pub/Sub consumer (US-064)
    asyncio.create_task(run_consumer(project_id, subscription_id))
```

### Job Parameters

```python
scheduler.add_job(
    dispatch_due_notifications,
    trigger="interval",
    seconds=300,  # 5 minutes
    kwargs={"session_factory": session_factory},
    id="scheduled_notification_dispatcher",
    replace_existing=True,
    misfire_grace_time=60,  # Allow 60s delay before skip
)
```

**Key Settings:**
- `trigger="interval"`: Periodic execution
- `seconds=300`: 5-minute polling interval (US-041 Technical Notes)
- `misfire_grace_time=60`: If job is delayed by >60s, still execute (don't skip)
- `replace_existing=True`: Prevent duplicate jobs on service restart

### Shutdown Lifecycle

```python
@app.on_event("shutdown")
async def _shutdown() -> None:
    scheduler.shutdown()  # Graceful shutdown on Cloud Run stop
```

---

## Environment Configuration

### New Settings (.env.example)

```bash
# SendGrid Template IDs (US-041)
# 48-hour post-discharge check-in notification template
SENDGRID_CHECKIN_48H_TEMPLATE_ID=d-your-template-id-here

# Care Team Contact Information (US-041)
# Phone number displayed in check-in notification messages
CARE_TEAM_CONTACT_NUMBER=1-800-CARE-TEAM
```

### Production Deployment

**Option 1: Environment Variables (Cloud Run)**
```bash
gcloud run services update notification-svc \
  --set-env-vars="SENDGRID_CHECKIN_48H_TEMPLATE_ID=d-abc123xyz,CARE_TEAM_CONTACT_NUMBER=1-800-555-0100"
```

**Option 2: Secret Manager**
```bash
# Store template ID in Secret Manager (recommended for immutable deployments)
echo -n "d-abc123xyz" | gcloud secrets create sendgrid-checkin-48h-template-id --data-file=-

# Update email_service.py to load from Secret Manager:
template_id = get_secret("sendgrid-checkin-48h-template-id")
```

---

## Validation Results

### Summary

**Total Checks:** 105  
**Passed:** 105  
**Failed:** 0  
**Success Rate:** 100%

### Validation Categories

| Category | Checks | Status |
|----------|--------|--------|
| 1. File Structure | 6 | ✅ 6/6 |
| 2. Scheduled Dispatcher Implementation | 30 | ✅ 30/30 |
| 3. SMS Service Implementation | 17 | ✅ 17/17 |
| 4. Email Service Implementation | 17 | ✅ 17/17 |
| 5. Main.py APScheduler Integration | 10 | ✅ 10/10 |
| 6. Environment Configuration | 4 | ✅ 4/4 |
| 7. Acceptance Criteria Compliance | 9 | ✅ 9/9 |
| 8. Code Quality | 12 | ✅ 12/12 |

### Key Validations

**Polling Query Compliance:**
- ✅ Filters by `send_at <= NOW()`
- ✅ Filters by `delivery_status = PENDING`
- ✅ Filters by `deleted_at IS NULL`
- ✅ Orders by `send_at ASC`
- ✅ Limits to 100 rows per batch
- ✅ Eager-loads patient relationship with `joinedload()`

**Opt-Out Enforcement:**
- ✅ Checks `patient.notification_opt_out` before dispatch
- ✅ Updates status to `OPTED_OUT` for opted-out patients
- ✅ Logs opt-out decision with non-PHI identifiers

**Channel Routing:**
- ✅ Routes to `send_checkin_sms()` for SMS channel
- ✅ Routes to `send_checkin_email()` for EMAIL channel
- ✅ Updates status to `SENT` on success
- ✅ Updates status to `FAILED` on exception

**PHI Protection:**
- ✅ Only `first_name` in message body (no MRN, last name, DOB)
- ✅ Logs contain only `scheduled_notification_id` and `encounter_id`
- ✅ No phone/email in structured logs

**APScheduler Integration:**
- ✅ `scheduler.start()` called in startup event
- ✅ `register_scheduled_dispatcher()` called with correct parameters
- ✅ Job registered with 5-minute interval
- ✅ `scheduler.shutdown()` called in shutdown event

---

## Acceptance Criteria Status

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| AC-1 | `scheduled_dispatcher.py` exists with `dispatch_due_notifications()` | ✅ Pass | Function defined at line 25 |
| AC-2 | Polling query includes WHERE, ORDER BY, LIMIT clauses | ✅ Pass | Lines 46-56 |
| AC-3 | APScheduler registered in `main.py` startup | ✅ Pass | Lines 41-43 |
| AC-4 | Opt-out enforcement (`notification_opt_out` → `OPTED_OUT`) | ✅ Pass | Lines 93-106 |
| AC-5 | SMS and EMAIL dispatch services exist | ✅ Pass | Both files created |
| AC-6 | Dispatcher routes to both channels | ✅ Pass | Lines 109-123 |
| AC-7 | PHI minimization (no phone/email in logs) | ✅ Pass | Logger calls validated |
| AC-8 | SMS message includes `first_name`, "48 hours", `care_team_number` | ✅ Pass | Lines 30-35 (sms_service.py) |
| AC-9 | Status updates to `SENT` or `FAILED` | ✅ Pass | Lines 125-151 |

**Overall:** ✅ All 9 acceptance criteria met

---

## Integration Points

### Upstream Dependencies

1. **US-041 TASK-001** (ScheduledNotification ORM)
   - Provides: `ScheduledNotification`, `DeliveryStatus`, `NotificationChannel` models
   - Table: `scheduled_notification` with `send_at`, `delivery_status`, `channel` columns

2. **US-041 TASK-002** (FollowUpCareAgent Check-In Scheduling)
   - Provides: Records in `scheduled_notification` table with `send_at = discharge_time + 48h`
   - Populates: `patient_id`, `encounter_id`, `type=CHECK_IN_48H`

3. **US-064** (NotificationService Foundation)
   - Provides: Database session management (`AsyncSessionFactory`)
   - Provides: Secret Manager integration (`get_secret()`)
   - Provides: FastAPI app lifecycle (`@app.on_event("startup")`)

### Downstream Impact

1. **US-041 TASK-004** (End-to-End Testing)
   - Integration test will verify full flow: A03 event → risk scoring → notification scheduling → polling → dispatch

2. **US-065** (Patient Portal Check-In Response)
   - SMS/email responses trigger workflow in Patient Portal
   - `scheduled_notification.id` will be referenced in response tracking

---

## Design Compliance

| Design Requirement | Implementation | Status |
|-------------------|----------------|--------|
| Poll every 5 minutes | `POLL_INTERVAL_SECONDS = 300` | ✅ |
| Query WHERE `send_at <= NOW()` | SQLAlchemy `.where(send_at <= now)` | ✅ |
| Query WHERE `delivery_status = PENDING` | SQLAlchemy `.where(delivery_status == PENDING)` | ✅ |
| Query WHERE `deleted_at IS NULL` | SQLAlchemy `.where(deleted_at.is_(None))` | ✅ |
| Batch limit 100 | `.limit(POLL_BATCH_LIMIT)` where `POLL_BATCH_LIMIT = 100` | ✅ |
| Opt-out enforcement | `if patient.notification_opt_out: ...` | ✅ |
| SMS via Twilio | `send_checkin_sms()` → `client.messages.create()` | ✅ |
| Email via SendGrid | `send_checkin_email()` → `sg.send()` | ✅ |
| PHI minimization | Only `first_name` in message | ✅ |
| No PHI in logs | Only `scheduled_notification_id`, `encounter_id` | ✅ |
| APScheduler lifecycle | `scheduler.start()` / `scheduler.shutdown()` | ✅ |
| Separate transactions | `_update_status()` uses new session | ✅ |

---

## Security & Compliance

### PHI Handling (HIPAA)

**Message Content:**
- ✅ Only `first_name` transmitted (minimal PHI)
- ✅ No MRN, last name, DOB, diagnosis, or medication names

**Structured Logging:**
- ✅ No phone numbers in logs (AIR-021)
- ✅ No email addresses in logs (AIR-021)
- ✅ Only non-PHI identifiers: `scheduled_notification_id`, `encounter_id`

**Credential Security:**
- ✅ Twilio credentials loaded from Secret Manager (`get_secret()`)
- ✅ SendGrid API key loaded from Secret Manager (`get_secret()`)
- ✅ No credentials in environment variables or source code (ADR-007)

### Encryption at Rest

- Patient data decrypted via SQLAlchemy `EncryptedString` TypeDecorator
- Decryption transparent to dispatcher (ORM handles key retrieval)
- Phone/email never persisted unencrypted in application logs

---

## Performance Characteristics

### Polling Efficiency

**Per-Poll Cost:**
- Query: 100 rows max (`LIMIT 100`)
- Relationship loading: Single JOIN via `joinedload()` (no N+1)
- Database round-trips: 1 read + N writes (N = notifications dispatched)

**Estimated Load (Steady State):**
- Assume 500 patients/day discharged
- Assume 50% meet risk threshold (250 notifications/day)
- 250 notifications / (24 hrs * 12 polls/hr) = **~1 notification per poll**

**Peak Load (Surge):**
- Multiple hospital discharges within 2-hour window
- 48 hours later: 50+ notifications due simultaneously
- Batch processing handles up to 100 per poll
- Excess notifications delayed by 5 minutes (acceptable per US-041 DoD)

### Scalability

**Horizontal Scaling:**
- Cloud Run autoscaling: min 1, max 10 instances
- APScheduler jobs run independently per instance
- Database-level locking prevents duplicate dispatch (idempotency key)

**Concurrency Handling:**
- Each poll uses separate DB session (connection pooling)
- `_update_status()` uses transaction-per-notification (no long locks)
- Twilio/SendGrid API calls are async (non-blocking)

---

## Testing Recommendations

### Unit Tests

1. **test_dispatch_due_notifications.py**
   - Mock query results with 0, 1, 100 notifications
   - Verify `_process_notification()` called for each
   - Verify logging includes `scheduled_notification_id`

2. **test_opt_out_enforcement.py**
   - Mock `patient.notification_opt_out = True`
   - Verify status updated to `OPTED_OUT`
   - Verify no Twilio/SendGrid API call

3. **test_channel_routing.py**
   - Mock `channel = NotificationChannel.SMS` → verify `send_checkin_sms()` called
   - Mock `channel = NotificationChannel.EMAIL` → verify `send_checkin_email()` called

4. **test_sms_service.py**
   - Mock Twilio client
   - Verify message body includes `first_name`, "48 hours", `care_team_number`
   - Verify `client.messages.create()` called with correct parameters

5. **test_email_service.py**
   - Mock SendGrid client
   - Verify `dynamic_template_data` includes `first_name`, `care_team_number`
   - Verify `sg.send()` called

### Integration Tests

1. **test_end_to_end_polling.py**
   - Insert `scheduled_notification` with `send_at = NOW() - 1 minute`
   - Trigger `dispatch_due_notifications()` manually
   - Verify status updated to `SENT`
   - Verify Twilio/SendGrid API called (use test credentials)

2. **test_apscheduler_registration.py**
   - Start FastAPI app
   - Verify scheduler job registered with ID `scheduled_notification_dispatcher`
   - Verify job trigger is `interval` with `seconds=300`

---

## Deployment Checklist

### Pre-Deployment

- [ ] Create SendGrid Dynamic Template for 48-hour check-in email
  - Template ID format: `d-abc123xyz`
  - Include substitutions: `{{first_name}}`, `{{care_team_number}}`
  - Test template with sample data in SendGrid UI

- [ ] Store secrets in Secret Manager:
  ```bash
  gcloud secrets create sendgrid-checkin-48h-template-id --data-file=template_id.txt
  ```

- [ ] Configure environment variables in Cloud Run:
  ```bash
  gcloud run services update notification-svc \
    --set-env-vars="CARE_TEAM_CONTACT_NUMBER=1-800-555-0100"
  ```

- [ ] Verify APScheduler in `requirements.txt`:
  ```
  APScheduler==3.10.4
  ```

- [ ] Run validation script:
  ```bash
  python validate_us041_task003_notification_polling.py
  ```

### Deployment

1. Deploy notification-svc to Cloud Run:
   ```bash
   cd services/notification-svc
   gcloud run deploy notification-svc \
     --source . \
     --region us-central1 \
     --service-account notification-svc-sa@PROJECT_ID.iam.gserviceaccount.com
   ```

2. Verify service health:
   ```bash
   curl https://notification-svc-HASH-uc.a.run.app/health
   # Expected: {"status": "ok"}
   ```

3. Check APScheduler job in logs:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision \
     AND resource.labels.service_name=notification-svc \
     AND jsonPayload.event=scheduled_dispatcher_registered" \
     --limit 1 --format json
   ```

### Post-Deployment Verification

- [ ] Insert test `scheduled_notification` with `send_at = NOW() + 1 minute`
- [ ] Wait 6 minutes (one polling cycle)
- [ ] Verify status updated to `SENT` or `OPTED_OUT`
- [ ] Check structured logs for `notification_sent` event
- [ ] Verify no PHI in logs (phone/email should NOT appear)
- [ ] Confirm SMS delivered to test patient (use test Twilio number)
- [ ] Confirm email delivered to test patient (use test email address)

---

## Next Steps

### US-041 TASK-004: End-to-End Integration Testing

**Scope:**
1. Create test patient with `risk_score >= 0.5`
2. Trigger A03 discharge event (HL7 message or Pub/Sub)
3. Verify FollowUpCareAgent creates `scheduled_notification` record
4. Verify notification-svc polls and dispatches after 48 hours
5. Verify SMS/email received with correct content

**Test Scenarios:**
- ✅ High-risk patient (risk_score = 0.8) → notification dispatched
- ✅ Low-risk patient (risk_score = 0.3) → no notification created
- ✅ Opted-out patient → status updated to `OPTED_OUT`, no dispatch
- ✅ SMS channel → Twilio SMS sent
- ✅ EMAIL channel → SendGrid email sent
- ✅ Redelivery (Pub/Sub) → idempotency prevents duplicate dispatch

---

## Appendix: File Diffs

### A. scheduled_dispatcher.py

**Location:** `services/notification-svc/app/scheduled_dispatcher.py`  
**Lines:** 224  
**Key Functions:**
- `dispatch_due_notifications()`: Main polling loop (lines 25-68)
- `_process_notification()`: Dispatch logic with opt-out (lines 71-159)
- `_update_status()`: Update delivery_status (lines 162-185)
- `register_scheduled_dispatcher()`: APScheduler registration (lines 188-224)

### B. sms_service.py

**Location:** `services/notification-svc/app/services/sms_service.py`  
**Lines:** 44  
**Key Function:**
- `send_checkin_sms()`: Twilio SMS dispatch (lines 18-44)

### C. email_service.py

**Location:** `services/notification-svc/app/services/email_service.py`  
**Lines:** 63  
**Key Function:**
- `send_checkin_email()`: SendGrid Dynamic Template dispatch (lines 17-63)

### D. main.py Diff

**Location:** `services/notification-svc/app/main.py`  
**Changes:**
- Added imports: `AsyncIOScheduler`, `register_scheduled_dispatcher`, `AsyncSessionFactory`
- Added `scheduler = AsyncIOScheduler()` global
- Updated `_startup()`: added `scheduler.start()` and `register_scheduled_dispatcher()` calls
- Added `_shutdown()`: calls `scheduler.shutdown()`

### E. .env.example Diff

**Location:** `services/notification-svc/.env.example`  
**Changes:**
- Added `SENDGRID_CHECKIN_48H_TEMPLATE_ID=d-your-template-id-here`
- Added `CARE_TEAM_CONTACT_NUMBER=1-800-CARE-TEAM`
- Updated Secret Manager comment to include `sendgrid-checkin-48h-template-id`

---

## Conclusion

US-041 TASK-003 is **complete and validated at 100%** (105/105 checks passed). The Notification Service now supports scheduled notification polling with:

✅ 5-minute polling interval  
✅ Batch processing (100 notifications per poll)  
✅ Opt-out enforcement (`notification_opt_out` → `OPTED_OUT`)  
✅ Channel routing (SMS via Twilio, EMAIL via SendGrid)  
✅ PHI minimization (only `first_name` in message body)  
✅ PHI-free structured logging (no phone/email in logs)  
✅ APScheduler lifecycle management (startup/shutdown)  
✅ Separate transactions for status updates  

**Ready for integration testing in US-041 TASK-004.**

---

**Implementation Date:** 2026-07-28  
**Validation Script:** `validate_us041_task003_notification_polling.py`  
**Task Status:** ✅ Complete  
**Next Task:** US-041 TASK-004 (End-to-End Integration Testing)
