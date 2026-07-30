"""Validation script for US-041 TASK-003: Notification Service Polling & Dispatch.

Checks implementation compliance with task specification and acceptance criteria.

Usage:
    python validate_us041_task003_notification_polling.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Any

# Base paths
REPO_ROOT = Path(__file__).parent
NOTIFICATION_SVC_BASE = REPO_ROOT / "services" / "notification-svc"
APP_DIR = NOTIFICATION_SVC_BASE / "app"


class ValidationResult:
    """Tracks validation check results."""
    
    def __init__(self) -> None:
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []
    
    def check(self, condition: bool, success_msg: str, failure_msg: str) -> None:
        """Record a validation check result."""
        self.total += 1
        if condition:
            self.passed += 1
            print(f"✓ {success_msg}")
        else:
            self.failed += 1
            self.errors.append(failure_msg)
            print(f"✗ {failure_msg}")
    
    def summary(self) -> None:
        """Print validation summary and exit with appropriate code."""
        print("\n" + "=" * 80)
        print(f"Validation Results: {self.passed}/{self.total} checks passed")
        if self.failed > 0:
            print(f"\n{self.failed} checks failed:")
            for error in self.errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print("\n✓ All validation checks passed!")
            print("✓ US-041 TASK-003 implementation is compliant with requirements.")
            sys.exit(0)


def validate_file_structure(result: ValidationResult) -> dict[str, Path]:
    """Category 1: Validate that all required files exist."""
    print("\n" + "=" * 80)
    print("Category 1: File Structure")
    print("=" * 80)
    
    files = {
        "scheduled_dispatcher": APP_DIR / "scheduled_dispatcher.py",
        "sms_service": APP_DIR / "services" / "sms_service.py",
        "email_service": APP_DIR / "services" / "email_service.py",
        "main": APP_DIR / "main.py",
        "env_example": NOTIFICATION_SVC_BASE / ".env.example",
        "services_init": APP_DIR / "services" / "__init__.py",
    }
    
    for name, path in files.items():
        result.check(
            path.exists(),
            f"File exists: {path.relative_to(REPO_ROOT)}",
            f"File missing: {path.relative_to(REPO_ROOT)}",
        )
    
    return files


def validate_scheduled_dispatcher(result: ValidationResult, file_path: Path) -> None:
    """Category 2: Validate scheduled_dispatcher.py implementation."""
    print("\n" + "=" * 80)
    print("Category 2: Scheduled Dispatcher Implementation")
    print("=" * 80)
    
    if not file_path.exists():
        result.check(False, "", "scheduled_dispatcher.py not found")
        return
    
    content = file_path.read_text(encoding="utf-8")
    
    # Check imports
    result.check(
        "from apscheduler.schedulers.asyncio import AsyncIOScheduler" in content,
        "Imports AsyncIOScheduler from apscheduler",
        "Missing: from apscheduler.schedulers.asyncio import AsyncIOScheduler",
    )
    
    result.check(
        "from sqlalchemy import select" in content,
        "Imports select from SQLAlchemy",
        "Missing: from sqlalchemy import select",
    )
    
    result.check(
        "from sqlalchemy.orm import joinedload" in content,
        "Imports joinedload for relationship loading",
        "Missing: from sqlalchemy.orm import joinedload",
    )
    
    # Check constants
    result.check(
        "POLL_INTERVAL_SECONDS" in content and "300" in content,
        "POLL_INTERVAL_SECONDS = 300 (5 minutes)",
        "POLL_INTERVAL_SECONDS not set to 300 seconds",
    )
    
    result.check(
        "POLL_BATCH_LIMIT" in content,
        "POLL_BATCH_LIMIT constant defined",
        "POLL_BATCH_LIMIT constant not found",
    )
    
    # Check dispatch_due_notifications function
    result.check(
        "async def dispatch_due_notifications" in content,
        "dispatch_due_notifications() async function defined",
        "dispatch_due_notifications() function not found",
    )
    
    result.check(
        "session_factory: async_sessionmaker" in content,
        "dispatch_due_notifications accepts session_factory parameter",
        "dispatch_due_notifications missing session_factory parameter",
    )
    
    # Check SQL query components
    result.check(
        "ScheduledNotification.send_at <= now" in content,
        "Query filters by send_at <= now",
        "Query missing send_at <= now condition",
    )
    
    result.check(
        "delivery_status == DeliveryStatus.PENDING" in content,
        "Query filters by delivery_status = PENDING",
        "Query missing delivery_status == PENDING condition",
    )
    
    result.check(
        "deleted_at.is_(None)" in content,
        "Query filters by deleted_at IS NULL",
        "Query missing deleted_at.is_(None) condition",
    )
    
    result.check(
        ".order_by(ScheduledNotification.send_at.asc())" in content,
        "Query orders by send_at ASC",
        "Query missing ORDER BY send_at ASC",
    )
    
    result.check(
        ".limit(POLL_BATCH_LIMIT)" in content,
        "Query limits results to POLL_BATCH_LIMIT",
        "Query missing LIMIT clause",
    )
    
    result.check(
        ".options(joinedload(ScheduledNotification.patient))" in content,
        "Query uses joinedload for patient relationship",
        "Query missing joinedload(ScheduledNotification.patient)",
    )
    
    # Check _process_notification function
    result.check(
        "async def _process_notification" in content,
        "_process_notification() async function defined",
        "_process_notification() function not found",
    )
    
    # Check opt-out enforcement
    result.check(
        "patient.notification_opt_out" in content,
        "Checks patient.notification_opt_out flag",
        "Missing: patient.notification_opt_out check",
    )
    
    result.check(
        "DeliveryStatus.OPTED_OUT" in content,
        "Sets delivery_status to OPTED_OUT for opted-out patients",
        "Missing: DeliveryStatus.OPTED_OUT status",
    )
    
    # Check channel routing
    result.check(
        "NotificationChannel.SMS" in content,
        "Routes SMS notifications via NotificationChannel.SMS",
        "Missing: NotificationChannel.SMS check",
    )
    
    result.check(
        "send_checkin_sms" in content,
        "Calls send_checkin_sms() for SMS dispatch",
        "Missing: send_checkin_sms() call",
    )
    
    result.check(
        "send_checkin_email" in content,
        "Calls send_checkin_email() for email dispatch",
        "Missing: send_checkin_email() call",
    )
    
    # Check status updates
    result.check(
        "DeliveryStatus.SENT" in content,
        "Updates delivery_status to SENT on success",
        "Missing: DeliveryStatus.SENT status",
    )
    
    result.check(
        "DeliveryStatus.FAILED" in content,
        "Updates delivery_status to FAILED on error",
        "Missing: DeliveryStatus.FAILED status",
    )
    
    # Check register_scheduled_dispatcher function
    result.check(
        "def register_scheduled_dispatcher" in content,
        "register_scheduled_dispatcher() function defined",
        "register_scheduled_dispatcher() function not found",
    )
    
    result.check(
        "scheduler.add_job" in content,
        "Registers job with scheduler.add_job()",
        "Missing: scheduler.add_job() call",
    )
    
    result.check(
        'trigger="interval"' in content,
        "Uses interval trigger for periodic polling",
        "Missing: trigger='interval'",
    )
    
    result.check(
        "seconds=POLL_INTERVAL_SECONDS" in content,
        "Sets interval to POLL_INTERVAL_SECONDS",
        "Missing: seconds=POLL_INTERVAL_SECONDS",
    )
    
    result.check(
        "misfire_grace_time" in content,
        "Configures misfire_grace_time for APScheduler",
        "Missing: misfire_grace_time parameter",
    )
    
    # Check PHI handling in logs
    result.check(
        '"scheduled_notification_id"' in content or "'scheduled_notification_id'" in content,
        "Logs scheduled_notification_id (not PHI)",
        "Missing: scheduled_notification_id in log extra",
    )
    
    result.check(
        '"encounter_id"' in content,
        "Logs encounter_id (not PHI)",
        "Missing: encounter_id in logs",
    )
    
    # Verify no PHI in logs (phone/email should not appear in logger calls)
    logger_calls = re.findall(r'logger\.\w+\([^)]+\)', content, re.DOTALL)
    has_phi_in_logs = any(
        "phone" in call or "email" in call or "patient.phone" in call or "patient.email" in call
        for call in logger_calls
    )
    result.check(
        not has_phi_in_logs,
        "No phone/email in structured logs (PHI protected)",
        "PHI VIOLATION: phone or email detected in logger calls",
    )
    
    # Check error handling
    result.check(
        "try:" in content and "except Exception" in content,
        "Exception handling for dispatch errors",
        "Missing: try/except block for dispatch errors",
    )
    
    # Check docstrings
    result.check(
        '"""' in content,
        "Module docstring present",
        "Missing: module docstring",
    )


