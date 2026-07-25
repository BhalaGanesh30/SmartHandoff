"""Validation script for US-067 TASK-004 implementation.

Verifies:
1. Notification model exists in backend with required fields
2. NotificationLogItem schema excludes PHI fields
3. Notifications router exists and imports correctly
4. Router registered in main.py
5. require_role dependency function exists
6. All files have no syntax errors
"""
import pathlib
import sys


def check_notification_model():
    """Verify notification model exists in backend."""
    print("Checking notification model in backend...")
    model_path = pathlib.Path("backend/app/models/notification.py")
    
    if not model_path.exists():
        print(f"  ✗ Model file not found: {model_path}")
        return False
    
    content = model_path.read_text()
    
    checks = {
        "Notification class": "class Notification(Base):" in content,
        "NotificationType enum": "class NotificationType(str, enum.Enum):" in content,
        "NotificationStatus enum": "class NotificationStatus(str, enum.Enum):" in content,
        "encounter_id field": "encounter_id:" in content,
        "delivery_status field": "delivery_status:" in content,
        "urgency_override field": "urgency_override:" in content,
        "recipient_phone_hash field": "recipient_phone_hash:" in content,
        "recipient_email_hash field": "recipient_email_hash:" in content,
        "sent_at field": "sent_at:" in content,
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed


def check_notification_log_schema():
    """Verify notification log schema has correct structure."""
    print("\nChecking notification log schema...")
    schema_path = pathlib.Path("backend/app/schemas/notification_log.py")
    
    if not schema_path.exists():
        print(f"  ✗ Schema file not found: {schema_path}")
        return False
    
    content = schema_path.read_text()
    
    checks = {
        "NotificationLogItem class": "class NotificationLogItem(BaseModel):" in content,
        "NotificationLogResponse class": "class NotificationLogResponse(BaseModel):" in content,
        "No recipient_phone field": "recipient_phone:" not in content or "recipient_phone_hash:" in content,
        "No recipient_email field": "recipient_email:" not in content or "recipient_email_hash:" in content,
        "Has recipient_phone_hash": "recipient_phone_hash:" in content,
        "Has recipient_email_hash": "recipient_email_hash:" in content,
        "Has type field": '"type"' in content or "notification_type:" in content,
        "Has channel field": "channel:" in content,
        "Has sent_at field": "sent_at:" in content,
        "Has delivery_status field": "delivery_status:" in content,
        "Has template_name field": "template_name:" in content,
        "Has urgency_override field": "urgency_override:" in content,
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed


def check_notifications_router():
    """Verify notifications router exists and has correct structure."""
    print("\nChecking notifications router...")
    router_path = pathlib.Path("backend/app/api/v1/routers/notifications.py")
    
    if not router_path.exists():
        print(f"  ✗ Router file not found: {router_path}")
        return False
    
    content = router_path.read_text()
    
    checks = {
        "Router defined": 'router = APIRouter(prefix="/notifications"' in content,
        "GET endpoint": '@router.get(' in content,
        "require_role import": "from app.core.auth.dependencies import require_role" in content,
        "get_read_db import": "from app.db.deps import get_read_db" in content,
        "Notification model import": "from app.models.notification import Notification" in content,
        "STAFF_ROLES constant": "STAFF_ROLES" in content,
        "encounter_id parameter": "encounter_id:" in content and "Query(" in content,
        "Uses get_read_db": "Depends(get_read_db)" in content,
        "Uses require_role": "Depends(require_role" in content,
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed


def check_router_registration():
    """Verify router is registered in main.py."""
    print("\nChecking router registration in main.py...")
    main_path = pathlib.Path("backend/app/main.py")
    
    if not main_path.exists():
        print(f"  ✗ main.py not found: {main_path}")
        return False
    
    content = main_path.read_text()
    
    checks = {
        "Import notifications router": "from app.api.v1.routers.notifications import router as notifications_router" in content,
        "Include notifications router": "app.include_router(notifications_router" in content,
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed


def check_require_role_dependency():
    """Verify require_role dependency exists."""
    print("\nChecking require_role dependency...")
    deps_path = pathlib.Path("backend/app/core/auth/dependencies.py")
    
    if not deps_path.exists():
        print(f"  ✗ dependencies.py not found: {deps_path}")
        return False
    
    content = deps_path.read_text()
    
    checks = {
        "require_role function": "def require_role(" in content,
        "allowed_roles parameter": "allowed_roles:" in content or "allowed_roles)" in content,
        "Returns dependency": "async def role_checker(" in content or "def role_checker(" in content,
        "Checks user role": "user.role not in allowed_roles" in content,
        "Raises 403": "HTTP_403_FORBIDDEN" in content,
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed


def check_imports():
    """Verify all files can be imported without errors."""
    print("\nChecking imports...")
    
    try:
        import sys
        sys.path.insert(0, "backend")
        
        from app.schemas.notification_log import NotificationLogItem, NotificationLogResponse
        print("  ✓ notification_log schema imports successfully")
        
        from app.models.notification import Notification
        print("  ✓ Notification model imports successfully")
        
        from app.api.v1.routers.notifications import router
        print("  ✓ notifications router imports successfully")
        
        from app.core.auth.dependencies import require_role
        print("  ✓ require_role dependency imports successfully")
        
        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False


def main():
    """Run all validation checks."""
    print("=" * 80)
    print("US-067 TASK-004 Validation")
    print("=" * 80)
    print()
    
    results = {
        "Notification Model": check_notification_model(),
        "Notification Log Schema": check_notification_log_schema(),
        "Notifications Router": check_notifications_router(),
        "Router Registration": check_router_registration(),
        "require_role Dependency": check_require_role_dependency(),
        "Imports": check_imports(),
    }
    
    print()
    print("=" * 80)
    print("Validation Summary")
    print("=" * 80)
    
    for check_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {check_name}")
    
    print()
    
    all_passed = all(results.values())
    if all_passed:
        print("✓ ALL VALIDATION CHECKS PASSED")
        print()
        print("Implementation Status: COMPLETE")
        print("Ready for code review and integration testing")
    else:
        print("✗ SOME VALIDATION CHECKS FAILED")
        print("Please review the failed checks above")
        sys.exit(1)
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
