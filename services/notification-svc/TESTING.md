# Notification Service Testing Guide

## Running Integration Tests

### Prerequisites

1. **Pub/Sub Emulator** installed:
   ```bash
   gcloud components install pubsub-emulator
   ```

2. **Test dependencies** installed:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Environment variables** set (copy from `.env.example`):
   ```bash
   cp .env.example .env
   # Edit .env with test values
   ```

### Start Pub/Sub Emulator

In a separate terminal:

```bash
gcloud beta emulators pubsub start --project=test-project
```

In your test terminal, set the emulator environment:

```bash
export PUBSUB_EMULATOR_HOST=localhost:8085
export GCP_PROJECT_ID=test-project
```

### Create Test Topics and Subscriptions

```bash
# Create notification-requests topic
gcloud pubsub topics create notification-requests \
  --project=test-project

# Create subscription
gcloud pubsub subscriptions create notification-service-test-sub \
  --topic=notification-requests \
  --project=test-project

# Create care-team-alerts topic (for failure notifications)
gcloud pubsub topics create care-team-alerts \
  --project=test-project
```

### Run All Tests

```bash
# Run all tests with coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Run only integration tests
pytest tests/integration/ -v -m integration

# Run only unit tests
pytest tests/unit/ -v -m unit

# Run specific test file
pytest tests/integration/test_twilio_webhook.py -v

# Run with detailed output
pytest tests/ -v -s
```

### Test Output Example

```
tests/integration/test_twilio_webhook.py::TestTwilioWebhook::test_missing_signature_returns_403 PASSED
tests/integration/test_twilio_webhook.py::TestTwilioWebhook::test_invalid_signature_returns_403 PASSED
tests/integration/test_twilio_webhook.py::TestTwilioWebhook::test_valid_signature_updates_status_delivered PASSED

---------- coverage: platform linux, python 3.11.5 -----------
Name                                  Stmts   Miss  Cover   Missing
-------------------------------------------------------------------
app/__init__.py                           0      0   100%
app/consumer.py                          45      5    89%   67-71
app/dispatchers/base.py                  15      0   100%
app/dispatchers/email.py                 78      8    90%   142-149
app/dispatchers/sms.py                   82      9    89%   155-163
app/main.py                              12      0   100%
app/schemas.py                           20      0   100%
app/webhooks/twilio.py                   42      3    93%   85-87
-------------------------------------------------------------------
TOTAL                                   294     25    91%
```

### Manual Testing with Emulator

#### 1. Start the Service

```bash
# Terminal 1: Start emulator
gcloud beta emulators pubsub start --project=test-project

# Terminal 2: Start service
export PUBSUB_EMULATOR_HOST=localhost:8085
export GCP_PROJECT_ID=test-project
export DATABASE_URL=postgresql+asyncpg://localhost/test
export SENDGRID_FROM_EMAIL=test@example.com
export TWILIO_FROM_NUMBER=+15555551234

python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

#### 2. Publish Test Messages

```bash
# Terminal 3: Publish test SMS
export PUBSUB_EMULATOR_HOST=localhost:8085

gcloud pubsub topics publish notification-requests \
  --project=test-project \
  --message='{
    "idempotency_key": "TEST-001",
    "type": "SMS",
    "phone": "+15555551234",
    "template": "test_message",
    "substitutions": {"name": "John Doe"}
  }'

# Publish test email
gcloud pubsub topics publish notification-requests \
  --project=test-project \
  --message='{
    "idempotency_key": "TEST-002",
    "type": "EMAIL",
    "email": "test@example.com",
    "template": "d-test-template",
    "substitutions": {"name": "Jane Smith"}
  }'
```

#### 3. Test Webhook Endpoint

```bash
# Test missing signature (should return 403)
curl -X POST http://localhost:8080/webhooks/twilio/status \
  -d 'MessageSid=SM123&MessageStatus=delivered' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -v

# Expected: HTTP 403 Forbidden
```

#### 4. Monitor Logs

Watch service logs in Terminal 2 for:
- `consumer.message_received` — Message pulled from Pub/Sub
- `sms_dispatcher.sent` or `email_dispatcher.sent` — Successful dispatch
- `twilio_webhook.status_updated` — Webhook processed

### Troubleshooting

#### Emulator Not Starting

```bash
# Check if port 8085 is in use
lsof -i :8085

# Kill existing emulator
pkill -f pubsub-emulator
```

#### Import Errors

```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or install in editable mode
pip install -e .
```

#### Database Connection Issues

```bash
# Use SQLite for testing
export DATABASE_URL=sqlite+aiosqlite:///./test.db

# Run Alembic migrations
alembic upgrade head
```

#### Mock External Services

For tests that don't require real API calls, use mocks:

```python
from unittest.mock import patch

# Mock Twilio
with patch('app.dispatchers.sms._build_twilio_client'):
    # Your test code

# Mock SendGrid
with patch('app.dispatchers.email._build_sendgrid_client'):
    # Your test code
```

### CI/CD Integration

Add to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Start Pub/Sub Emulator
  run: |
    gcloud beta emulators pubsub start --project=test-project &
    sleep 5

- name: Run Tests
  env:
    PUBSUB_EMULATOR_HOST: localhost:8085
    GCP_PROJECT_ID: test-project
  run: |
    pytest tests/ --cov=app --cov-report=xml

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

## Load Testing

### Install Locust

```bash
pip install locust
```

### Create Load Test Script

See `tests/load/locustfile.py` for Pub/Sub message publishing scenarios.

### Run Load Test

```bash
locust -f tests/load/locustfile.py --host=http://localhost:8080
```

Open http://localhost:8089 to configure and start load test.

## Performance Benchmarks

Target metrics (US-064 DoD):
- **SMS dispatch latency**: < 2s p95
- **Email dispatch latency**: < 3s p95
- **Webhook processing**: < 500ms p95
- **Throughput**: 100 notifications/second sustained

Monitor with Cloud Monitoring or Prometheus metrics.