def validate_sms_service(result: ValidationResult, file_path: Path) -> None:
    """Category 3: Validate sms_service.py implementation."""
    print("\n" + "=" * 80)
    print("Category 3: SMS Service Implementation")
    print("=" * 80)
    
    if not file_path.exists():
        result.check(False, "", "sms_service.py not found")
        return
    
    content = file_path.read_text(encoding="utf-8")
    
    # Check imports
    result.check(
        "from app.core.secrets import get_secret" in content,
        "Imports get_secret for credentials",
        "Missing: from app.core.secrets import get_secret",
    )
    
    # Check function signature
    result.check(
        "async def send_checkin_sms" in content,
        "send_checkin_sms() async function defined",
        "send_checkin_sms() function not found",
    )
    
    result.check(
        "to_phone: str" in content,
        "send_checkin_sms accepts to_phone parameter",
        "Missing: to_phone parameter",
    )
    
    result.check(
        "first_name: str" in content,
        "send_checkin_sms accepts first_name parameter",
        "Missing: first_name parameter",
    )
    
    result.check(
        "care_team_number: str" in content,
        "send_checkin_sms accepts care_team_number parameter",
        "Missing: care_team_number parameter",
    )
    
    # Check Twilio imports and usage
    result.check(
        "from twilio.rest import Client" in content or "TwilioClient" in content,
        "Imports Twilio Client",
        "Missing: Twilio Client import",
    )
    
    result.check(
        'get_secret("twilio-account-sid")' in content,
        "Loads twilio-account-sid from Secret Manager",
        "Missing: get_secret('twilio-account-sid')",
    )
    
    result.check(
        'get_secret("twilio-auth-token")' in content,
        "Loads twilio-auth-token from Secret Manager",
        "Missing: get_secret('twilio-auth-token')",
    )
    
    result.check(
        'get_secret("twilio-from-number")' in content,
        "Loads twilio-from-number from Secret Manager",
        "Missing: get_secret('twilio-from-number')",
    )
    
    # Check message content
    result.check(
        "Hi {first_name}" in content or "f\"Hi {first_name}" in content,
        "Message includes 'Hi {first_name}' greeting",
        "Missing: 'Hi {first_name}' in message body",
    )
    
    result.check(
        "48 hours since your discharge" in content,
        "Message mentions '48 hours since your discharge'",
        "Missing: '48 hours since your discharge' in message",
    )
    
    result.check(
        "How are you feeling" in content,
        "Message asks 'How are you feeling'",
        "Missing: 'How are you feeling' in message",
    )
    
    result.check(
        "{care_team_number}" in content or "f\"{care_team_number}\"" in content,
        "Message includes care_team_number",
        "Missing: care_team_number in message body",
    )
    
    # Check Twilio API call
    result.check(
        "client.messages.create" in content,
        "Calls client.messages.create() to send SMS",
        "Missing: client.messages.create() call",
    )
    
    result.check(
        "body=" in content,
        "Passes body parameter to messages.create()",
        "Missing: body parameter in messages.create()",
    )
    
    result.check(
        "from_=" in content,
        "Passes from_ parameter to messages.create()",
        "Missing: from_ parameter in messages.create()",
    )
    
    result.check(
        "to=" in content,
        "Passes to parameter to messages.create()",
        "Missing: to parameter in messages.create()",
    )


