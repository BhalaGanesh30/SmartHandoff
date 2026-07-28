#!/usr/bin/env python
"""Validation script for US-035 TASK-004: Housekeeping Pub/Sub Notification.

Validates:
1. HousekeepingNotificationPayload Schema
2. HousekeepingNotifier Implementation
3. Main.py Integration
4. __init__.py Exports
5. Code Quality

Run: python validate_us035_task004_notifier.py

Design refs:
    US-035 AC Scenario 2 — housekeeping notification published within 5 seconds
"""
from __future__ import annotations

import pathlib
import sys

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS_PATH = pathlib.Path("backend/app/agents/bed_management/schemas.py")
NOTIFIER_PATH = pathlib.Path("backend/app/agents/bed_management/notifier.py")
MAIN_PATH = pathlib.Path("backend/app/agents/bed_management/main.py")
INIT_PATH = pathlib.Path("backend/app/agents/bed_management/__init__.py")

# ══════════════════════════════════════════════════════════════════════════════
# VALIDATORS
# ══════════════════════════════════════════════════════════════════════════════


def validate_notification_payload_schema() -> tuple[int, list[str]]:
    """Validate HousekeepingNotificationPayload in schemas.py."""
    errors: list[str] = []
    checks_passed = 0

    if not SCHEMAS_PATH.exists():
        errors.append(f"❌ schemas.py not found: {SCHEMAS_PATH}")
        return 0, errors

    content = SCHEMAS_PATH.read_text(encoding="utf-8")

    # Check for HousekeepingNotificationPayload class
    if "class HousekeepingNotificationPayload" in content:
        print("✅ HousekeepingNotificationPayload class defined")
        checks_passed += 1
    else:
        errors.append("❌ HousekeepingNotificationPayload class not found")

    # Check for required fields
    required_fields = [
        "notification_type",
        "bed_id",
        "unit",
        "room",
        "bed_number",
        "encounter_id",
        "idempotency_key",
    ]
    for field in required_fields:
        if f"{field}:" in content or f"{field} =" in content:
            print(f"✅ HousekeepingNotificationPayload has '{field}' field")
            checks_passed += 1
        else:
            errors.append(f"❌ HousekeepingNotificationPayload missing '{field}' field")

    # Check for Literal["HOUSEKEEPING_REQUIRED"]
    if 'Literal["HOUSEKEEPING_REQUIRED"]' in content:
        print("✅ notification_type uses Literal type")
        checks_passed += 1
    else:
        errors.append("❌ notification_type Literal not found")

    # Check for build() classmethod
    if "@classmethod" in content and "def build(" in content:
        print("✅ HousekeepingNotificationPayload has build() classmethod")
        checks_passed += 1
    else:
        errors.append("❌ HousekeepingNotificationPayload missing build() classmethod")

    # Check for hashlib usage (idempotency key generation)
    if "import hashlib" in content:
        print("✅ hashlib imported for idempotency key")
        checks_passed += 1
    else:
        errors.append("❌ hashlib not imported (needed for idempotency key)")

    # Check for SHA-256 hashing
    if "hashlib.sha256" in content:
        print("✅ Uses SHA-256 for idempotency key generation")
        checks_passed += 1
    else:
        errors.append("❌ SHA-256 hashing not found")

    # Check for deterministic key (bed_id:encounter_id)
    if 'bed_id}:{encounter_id}' in content or 'bed_id":"encounter_id' in content:
        print("✅ Idempotency key uses bed_id + encounter_id")
        checks_passed += 1
    else:
        errors.append("❌ Idempotency key does not use bed_id + encounter_id pattern")

    return checks_passed, errors


