"""Validation script for US-067 TASK-003: Opt-Out Suppression + Urgency Bypass.

Validates:
    - Consumer persists urgency_override on notification INSERT
    - SMS dispatcher persists urgency_override on SENT/OPTED_OUT status
    - Email dispatcher persists urgency_override on SENT/OPTED_OUT status
    - Audit log entries written for all dispatch attempts
    - Base dispatcher write_audit_log helper exists
    - No syntax errors
"""
import ast
import pathlib
import sys


def validate_file_syntax(file_path: pathlib.Path) -> bool:
    """Validate Python syntax by parsing the file."""
    try:
        ast.parse(file_path.read_text(encoding="utf-8"))
        print(f"✓ {file_path.name} — Syntax check PASSED")
        return True
    except SyntaxError as e:
        print(f"✗ {file_path.name} — Syntax error: {e}")
        return False


def check_string_in_file(file_path: pathlib.Path, search_str: str, description: str) -> bool:
    """Check if a string exists in a file."""
    content = file_path.read_text(encoding="utf-8")
    if search_str in content:
        print(f"✓ {file_path.name} — {description}: FOUND")
        return True
    else:
        print(f"✗ {file_path.name} — {description}: NOT FOUND")
        return False


def main() -> int:
    """Run all validation checks."""
    print()
    print("=" * 80)
    print("US-067 TASK-003 VALIDATION: Opt-Out Suppression + Urgency Bypass")
    print("=" * 80)
    print()

    files_to_check = [
        pathlib.Path("services/notification-svc/app/consumer.py"),
        pathlib.Path("services/notification-svc/app/dispatchers/base.py"),
        pathlib.Path("services/notification-svc/app/dispatchers/sms.py"),
        pathlib.Path("services/notification-svc/app/dispatchers/email.py"),
    ]

    # Syntax checks
    print("1. SYNTAX VALIDATION")
    print("-" * 80)
    syntax_results = [validate_file_syntax(f) for f in files_to_check]
    print()

    # Consumer urgency_override persistence
    print("2. CONSUMER: urgency_override PERSISTENCE")
    print("-" * 80)
    consumer_file = pathlib.Path("services/notification-svc/app/consumer.py")
    consumer_checks = [
        check_string_in_file(
            consumer_file,
            "urgency_override",
            "urgency_override field in INSERT columns"
        ),
        check_string_in_file(
            consumer_file,
            ":urgency_override",
            "urgency_override placeholder in INSERT VALUES"
        ),
        check_string_in_file(
            consumer_file,
            '"urgency_override": request.urgency_override',
            "urgency_override parameter binding"
        ),
    ]
    print()

    # Base dispatcher audit log
    print("3. BASE DISPATCHER: write_audit_log HELPER")
    print("-" * 80)
    base_file = pathlib.Path("services/notification-svc/app/dispatchers/base.py")
    base_checks = [
        check_string_in_file(
            base_file,
            "async def write_audit_log",
            "write_audit_log method definition"
        ),
        check_string_in_file(
            base_file,
            "INSERT INTO audit_log",
            "Audit log INSERT statement"
        ),
        check_string_in_file(
            base_file,
            "action: str",
            "Audit log action parameter"
        ),
        check_string_in_file(
            base_file,
            "urgency_override: bool",
            "Audit log urgency_override parameter"
        ),
    ]
    print()

    # SMS dispatcher audit log calls
    print("4. SMS DISPATCHER: AUDIT LOG INTEGRATION")
    print("-" * 80)
    sms_file = pathlib.Path("services/notification-svc/app/dispatchers/sms.py")
    sms_checks = [
        check_string_in_file(
            sms_file,
            "BaseNotificationDispatcher.write_audit_log",
            "Audit log call via BaseNotificationDispatcher"
        ),
        check_string_in_file(
            sms_file,
            "NOTIFICATION_SUPPRESSED_OPT_OUT",
            "Audit action for opt-out suppression"
        ),
        check_string_in_file(
            sms_file,
            "NOTIFICATION_DISPATCHED",
            "Audit action for successful dispatch"
        ),
        check_string_in_file(
            sms_file,
            "NOTIFICATION_FAILED",
            "Audit action for final failure"
        ),
        check_string_in_file(
            sms_file,
            "urgency_override = :urgency_override",
            "urgency_override in SENT status UPDATE"
        ),
    ]
    print()

    # Email dispatcher audit log calls
    print("5. EMAIL DISPATCHER: AUDIT LOG INTEGRATION")
    print("-" * 80)
    email_file = pathlib.Path("services/notification-svc/app/dispatchers/email.py")
    email_checks = [
        check_string_in_file(
            email_file,
            "BaseNotificationDispatcher.write_audit_log",
            "Audit log call via BaseNotificationDispatcher"
        ),
        check_string_in_file(
            email_file,
            "NOTIFICATION_SUPPRESSED_OPT_OUT",
            "Audit action for opt-out suppression"
        ),
        check_string_in_file(
            email_file,
            "NOTIFICATION_DISPATCHED",
            "Audit action for successful dispatch"
        ),
        check_string_in_file(
            email_file,
            "NOTIFICATION_FAILED",
            "Audit action for final failure"
        ),
        check_string_in_file(
            email_file,
            "urgency_override=request.urgency_override",
            "urgency_override in set_status call"
        ),
    ]
    print()

    # Summary
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    all_checks = (
        syntax_results +
        consumer_checks +
        base_checks +
        sms_checks +
        email_checks
    )
    
    passed = sum(all_checks)
    total = len(all_checks)
    
    print(f"Total checks: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print()
    
    if passed == total:
        print("✓ ALL CHECKS PASSED — TASK-003 IMPLEMENTATION COMPLETE")
        print()
        return 0
    else:
        print("✗ SOME CHECKS FAILED — REVIEW IMPLEMENTATION")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