def validate_email_service(result: ValidationResult, file_path: Path) -> None:
    """Category 4: Validate email_service.py implementation."""
    print("\n" + "=" * 80)
    print("Category 4: Email Service Implementation")
    print("=" * 80)
    
    if not file_path.exists():
        result.check(False, "", "email_service.py not found")
        return
    
    content = file_path.read_text(encoding="utf-8")
    
    # Check imports
    result.check(
        "from app.core.secrets import get_secret" in content,
        "Imports get_secret for credentials",
        "Missing: from app.core.secrets import get_secret",
    )
    
    # Check function signature
    result.check(
        "async def send_checkin_email" in content,
        "send_checkin_email() async function defined",
        "send_checkin_email() function not found",
    )
    
    result.check(
        "to_email: str" in content,
        "send_checkin_email accepts to_email parameter",
        "Missing: to_email parameter",
    )
    
    result.check(
        "first_name: str" in content,
        "send_checkin_email accepts first_name parameter",
        "Missing: first_name parameter",
    )
    
    result.check(
        "care_team_number: str" in content,
        "send_checkin_email accepts care_team_number parameter",
        "Missing: care_team_number parameter",
    )
    
    # Check SendGrid imports
    result.check(
        "from sendgrid import SendGridAPIClient" in content,
        "Imports SendGridAPIClient",
        "Missing: from sendgrid import SendGridAPIClient",
    )
    
    result.check(
        "from sendgrid.helpers.mail import Mail" in content or "Mail" in content,
        "Imports Mail from sendgrid.helpers.mail",
        "Missing: Mail import",
    )
    
    result.check(
        "DynamicTemplateData" in content,
        "Uses DynamicTemplateData for template substitutions",
        "Missing: DynamicTemplateData usage",
    )
    
    # Check credentials loading
    result.check(
        'get_secret("sendgrid-api-key")' in content,
        "Loads sendgrid-api-key from Secret Manager",
        "Missing: get_secret('sendgrid-api-key')",
    )
    
    result.check(
        'get_secret("sendgrid-from-email")' in content,
        "Loads sendgrid-from-email from Secret Manager",
        "Missing: get_secret('sendgrid-from-email')",
    )
    
    # Check template ID configuration
    result.check(
        "SENDGRID_CHECKIN_48H_TEMPLATE_ID" in content,
        "References SENDGRID_CHECKIN_48H_TEMPLATE_ID env var",
        "Missing: SENDGRID_CHECKIN_48H_TEMPLATE_ID reference",
    )
    
    result.check(
        "os.environ.get" in content or "get_secret(" in content,
        "Loads template ID from env or Secret Manager",
        "Missing: template ID loading mechanism",
    )
    
    # Check template data substitutions
    result.check(
        '"first_name": first_name' in content or "'first_name': first_name" in content,
        "Passes first_name to DynamicTemplateData",
        "Missing: first_name in template substitutions",
    )
    
    result.check(
        '"care_team_number": care_team_number' in content or "'care_team_number': care_team_number" in content,
        "Passes care_team_number to DynamicTemplateData",
        "Missing: care_team_number in template substitutions",
    )
    
    # Check SendGrid API call
    result.check(
        "message.template_id" in content,
        "Sets template_id on Mail message",
        "Missing: message.template_id assignment",
    )
    
    result.check(
        "message.dynamic_template_data" in content,
        "Sets dynamic_template_data on Mail message",
        "Missing: message.dynamic_template_data assignment",
    )
    
    result.check(
        "sg.send(message)" in content or "sg.send(" in content,
        "Calls sg.send() to dispatch email",
        "Missing: sg.send() call",
    )


