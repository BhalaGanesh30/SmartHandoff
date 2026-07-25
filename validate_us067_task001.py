"""Validation script for US-067 TASK-001 implementation.

Verifies:
1. Notification model has urgency_override field and delivery_status (renamed from status)
2. NotificationStatus enum includes OPTED_OUT
3. Patient model has notification_opt_out field
4. Alembic migrations exist for both changes
5. All code references updated from status to delivery_status
"""
import pathlib
import sys


def check_notification_model():
    """Verify notification model has required changes."""
    print("Checking notification model...")
    model_path = pathlib.Path(
        "services/notification-svc/app/models/notification.py"
    )
    
    if not model_path.exists():
        print(f"  ✗ Model file not found: {model_path}")
        return False
    
    content = model_path.read_text()
    
    checks = {
        "urgency_override field": "urgency_override: Mapped[bool]" in content,
        "delivery_status field": "delivery_status: Mapped[NotificationStatus]" in content,
        "OPTED_OUT enum value": 'OPTED_OUT = "OPTED_OUT"' in content,
        "No old status field": "    status: Mapped[NotificationStatus] = mapped_column(" not in content,
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed


def check_patient_model():
    """Verify patient model has notification_opt_out field."""
    print("\nChecking patient model...")
    model_path = pathlib.Path("backend/app/models/patient.py")
    
    if not model_path.exists():
        print(f"  ✗ Model file not found: {model_path}")
        return False
    
    content = model_path.read_text()
    
    checks = {
        "notification_opt_out field": "notification_opt_out: Mapped[bool]" in content,
        "US-067 comment": "US-067" in content and "notification_opt_out" in content,
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed


def check_migrations():
    """Verify migration files exist."""
    print("\nChecking migration files...")
    
    notification_migration = pathlib.Path(
        "services/notification-svc/app/migrations/versions/"
        "0002_us067_add_urgency_override_rename_status.py"
    )
    
    patient_migration = pathlib.Path(
        "backend/alembic/versions/"
        "j4g7f0b35e49_add_notification_opt_out_to_patient.py"
    )
    
    checks = {
        "Notification migration exists": notification_migration.exists(),
        "Patient migration exists": patient_migration.exists(),
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    # Check migration content
    if notification_migration.exists():
        content = notification_migration.read_text()
        upgrade_checks = {
            "Renames status to delivery_status": 'new_column_name="delivery_status"' in content,
            "Adds urgency_override": '"urgency_override"' in content,
            "Revision ID is 0002": 'revision: str = "0002"' in content,
        }
        
        for check_name, passed in upgrade_checks.items():
            status = "✓" if passed else "✗"
            print(f"    {status} {check_name}")
            if not passed:
                all_passed = False
    
    if patient_migration.exists():
        content = patient_migration.read_text()
        upgrade_checks = {
            "Adds notification_opt_out": '"notification_opt_out"' in content,
            "Has US-067 reference": "US-067" in content,
        }
        
        for check_name, passed in upgrade_checks.items():
            status = "✓" if passed else "✗"
            print(f"    {status} {check_name}")
            if not passed:
                all_passed = False
    
    return all_passed


def check_code_updates():
    """Verify code references updated from status to delivery_status."""
    print("\nChecking code references...")
    
    files_to_check = [
        "services/notification-svc/app/dispatchers/base.py",
        "services/notification-svc/app/dispatchers/sms.py",
        "services/notification-svc/app/webhooks/twilio.py",
        "services/notification-svc/tests/unit/test_opt_out.py",
        "services/notification-svc/tests/unit/test_sms_retry.py",
        "services/notification-svc/tests/unit/test_webhook_validation.py",
    ]
    
    all_passed = True
    for file_path_str in files_to_check:
        file_path = pathlib.Path(file_path_str)
        if not file_path.exists():
            print(f"  ✗ File not found: {file_path}")
            all_passed = False
            continue
        
        content = file_path.read_text()
        
        # Check for old status references (excluding response.status_code which is OK)
        has_old_ref = (
            "notification.status" in content or
            "row.status " in content or
            'status="' in content and "delivery_status" not in content
        )
        
        has_new_ref = "delivery_status" in content
        
        if has_old_ref and not has_new_ref:
            print(f"  ✗ {file_path.name}: Still has old 'status' references")
            all_passed = False
        elif has_new_ref:
            print(f"  ✓ {file_path.name}: Uses 'delivery_status'")
        else:
            print(f"  ~ {file_path.name}: No status references")
    
    return all_passed


def main():
    """Run all validation checks."""
    print("=" * 80)
    print("US-067 TASK-001 Implementation Validation")
    print("=" * 80)
    print()
    
    results = {
        "Notification Model": check_notification_model(),
        "Patient Model": check_patient_model(),
        "Migration Files": check_migrations(),
        "Code Updates": check_code_updates(),
    }
    
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✓ ALL CHECKS PASSED")
        print("\nNext steps:")
        print("  1. Review the changes with: git diff")
        print("  2. Run migrations locally (requires PostgreSQL):")
        print("     cd services/notification-svc && alembic upgrade head")
        print("     cd backend && alembic upgrade head")
        print("  3. Run unit tests:")
        print("     cd services/notification-svc && pytest tests/unit/ -v")
        print()
        return 0
    else:
        print("✗ SOME CHECKS FAILED - Review the output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
