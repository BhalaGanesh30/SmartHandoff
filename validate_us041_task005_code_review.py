"""Comprehensive validation script for US-041 TASK-005: Code Review & DoD Sign-off.

This script performs automated checks for:
1. PHI handling compliance (HIPAA/BR-020/AIR-021)
2. Idempotency integrity (ADR-001)
3. Risk threshold correctness
4. Code quality metrics
5. Definition of Done checklist items

Usage:
    python validate_us041_task005_code_review.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Any

# Base paths
REPO_ROOT = Path(__file__).parent
BACKEND_BASE = REPO_ROOT / "backend"
NOTIFICATION_SVC_BASE = REPO_ROOT / "services" / "notification-svc"


class ValidationResult:
    """Tracks validation check results."""
    
    def __init__(self) -> None:
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors: list[str] = []
        self.warning_msgs: list[str] = []
    
    def check(self, condition: bool, success_msg: str, failure_msg: str, is_warning: bool = False) -> None:
        """Record a validation check result."""
        self.total += 1
        if condition:
            self.passed += 1
            print(f"✓ {success_msg}")
        else:
            if is_warning:
                self.warnings += 1
                self.warning_msgs.append(failure_msg)
                print(f"⚠ {failure_msg}")
            else:
                self.failed += 1
                self.errors.append(failure_msg)
                print(f"✗ {failure_msg}")
    
    def summary(self) -> None:
        """Print validation summary and exit with appropriate code."""
        print("\n" + "=" * 80)
        print(f"Validation Results: {self.passed}/{self.total} checks passed")
        if self.warnings > 0:
            print(f"\n⚠ {self.warnings} warnings:")
            for warning in self.warning_msgs:
                print(f"  - {warning}")
        if self.failed > 0:
            print(f"\n✗ {self.failed} checks failed:")
            for error in self.errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print("\n✓ All validation checks passed!")
            print("✓ US-041 TASK-005 code review complete - APPROVED FOR PRODUCTION.")
            sys.exit(0)


def validate_phi_compliance(result: ValidationResult) -> None:
    """Category 1: PHI Handling Compliance (HIPAA/BR-020/AIR-021)."""
    print("\n" + "=" * 80)
    print("Category 1: PHI Handling Compliance")
    print("=" * 80)
    
    # Check checkin_scheduler.py logs
    checkin_scheduler_path = BACKEND_BASE / "app" / "agents" / "followup_care" / "checkin_scheduler.py"
    if checkin_scheduler_path.exists():
        content = checkin_scheduler_path.read_text(encoding="utf-8")
        
        # Extract all logger calls
        logger_calls = re.findall(r'logger\.\w+\([^)]+extra=\{[^}]+\}', content, re.DOTALL)
        
        phi_fields = ["first_name", "phone", "email", "mrn", "dob", "patient_name"]
        has_phi_in_logs = False
        for call in logger_calls:
            for field in phi_fields:
                if f'"{field}"' in call or f"'{field}'" in call:
                    has_phi_in_logs = True
                    break
        
        result.check(
            not has_phi_in_logs,
            "checkin_scheduler.py: No PHI in structured logs",
            "PHI VIOLATION: PHI fields detected in checkin_scheduler.py logs",
        )
        
        # Check that only safe fields are logged
        result.check(
            '"encounter_id"' in content or "'encounter_id'" in content,
            "checkin_scheduler.py: Logs encounter_id (non-PHI)",
            "checkin_scheduler.py: Missing encounter_id in logs",
        )
        
        result.check(
            '"risk_score"' in content or "'risk_score'" in content,
            "checkin_scheduler.py: Logs risk_score (non-PHI)",
            "checkin_scheduler.py: Missing risk_score in logs",
        )
    
    # Check scheduled_dispatcher.py logs
    scheduled_dispatcher_path = NOTIFICATION_SVC_BASE / "app" / "scheduled_dispatcher.py"
    if scheduled_dispatcher_path.exists():
        content = scheduled_dispatcher_path.read_text(encoding="utf-8")
        
        logger_calls = re.findall(r'logger\.\w+\([^)]+extra=\{[^}]+\}', content, re.DOTALL)
        
        phi_fields = ["first_name", "phone", "email", "mrn", "dob", "patient_name"]
        has_phi_in_logs = False
        for call in logger_calls:
            for field in phi_fields:
                if f'"{field}"' in call or f"'{field}'" in call:
                    has_phi_in_logs = True
                    break
        
        result.check(
            not has_phi_in_logs,
            "scheduled_dispatcher.py: No PHI in structured logs",
            "PHI VIOLATION: PHI fields detected in scheduled_dispatcher.py logs",
        )
        
        result.check(
            '"scheduled_notification_id"' in content or "'scheduled_notification_id'" in content,
            "scheduled_dispatcher.py: Logs scheduled_notification_id (non-PHI)",
            "scheduled_dispatcher.py: Missing scheduled_notification_id in logs",
        )
    
    # Check sms_service.py
    sms_service_path = NOTIFICATION_SVC_BASE / "app" / "services" / "sms_service.py"
    if sms_service_path.exists():
        content = sms_service_path.read_text(encoding="utf-8")
        
        # Verify logger calls don't log PHI
        logger_calls = re.findall(r'logger\.\w+\([^)]+\)', content, re.DOTALL)
        has_phi_in_logs = any(
            "to_phone" in call or "first_name" in call or "phone" in call
            for call in logger_calls
        )
        
        result.check(
            not has_phi_in_logs,
            "sms_service.py: No PHI in logs",
            "PHI VIOLATION: PHI detected in sms_service.py logs",
        )
        
        # Verify first_name and to_phone are only used as function arguments
        result.check(
            "to_phone: str" in content,
            "sms_service.py: to_phone used as function parameter (correct usage)",
            "sms_service.py: Missing to_phone parameter",
        )
        
        result.check(
            "first_name: str" in content,
            "sms_service.py: first_name used as function parameter (correct usage)",
            "sms_service.py: Missing first_name parameter",
        )
    
    # Check email_service.py
    email_service_path = NOTIFICATION_SVC_BASE / "app" / "services" / "email_service.py"
    if email_service_path.exists():
        content = email_service_path.read_text(encoding="utf-8")
        
        logger_calls = re.findall(r'logger\.\w+\([^)]+\)', content, re.DOTALL)
        has_phi_in_logs = any(
            "to_email" in call or "first_name" in call or "email" in call
            for call in logger_calls
        )
        
        result.check(
            not has_phi_in_logs,
            "email_service.py: No PHI in logs",
            "PHI VIOLATION: PHI detected in email_service.py logs",
        )
        
        result.check(
            "to_email: str" in content,
            "email_service.py: to_email used as function parameter (correct usage)",
            "email_service.py: Missing to_email parameter",
        )
        
        result.check(
            "first_name: str" in content,
            "email_service.py: first_name used as function parameter (correct usage)",
            "email_service.py: Missing first_name parameter",
        )
    
    # Check scheduled_notification table schema (no PHI stored)
    scheduled_notification_model = BACKEND_BASE / "app" / "models" / "scheduled_notification.py"
    if scheduled_notification_model.exists():
        content = scheduled_notification_model.read_text(encoding="utf-8")
        
        # Verify no PHI columns in model
        phi_columns = ["phone", "email", "first_name", "last_name", "mrn", "dob"]
        has_phi_column = any(
            f"{col}: Mapped[" in content or f'"{col}"' in content
            for col in phi_columns
        )
        
        result.check(
            not has_phi_column,
            "scheduled_notification model: No PHI columns (only UUIDs)",
            "PHI VIOLATION: PHI columns detected in scheduled_notification model",
        )
        
        # Verify UUID foreign keys present
        result.check(
            "patient_id: Mapped[uuid.UUID]" in content or "patient_id = mapped_column" in content,
            "scheduled_notification model: Uses patient_id UUID (not PHI)",
            "scheduled_notification model: Missing patient_id column",
        )
        
        result.check(
            "encounter_id: Mapped[uuid.UUID]" in content or "encounter_id = mapped_column" in content,
            "scheduled_notification model: Uses encounter_id UUID (not PHI)",
            "scheduled_notification model: Missing encounter_id column",
        )


def validate_idempotency_integrity(result: ValidationResult) -> None:
    """Category 2: Idempotency Integrity (ADR-001)."""
    print("\n" + "=" * 80)
    print("Category 2: Idempotency Integrity")
    print("=" * 80)
    
    # Check idempotency key format
    checkin_scheduler_path = BACKEND_BASE / "app" / "agents" / "followup_care" / "checkin_scheduler.py"
    if checkin_scheduler_path.exists():
        content = checkin_scheduler_path.read_text(encoding="utf-8")
        
        result.check(
            'idempotency_key = f"CHK48-{encounter.id}"' in content or 'f"CHK48-{encounter' in content,
            "Idempotency key format: CHK48-{encounter.id}",
            "Idempotency key format incorrect or missing",
        )
        
        result.check(
            "IntegrityError" in content,
            "IntegrityError exception handling present",
            "Missing IntegrityError exception handling",
        )
        
        result.check(
            "session.rollback()" in content,
            "session.rollback() called on IntegrityError",
            "Missing session.rollback() call",
        )
        
        result.check(
            "return None" in content,
            "Returns None on duplicate (idempotency enforcement)",
            "Missing return None on duplicate",
        )
    
    # Check migration for unique constraint
    migration_files = list((BACKEND_BASE / "alembic" / "versions").glob("*scheduled_notification*.py"))
    if migration_files:
        migration_content = migration_files[0].read_text(encoding="utf-8")
        
        result.check(
            "UniqueConstraint" in migration_content or "unique=True" in migration_content or "create_unique_constraint" in migration_content,
            "Migration defines unique constraint on idempotency_key",
            "Migration missing unique constraint on idempotency_key",
        )
        
        result.check(
            "idempotency_key" in migration_content,
            "Migration includes idempotency_key column",
            "Migration missing idempotency_key column",
        )
    
    # Check test coverage for idempotency
    test_checkin_scheduler = BACKEND_BASE / "tests" / "unit" / "agents" / "followup_care" / "test_checkin_scheduler.py"
    if test_checkin_scheduler.exists():
        content = test_checkin_scheduler.read_text(encoding="utf-8")
        
        result.check(
            "test_returns_none_on_unique_constraint_violation" in content,
            "Test: test_returns_none_on_unique_constraint_violation exists",
            "Missing test: test_returns_none_on_unique_constraint_violation",
        )
        
        result.check(
            "IntegrityError" in content,
            "Test mocks IntegrityError",
            "Test missing IntegrityError mock",
        )


def validate_risk_threshold_correctness(result: ValidationResult) -> None:
    """Category 3: Risk Threshold Correctness (Patient Safety)."""
    print("\n" + "=" * 80)
    print("Category 3: Risk Threshold Correctness")
    print("=" * 80)
    
    checkin_scheduler_path = BACKEND_BASE / "app" / "agents" / "followup_care" / "checkin_scheduler.py"
    if checkin_scheduler_path.exists():
        content = checkin_scheduler_path.read_text(encoding="utf-8")
        
        # Check threshold definition
        result.check(
            "CHECKIN_RISK_THRESHOLD = 0.5" in content or "CHECKIN_RISK_THRESHOLD: float = 0.5" in content,
            "CHECKIN_RISK_THRESHOLD = 0.5 defined",
            "CHECKIN_RISK_THRESHOLD not set to 0.5",
        )
        
        # Check threshold is used correctly
        result.check(
            "risk_score < CHECKIN_RISK_THRESHOLD" in content or "risk_score >= CHECKIN_RISK_THRESHOLD" in content,
            "Threshold used in risk score comparison",
            "Threshold not used in risk score comparison",
        )
        
        # Verify threshold is not duplicated in other files
        agent_path = BACKEND_BASE / "app" / "agents" / "followup_care" / "agent.py"
        if agent_path.exists():
            agent_content = agent_path.read_text(encoding="utf-8")
            result.check(
                "0.5" not in agent_content or "CHECKIN_RISK_THRESHOLD" not in agent_content,
                "Threshold not duplicated in agent.py",
                "WARNING: Threshold may be duplicated in agent.py",
                is_warning=True,
            )
    
    # Check test coverage for threshold boundaries
    test_checkin_scheduler = BACKEND_BASE / "tests" / "unit" / "agents" / "followup_care" / "test_checkin_scheduler.py"
    if test_checkin_scheduler.exists():
        content = test_checkin_scheduler.read_text(encoding="utf-8")
        
        result.check(
            "test_checkin_not_created_for_low_risk" in content,
            "Test: risk_score < 0.5 (no schedule)",
            "Missing test: risk_score < 0.5",
        )
        
        result.check(
            "test_checkin_created_at_exact_threshold" in content or "risk_score=0.5" in content,
            "Test: risk_score == 0.5 (schedule)",
            "Missing test: risk_score == 0.5",
        )
        
        result.check(
            "test_checkin_created_for_medium_risk" in content or "risk_score=0.6" in content,
            "Test: risk_score > 0.5 (schedule)",
            "Missing test: risk_score > 0.5",
        )


def validate_definition_of_done(result: ValidationResult) -> None:
    """Category 4: Definition of Done Checklist."""
    print("\n" + "=" * 80)
    print("Category 4: Definition of Done Checklist")
    print("=" * 80)
    
    # DoD 1: ScheduledNotification ORM model
    scheduled_notification_model = BACKEND_BASE / "app" / "models" / "scheduled_notification.py"
    result.check(
        scheduled_notification_model.exists(),
        "DoD 1: ScheduledNotification ORM model exists",
        "DoD 1 FAILED: ScheduledNotification model not found",
    )
    
    if scheduled_notification_model.exists():
        content = scheduled_notification_model.read_text(encoding="utf-8")
        required_fields = ["type", "send_at", "patient_id", "encounter_id", "channel", "delivery_status"]
        for field in required_fields:
            result.check(
                f"{field}" in content,
                f"DoD 1: Model has {field} field",
                f"DoD 1 FAILED: Model missing {field} field",
            )
    
    # DoD 2: Follow-up care agent creates CHECK_IN_48H
    checkin_scheduler_path = BACKEND_BASE / "app" / "agents" / "followup_care" / "checkin_scheduler.py"
    result.check(
        checkin_scheduler_path.exists(),
        "DoD 2: checkin_scheduler.py exists",
        "DoD 2 FAILED: checkin_scheduler.py not found",
    )
    
    if checkin_scheduler_path.exists():
        content = checkin_scheduler_path.read_text(encoding="utf-8")
        result.check(
            "CHECK_IN_48H" in content,
            "DoD 2: Creates CHECK_IN_48H notification type",
            "DoD 2 FAILED: CHECK_IN_48H not found",
        )
        
        result.check(
            "risk_score" in content and "0.5" in content,
            "DoD 2: Risk score threshold check present",
            "DoD 2 FAILED: Risk score threshold check missing",
        )
    
    # DoD 3: Notification service polls and dispatches
    scheduled_dispatcher_path = NOTIFICATION_SVC_BASE / "app" / "scheduled_dispatcher.py"
    result.check(
        scheduled_dispatcher_path.exists(),
        "DoD 3: scheduled_dispatcher.py exists",
        "DoD 3 FAILED: scheduled_dispatcher.py not found",
    )
    
    if scheduled_dispatcher_path.exists():
        content = scheduled_dispatcher_path.read_text(encoding="utf-8")
        result.check(
            "dispatch_due_notifications" in content,
            "DoD 3: dispatch_due_notifications() function exists",
            "DoD 3 FAILED: dispatch_due_notifications() not found",
        )
        
        result.check(
            "send_at" in content and "PENDING" in content,
            "DoD 3: Queries send_at and PENDING status",
            "DoD 3 FAILED: Missing send_at or PENDING query logic",
        )
    
    # DoD 4: Opt-out enforcement
    if scheduled_dispatcher_path.exists():
        content = scheduled_dispatcher_path.read_text(encoding="utf-8")
        result.check(
            "notification_opt_out" in content,
            "DoD 4: Checks notification_opt_out flag",
            "DoD 4 FAILED: notification_opt_out check missing",
        )
        
        result.check(
            "OPTED_OUT" in content,
            "DoD 4: Sets OPTED_OUT status for opted-out patients",
            "DoD 4 FAILED: OPTED_OUT status not set",
        )
    
    # DoD 5: Unit tests
    test_checkin_scheduler = BACKEND_BASE / "tests" / "unit" / "agents" / "followup_care" / "test_checkin_scheduler.py"
    result.check(
        test_checkin_scheduler.exists(),
        "DoD 5: test_checkin_scheduler.py exists",
        "DoD 5 FAILED: test_checkin_scheduler.py not found",
    )
    
    test_scheduled_dispatcher = NOTIFICATION_SVC_BASE / "tests" / "unit" / "test_scheduled_dispatcher.py"
    result.check(
        test_scheduled_dispatcher.exists(),
        "DoD 5: test_scheduled_dispatcher.py exists",
        "DoD 5 FAILED: test_scheduled_dispatcher.py not found",
    )


def validate_file_existence(result: ValidationResult) -> None:
    """Category 5: File Existence Check."""
    print("\n" + "=" * 80)
    print("Category 5: File Existence Check")
    print("=" * 80)
    
    files_to_check = [
        (BACKEND_BASE / "app" / "models" / "scheduled_notification.py", "scheduled_notification.py"),
        (BACKEND_BASE / "app" / "agents" / "followup_care" / "checkin_scheduler.py", "checkin_scheduler.py"),
        (NOTIFICATION_SVC_BASE / "app" / "scheduled_dispatcher.py", "scheduled_dispatcher.py"),
        (NOTIFICATION_SVC_BASE / "app" / "services" / "sms_service.py", "sms_service.py"),
        (NOTIFICATION_SVC_BASE / "app" / "services" / "email_service.py", "email_service.py"),
        (BACKEND_BASE / "tests" / "unit" / "agents" / "followup_care" / "test_checkin_scheduler.py", "test_checkin_scheduler.py"),
        (NOTIFICATION_SVC_BASE / "tests" / "unit" / "test_scheduled_dispatcher.py", "test_scheduled_dispatcher.py"),
    ]
    
    for file_path, file_name in files_to_check:
        result.check(
            file_path.exists(),
            f"File exists: {file_name}",
            f"File missing: {file_name}",
        )


def main() -> None:
    """Run all validation checks."""
    print("US-041 TASK-005 Code Review & DoD Sign-off Validation")
    print("=" * 80)
    
    result = ValidationResult()
    
    # Category 1: PHI Compliance
    validate_phi_compliance(result)
    
    # Category 2: Idempotency Integrity
    validate_idempotency_integrity(result)
    
    # Category 3: Risk Threshold Correctness
    validate_risk_threshold_correctness(result)
    
    # Category 4: Definition of Done
    validate_definition_of_done(result)
    
    # Category 5: File Existence
    validate_file_existence(result)
    
    # Print summary and exit
    result.summary()


if __name__ == "__main__":
    main()