def validate_main_modifications(result: ValidationResult, file_path: Path) -> None:
    """Category 5: Validate main.py modifications."""
    print("\n" + "=" * 80)
    print("Category 5: Main.py APScheduler Integration")
    print("=" * 80)
    
    if not file_path.exists():
        result.check(False, "", "main.py not found")
        return
    
    content = file_path.read_text(encoding="utf-8")
    
    # Check imports
    result.check(
        "from apscheduler.schedulers.asyncio import AsyncIOScheduler" in content,
        "Imports AsyncIOScheduler",
        "Missing: from apscheduler.schedulers.asyncio import AsyncIOScheduler",
    )
    
    result.check(
        "from app.scheduled_dispatcher import register_scheduled_dispatcher" in content,
        "Imports register_scheduled_dispatcher",
        "Missing: from app.scheduled_dispatcher import register_scheduled_dispatcher",
    )
    
    result.check(
        "from app.db.session import" in content and "AsyncSessionFactory" in content,
        "Imports AsyncSessionFactory from db.session",
        "Missing: AsyncSessionFactory import",
    )
    
    # Check scheduler initialization
    result.check(
        "scheduler = AsyncIOScheduler()" in content,
        "Creates AsyncIOScheduler instance",
        "Missing: scheduler = AsyncIOScheduler()",
    )
    
    # Check startup event
    result.check(
        "scheduler.start()" in content,
        "Calls scheduler.start() in startup event",
        "Missing: scheduler.start() call",
    )
    
    result.check(
        "register_scheduled_dispatcher(" in content,
        "Calls register_scheduled_dispatcher() in startup",
        "Missing: register_scheduled_dispatcher() call",
    )
    
    result.check(
        "scheduler=scheduler" in content,
        "Passes scheduler to register_scheduled_dispatcher",
        "Missing: scheduler=scheduler argument",
    )
    
    result.check(
        "session_factory=AsyncSessionFactory" in content,
        "Passes AsyncSessionFactory to register_scheduled_dispatcher",
        "Missing: session_factory=AsyncSessionFactory argument",
    )
    
    # Check shutdown event
    result.check(
        '@app.on_event("shutdown")' in content or "async def _shutdown" in content,
        "Defines shutdown event handler",
        "Missing: shutdown event handler",
    )
    
    result.check(
        "scheduler.shutdown()" in content,
        "Calls scheduler.shutdown() on service stop",
        "Missing: scheduler.shutdown() call",
    )