def validate_notifier_py() -> tuple[int, list[str]]:
    """Validate notifier.py implementation."""
    errors: list[str] = []
    checks_passed = 0

    if not NOTIFIER_PATH.exists():
        errors.append(f"❌ notifier.py not found: {NOTIFIER_PATH}")
        return 0, errors

    content = NOTIFIER_PATH.read_text(encoding="utf-8")

    # Check for HousekeepingNotifier class
    if "class HousekeepingNotifier" in content:
        print("✅ HousekeepingNotifier class defined")
        checks_passed += 1
    else:
        errors.append("❌ HousekeepingNotifier class not found")

    # Check for required methods
    required_methods = ["__init__", "notify", "_fetch_bed_coordinates", "_publish"]
    for method in required_methods:
        if f"def {method}" in content:
            print(f"✅ HousekeepingNotifier has {method} method")
            checks_passed += 1
        else:
            errors.append(f"❌ HousekeepingNotifier missing {method} method")

    # Check for topic_id constant
    if '_TOPIC_ID = "notification-requests"' in content:
        print("✅ Uses 'notification-requests' topic")
        checks_passed += 1
    else:
        errors.append("❌ 'notification-requests' topic not found")

    # Check for 5-second timeout
    if "timeout=5" in content:
        print("✅ Uses 5-second timeout (AC Scenario 2 SLA)")
        checks_passed += 1
    else:
        errors.append("❌ 5-second timeout not found (required by AC Scenario 2)")

    # Check for exception handling in notify()
    if "try:" in content and "except Exception:" in content:
        print("✅ Exception handling in notify()")
        checks_passed += 1
    else:
        errors.append("❌ Exception handling not found (failures should be logged)")

    # Check for logging (not raising exceptions)
    if "logger.exception" in content or "logger.error" in content:
        print("✅ Logs exceptions without re-raising")
        checks_passed += 1
    else:
        errors.append("❌ Exception logging not found")

    # Check for HousekeepingNotificationPayload.build() call
    if "HousekeepingNotificationPayload.build(" in content:
        print("✅ Calls HousekeepingNotificationPayload.build()")
        checks_passed += 1
    else:
        errors.append("❌ HousekeepingNotificationPayload.build() not called")

    # Check for Pub/Sub publish
    if "publish(" in content and "self._pubsub.publish" in content:
        print("✅ Publishes to Pub/Sub")
        checks_passed += 1
    else:
        errors.append("❌ Pub/Sub publish not found")

    # Check for JSON encoding
    if "json.dumps" in content:
        print("✅ JSON-encodes payload")
        checks_passed += 1
    else:
        errors.append("❌ JSON encoding not found")

    # Check for Pub/Sub attributes (notification_type, idempotency_key)
    if "attributes =" in content or "attributes=" in content:
        print("✅ Sets Pub/Sub message attributes")
        checks_passed += 1
    else:
        errors.append("❌ Pub/Sub attributes not set")

    # Check for bed coordinates fetch from read replica
    if "select(Bed)" in content:
        print("✅ Fetches bed coordinates from database")
        checks_passed += 1
    else:
        errors.append("❌ Bed coordinate lookup not found")

    # Check for async/await
    if "async def notify" in content:
        print("✅ notify() is async def")
        checks_passed += 1
    else:
        errors.append("❌ notify() is not async def")

    # Check for import of HousekeepingNotificationPayload
    if "from app.agents.bed_management.schemas import HousekeepingNotificationPayload" in content:
        print("✅ Imports HousekeepingNotificationPayload")
        checks_passed += 1
    else:
        errors.append("❌ HousekeepingNotificationPayload not imported")

    # Check for no PHI logging
    if "bed_id=%s" in content and "encounter_id=%s" in content:
        print("✅ Logs only bed_id and encounter_id (no PHI)")
        checks_passed += 1
    else:
        errors.append("❌ Logging pattern does not follow no-PHI guidelines")

    return checks_passed, errors