def validate_env_example(result: ValidationResult, file_path: Path) -> None:
    """Category 6: Validate .env.example modifications."""
    print("\n" + "=" * 80)
    print("Category 6: Environment Configuration")
    print("=" * 80)
    
    if not file_path.exists():
        result.check(False, "", ".env.example not found")
        return
    
    content = file_path.read_text(encoding="utf-8")
    
    result.check(
        "SENDGRID_CHECKIN_48H_TEMPLATE_ID" in content,
        ".env.example includes SENDGRID_CHECKIN_48H_TEMPLATE_ID",
        "Missing: SENDGRID_CHECKIN_48H_TEMPLATE_ID in .env.example",
    )
    
    result.check(
        "CARE_TEAM_CONTACT_NUMBER" in content,
        ".env.example includes CARE_TEAM_CONTACT_NUMBER",
        "Missing: CARE_TEAM_CONTACT_NUMBER in .env.example",
    )
    
    result.check(
        "d-your-template-id" in content or "template" in content.lower(),
        "SENDGRID_CHECKIN_48H_TEMPLATE_ID has placeholder value",
        "SENDGRID_CHECKIN_48H_TEMPLATE_ID missing placeholder",
    )
    
    result.check(
        "800" in content or "CARE-TEAM" in content or "care" in content.lower(),
        "CARE_TEAM_CONTACT_NUMBER has placeholder value",
        "CARE_TEAM_CONTACT_NUMBER missing placeholder",
    )


def validate_acceptance_criteria(result: ValidationResult) -> None:
    """Category 7: Validate US-041 TASK-003 Acceptance Criteria."""
    print("\n" + "=" * 80)
    print("Category 7: Acceptance Criteria Compliance")
    print("=" * 80)
    
    # AC 1: scheduled_dispatcher.py exists with dispatch_due_notifications
    dispatcher_path = APP_DIR / "scheduled_dispatcher.py"
    if dispatcher_path.exists():
        content = dispatcher_path.read_text(encoding="utf-8")
        result.check(
            "async def dispatch_due_notifications" in content,
            "AC 1: dispatch_due_notifications() function exists",
            "AC 1 FAILED: dispatch_due_notifications() not found",
        )
    else:
        result.check(False, "", "AC 1 FAILED: scheduled_dispatcher.py not found")
    
    # AC 2: Polling query structure
    if dispatcher_path.exists():
        content = dispatcher_path.read_text(encoding="utf-8")
        has_send_at = "send_at <= now" in content
        has_pending = "PENDING" in content
        has_deleted = "deleted_at" in content
        has_order = "order_by" in content
        has_limit = "limit(" in content
        
        result.check(
            has_send_at and has_pending and has_deleted and has_order and has_limit,
            "AC 2: Polling query has all required clauses (WHERE, ORDER BY, LIMIT)",
            "AC 2 FAILED: Polling query missing required clauses",
        )
    
    # AC 3: APScheduler registration in main.py
    main_path = APP_DIR / "main.py"
    if main_path.exists():
        content = main_path.read_text(encoding="utf-8")
        result.check(
            "scheduler.start()" in content and "register_scheduled_dispatcher" in content,
            "AC 3: APScheduler registered in main.py startup",
            "AC 3 FAILED: APScheduler not properly registered",
        )
    else:
        result.check(False, "", "AC 3 FAILED: main.py not found")
    
    # AC 4: Opt-out enforcement
    if dispatcher_path.exists():
        content = dispatcher_path.read_text(encoding="utf-8")
        result.check(
            "notification_opt_out" in content and "OPTED_OUT" in content,
            "AC 4: Opt-out enforcement implemented (notification_opt_out → OPTED_OUT)",
            "AC 4 FAILED: Opt-out enforcement not found",
        )
    
    # AC 5: Channel routing (SMS vs EMAIL)
    sms_path = APP_DIR / "services" / "sms_service.py"
    email_path = APP_DIR / "services" / "email_service.py"
    result.check(
        sms_path.exists() and email_path.exists(),
        "AC 5: Both SMS and EMAIL dispatch services exist",
        "AC 5 FAILED: Missing SMS or EMAIL service file",
    )
    
    if dispatcher_path.exists():
        content = dispatcher_path.read_text(encoding="utf-8")
        result.check(
            "send_checkin_sms" in content and "send_checkin_email" in content,
            "AC 5: Dispatcher routes to both SMS and EMAIL services",
            "AC 5 FAILED: Dispatcher doesn't route to both channels",
        )
    
    # AC 6: PHI minimization
    if dispatcher_path.exists():
        content = dispatcher_path.read_text(encoding="utf-8")
        logger_calls = re.findall(r'logger\.\w+\([^)]+\)', content, re.DOTALL)
        has_phi = any(
            "phone" in call or "email" in call
            for call in logger_calls
        )
        result.check(
            not has_phi,
            "AC 6: No phone/email in logs (PHI minimization)",
            "AC 6 FAILED: PHI detected in logs",
        )
    
    # AC 7: Message content requirements
    if sms_path.exists():
        content = sms_path.read_text(encoding="utf-8")
        has_first_name = "first_name" in content
        has_48h = "48 hours" in content
        has_care_team = "care_team_number" in content
        
        result.check(
            has_first_name and has_48h and has_care_team,
            "AC 7: SMS message includes first_name, '48 hours', and care_team_number",
            "AC 7 FAILED: SMS message missing required content",
        )
    
    # AC 8: Status updates (SENT, FAILED)
    if dispatcher_path.exists():
        content = dispatcher_path.read_text(encoding="utf-8")
        result.check(
            "SENT" in content and "FAILED" in content,
            "AC 8: Updates delivery_status to SENT or FAILED after dispatch",
            "AC 8 FAILED: Missing SENT or FAILED status updates",
        )


def validate_code_quality(result: ValidationResult) -> None:
    """Category 8: Validate code quality standards."""
    print("\n" + "=" * 80)
    print("Category 8: Code Quality")
    print("=" * 80)
    
    files_to_check = [
        APP_DIR / "scheduled_dispatcher.py",
        APP_DIR / "services" / "sms_service.py",
        APP_DIR / "services" / "email_service.py",
    ]
    
    for file_path in files_to_check:
        if not file_path.exists():
            continue
        
        content = file_path.read_text(encoding="utf-8")
        
        # Check module docstring
        result.check(
            content.startswith('"""') or content.startswith("'''"),
            f"{file_path.name}: Has module docstring",
            f"{file_path.name}: Missing module docstring",
        )
        
        # Check future annotations import
        result.check(
            "from __future__ import annotations" in content,
            f"{file_path.name}: Uses from __future__ import annotations",
            f"{file_path.name}: Missing from __future__ import annotations",
        )
        
        # Check async function definitions have proper typing
        async_funcs = re.findall(r'async def \w+\([^)]*\)', content)
        for func in async_funcs:
            has_types = ":" in func  # Simple check for type hints
            result.check(
                has_types,
                f"{file_path.name}: {func[:30]}... has type hints",
                f"{file_path.name}: {func[:30]}... missing type hints",
            )


def main() -> None:
    """Run all validation checks."""
    print("US-041 TASK-003 Validation: Notification Service Polling & Dispatch")
    print("=" * 80)
    
    result = ValidationResult()
    
    # Category 1: File Structure
    files = validate_file_structure(result)
    
    # Category 2: Scheduled Dispatcher
    validate_scheduled_dispatcher(result, files.get("scheduled_dispatcher"))
    
    # Category 3: SMS Service
    validate_sms_service(result, files.get("sms_service"))
    
    # Category 4: Email Service
    validate_email_service(result, files.get("email_service"))
    
    # Category 5: Main.py Modifications
    validate_main_modifications(result, files.get("main"))
    
    # Category 6: Environment Configuration
    validate_env_example(result, files.get("env_example"))
    
    # Category 7: Acceptance Criteria
    validate_acceptance_criteria(result)
    
    # Category 8: Code Quality
    validate_code_quality(result)
    
    # Print summary and exit
    result.summary()


if __name__ == "__main__":
    main()