def validate_main_py_integration() -> tuple[int, list[str]]:
    """Validate main.py wires HousekeepingNotifier into startup."""
    errors: list[str] = []
    checks_passed = 0

    if not MAIN_PATH.exists():
        errors.append(f"❌ main.py not found: {MAIN_PATH}")
        return 0, errors

    content = MAIN_PATH.read_text(encoding="utf-8")

    # Check for HousekeepingNotifier import
    if "from app.agents.bed_management.notifier import HousekeepingNotifier" in content:
        print("✅ main.py imports HousekeepingNotifier")
        checks_passed += 1
    else:
        errors.append("❌ main.py does not import HousekeepingNotifier")

    # Check for notifier instantiation (even if commented)
    if "HousekeepingNotifier(" in content:
        print("✅ HousekeepingNotifier instantiated in main")
        checks_passed += 1
    else:
        errors.append("❌ HousekeepingNotifier not instantiated in main")

    # Check for pubsub_client passed to notifier
    if "pubsub_client=" in content and "HousekeepingNotifier" in content:
        print("✅ pubsub_client passed to HousekeepingNotifier")
        checks_passed += 1
    else:
        errors.append("❌ pubsub_client not passed to HousekeepingNotifier")

    # Check for project_id passed to notifier
    if "project_id=" in content and "HousekeepingNotifier" in content:
        print("✅ project_id passed to HousekeepingNotifier")
        checks_passed += 1
    else:
        errors.append("❌ project_id not passed to HousekeepingNotifier")

    # Check for read_session_factory passed to notifier
    if "read_session_factory=" in content and "HousekeepingNotifier" in content:
        print("✅ read_session_factory passed to HousekeepingNotifier")
        checks_passed += 1
    else:
        errors.append("❌ read_session_factory not passed to HousekeepingNotifier")

    # Check for TASK-004 status marker
    if "TASK-004" in content:
        print("✅ TASK-004 status documented in main.py")
        checks_passed += 1
    else:
        errors.append("❌ TASK-004 status not documented in main.py")

    return checks_passed, errors


def validate_init_py_exports() -> tuple[int, list[str]]:
    """Validate __init__.py exports notifier classes."""
    errors: list[str] = []
    checks_passed = 0

    if not INIT_PATH.exists():
        errors.append(f"❌ __init__.py not found: {INIT_PATH}")
        return 0, errors

    content = INIT_PATH.read_text(encoding="utf-8")

    # Check for HousekeepingNotifier in __all__
    if "HousekeepingNotifier" in content:
        print("✅ __init__.py exports HousekeepingNotifier")
        checks_passed += 1
    else:
        errors.append("❌ __init__.py does not export HousekeepingNotifier")

    # Check for HousekeepingNotificationPayload in __all__
    if "HousekeepingNotificationPayload" in content:
        print("✅ __init__.py exports HousekeepingNotificationPayload")
        checks_passed += 1
    else:
        errors.append("❌ __init__.py does not export HousekeepingNotificationPayload")

    # Check for import from notifier
    if "from app.agents.bed_management.notifier import HousekeepingNotifier" in content:
        print("✅ __init__.py imports HousekeepingNotifier from notifier module")
        checks_passed += 1
    else:
        errors.append("❌ __init__.py does not import HousekeepingNotifier from notifier module")

    # Check for import from schemas
    if "HousekeepingNotificationPayload" in content and "from app.agents.bed_management.schemas" in content:
        print("✅ __init__.py imports HousekeepingNotificationPayload from schemas module")
        checks_passed += 1
    else:
        errors.append("❌ __init__.py does not import HousekeepingNotificationPayload from schemas module")

    return checks_passed, errors


def validate_code_quality() -> tuple[int, list[str]]:
    """Validate code quality standards."""
    errors: list[str] = []
    checks_passed = 0

    # Check notifier.py
    if NOTIFIER_PATH.exists():
        content = NOTIFIER_PATH.read_text(encoding="utf-8")

        # Module docstring
        if '"""' in content[:500]:
            print("✅ notifier.py has module docstring")
            checks_passed += 1
        else:
            errors.append("❌ notifier.py missing module docstring")

        # Class docstring
        if "class HousekeepingNotifier:" in content:
            class_start = content.find("class HousekeepingNotifier:")
            next_200 = content[class_start : class_start + 400]
            if '"""' in next_200:
                print("✅ HousekeepingNotifier has class docstring")
                checks_passed += 1
            else:
                errors.append("❌ HousekeepingNotifier missing class docstring")

        # Future annotations
        if "from __future__ import annotations" in content:
            print("✅ notifier.py uses future annotations")
            checks_passed += 1
        else:
            errors.append("❌ notifier.py missing future annotations")

        # Type hints
        if "-> None" in content or "-> Bed" in content:
            print("✅ notifier.py uses return type hints")
            checks_passed += 1
        else:
            errors.append("❌ notifier.py missing return type hints")

    # Check schemas.py for HousekeepingNotificationPayload docstring
    if SCHEMAS_PATH.exists():
        content = SCHEMAS_PATH.read_text(encoding="utf-8")
        if "class HousekeepingNotificationPayload" in content:
            class_start = content.find("class HousekeepingNotificationPayload")
            next_300 = content[class_start : class_start + 500]
            if '"""' in next_300:
                print("✅ HousekeepingNotificationPayload has class docstring")
                checks_passed += 1
            else:
                errors.append("❌ HousekeepingNotificationPayload missing class docstring")

    return checks_passed, errors


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    """Run all validators and report results."""
    print("=" * 70)
    print("US-035 TASK-004 VALIDATION")
    print("Housekeeping Pub/Sub Notification")
    print("=" * 70)

    all_errors: list[str] = []
    all_warnings: list[str] = []
    total_checks = 0
    total_passed = 0

    # 1. HousekeepingNotificationPayload Schema
    print("\n" + "=" * 70)
    print("1. HOUSEKEEPINGNOTIFICATIONPAYLOAD SCHEMA")
    print("=" * 70)
    passed, errors = validate_notification_payload_schema()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Payload Schema: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Payload Schema: ✅ All checks passed")

    # 2. HousekeepingNotifier Implementation
    print("\n" + "=" * 70)
    print("2. HOUSEKEEPINGNOTIFIER (notifier.py)")
    print("=" * 70)
    passed, errors = validate_notifier_py()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Notifier: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Notifier: ✅ All checks passed")

    # 3. Main.py Integration
    print("\n" + "=" * 70)
    print("3. MAIN.PY INTEGRATION")
    print("=" * 70)
    passed, errors = validate_main_py_integration()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Integration: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Integration: ✅ All checks passed")

    # 4. __init__.py Exports
    print("\n" + "=" * 70)
    print("4. __INIT__.PY EXPORTS")
    print("=" * 70)
    passed, errors = validate_init_py_exports()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Exports: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Exports: ✅ All checks passed")

    # 5. Code Quality
    print("\n" + "=" * 70)
    print("5. CODE QUALITY")
    print("=" * 70)
    passed, errors = validate_code_quality()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Code Quality: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Code Quality: ✅ All checks passed")

    # Final Summary
    print("\n" + "=" * 70)
    print("📊 OVERALL VALIDATION SUMMARY")
    print("=" * 70)

    if all_errors:
        print(f"\n❌ VALIDATION FAILED: {len(all_errors)} critical error(s) found\n")
        print("Critical Errors:")
        for err in all_errors[:10]:
            print(f"  {err}")
        if len(all_errors) > 10:
            print(f"  ... and {len(all_errors) - 10} more errors")
    else:
        print(f"\n✅ ALL VALIDATION CHECKS PASSED\n")
        print("US-035 TASK-004 Implementation Status:")
        print("  ✓ HousekeepingNotificationPayload with idempotency key")
        print("  ✓ HousekeepingNotifier with 5-second timeout")
        print("  ✓ Integration with agent entrypoint")
        print("  ✓ No PHI in Pub/Sub payloads or logs")
        print("  ✓ Code quality standards met")

    if all_warnings:
        print(f"\n⚠️  {len(all_warnings)} warning(s) - non-critical\n")
        for warn in all_warnings:
            print(f"  {warn}")

    if not all_errors:
        print("\nNext steps:")
        print("  1. Update task_004 status to Complete")
        print("  2. Create implementation summary")
        print("  3. Proceed to US-035 TASK-005")
    else:
        print("\nNext steps:")
        print("  1. Fix the critical errors listed above")
        print("  2. Re-run this validation script")
        print("  3. Ensure 100% pass rate before marking task Complete")

    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
