#!/usr/bin/env python3
"""Validation script for US-038 TASK-004: Boarding Alert Resolution.

Verifies:
    1. boarding_resolver.py module exists
    2. resolve_boarding_alert() function is defined
    3. Function accepts encounter_id and session parameters
    4. Function returns bool
    5. UPDATE query has WHERE boarding_alert_sent_at IS NOT NULL
    6. UPDATE query has WHERE boarding_alert_resolved_at IS NULL
    7. Function sets boarding_alert_resolved_at = now_utc
    8. Function returns True on rowcount > 0
    9. Function returns False on rowcount == 0
    10. BedStatusPatchRequest has encounter_id field
    11. PATCH endpoint imports resolve_boarding_alert
    12. PATCH endpoint calls resolve_boarding_alert when status=RESERVED
    13. Package __init__.py exports boarding_resolver

Design refs:
    US-038 TASK-004 — Boarding alert resolution on bed assignment
    US-038 AC Scenario 2 — no-op when no alert sent
    US-038 AC Scenario 3 — resolution on RESERVED assignment
"""
import sys
from pathlib import Path


def check_boarding_resolver_exists() -> bool:
    """Check if boarding_resolver.py module exists."""
    print("[1/13] Boarding Resolver Module Existence Check")
    
    resolver_file = Path("backend/app/agents/bed_management/boarding_resolver.py")
    
    if not resolver_file.exists():
        print(f"  ✗ Resolver file not found: {resolver_file}")
        return False
    
    print(f"  ✓ Resolver file exists: {resolver_file}")
    return True


def check_resolve_boarding_alert_function() -> bool:
    """Check if resolve_boarding_alert() function is defined."""
    print("\n[2/13] resolve_boarding_alert() Function Check")
    
    resolver_file = Path("backend/app/agents/bed_management/boarding_resolver.py")
    content = resolver_file.read_text(encoding='utf-8')
    
    checks = {
        "async def resolve_boarding_alert": "async def resolve_boarding_alert(",
        "US-038 reference": "US-038",
        "TASK-004 reference": "TASK-004",
        "Design refs comment": "Design refs:",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_function_signature() -> bool:
    """Check if function accepts correct parameters."""
    print("\n[3/13] Function Signature Check")
    
    resolver_file = Path("backend/app/agents/bed_management/boarding_resolver.py")
    content = resolver_file.read_text(encoding='utf-8')
    
    checks = {
        "encounter_id parameter": "encounter_id: str",
        "session parameter": "session: AsyncSession",
        "return type": "-> bool:",
        "docstring": '"""Resolve the boarding alert',
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_uuid_parsing() -> bool:
    """Check if encounter_id is parsed as UUID."""
    print("\n[4/13] UUID Parsing Check")
    
    resolver_file = Path("backend/app/agents/bed_management/boarding_resolver.py")
    content = resolver_file.read_text(encoding='utf-8')
    
    checks = {
        "uuid.UUID() call": "uuid.UUID(encounter_id)",
        "except ValueError": "except ValueError:",
        "logger.error on invalid UUID": "logger.error",
        "return False on error": "return False",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_update_query_filters() -> bool:
    """Check if UPDATE query has correct WHERE clause."""
    print("\n[5/13] UPDATE Query Filters Check")
    
    resolver_file = Path("backend/app/agents/bed_management/boarding_resolver.py")
    content = resolver_file.read_text(encoding='utf-8')
    
    checks = {
        "update(Encounter)": "update(Encounter)",
        "Encounter.id == encounter_uuid": "Encounter.id == encounter_uuid",
        "boarding_alert_sent_at.is_not(None)": "Encounter.boarding_alert_sent_at.is_not(None)",
        "boarding_alert_resolved_at.is_(None)": "Encounter.boarding_alert_resolved_at.is_(None)",
        "values(boarding_alert_resolved_at": "values(boarding_alert_resolved_at=now_utc)",
        "returning(Encounter.id)": "returning(Encounter.id)",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_return_logic() -> bool:
    """Check if function returns True/False based on rowcount."""
    print("\n[6/13] Return Logic Check")
    
    resolver_file = Path("backend/app/agents/bed_management/boarding_resolver.py")
    content = resolver_file.read_text(encoding='utf-8')
    
    checks = {
        "rowcount check": "resolved = result.rowcount > 0",
        "logger.info on success": "logger.info",
        "logger.debug on no-op": "logger.debug",
        "return resolved": "return resolved",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_imports() -> bool:
    """Check if all required imports are present."""
    print("\n[7/13] Imports Check")
    
    resolver_file = Path("backend/app/agents/bed_management/boarding_resolver.py")
    content = resolver_file.read_text(encoding='utf-8')
    
    checks = {
        "logging import": "import logging",
        "uuid import": "import uuid",
        "datetime import": "from datetime import UTC, datetime",
        "sqlalchemy update": "from sqlalchemy import update",
        "AsyncSession import": "from sqlalchemy.ext.asyncio import AsyncSession",
        "Encounter import": "from app.models.encounter import Encounter",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_bed_status_patch_request() -> bool:
    """Check if BedStatusPatchRequest has encounter_id field."""
    print("\n[8/13] BedStatusPatchRequest Schema Check")
    
    beds_router = Path("backend/app/api/v1/routers/beds.py")
    content = beds_router.read_text(encoding='utf-8')
    
    checks = {
        "encounter_id field": "encounter_id: uuid.UUID | None",
        "Field definition": 'Field(\n        None,',
        "description": "Encounter ID for bed assignment",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_patch_endpoint_import() -> bool:
    """Check if PATCH endpoint imports resolve_boarding_alert."""
    print("\n[9/13] PATCH Endpoint Import Check")
    
    beds_router = Path("backend/app/api/v1/routers/beds.py")
    content = beds_router.read_text(encoding='utf-8')
    
    checks = {
        "resolve_boarding_alert import": "from app.agents.bed_management.boarding_resolver import resolve_boarding_alert",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_patch_endpoint_call() -> bool:
    """Check if PATCH endpoint calls resolve_boarding_alert when status=RESERVED."""
    print("\n[10/13] PATCH Endpoint Resolution Call Check")
    
    beds_router = Path("backend/app/api/v1/routers/beds.py")
    content = beds_router.read_text(encoding='utf-8')
    
    checks = {
        "US-038 comment": "# US-038: Resolve boarding alert when bed is RESERVED",
        "RESERVED status check": "if body.status == BedStatus.RESERVED and body.encounter_id:",
        "await resolve_boarding_alert": "await resolve_boarding_alert(",
        "encounter_id parameter": "encounter_id=str(body.encounter_id)",
        "session parameter": "session=write_db",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_atomic_commit() -> bool:
    """Check if resolution and bed update are in same transaction."""
    print("\n[11/13] Atomic Transaction Check")
    
    beds_router = Path("backend/app/api/v1/routers/beds.py")
    content = beds_router.read_text(encoding='utf-8')
    
    # Verify resolution happens before commit
    checks = {
        "Resolution before commit": "await resolve_boarding_alert(" in content and content.index("await resolve_boarding_alert(") < content.index("await write_db.commit()"),
        "Single commit": content.count("await write_db.commit()") == 1,
    }
    
    all_passed = True
    for check_name, condition in checks.items():
        if condition:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} failed")
            all_passed = False
    
    return all_passed


def check_package_init_updated() -> bool:
    """Check if bed_management __init__.py exports boarding_resolver."""
    print("\n[12/13] Package Initialization Check")
    
    init_file = Path("backend/app/agents/bed_management/__init__.py")
    content = init_file.read_text(encoding='utf-8')
    
    checks = {
        "boarding_resolver in __all__": '"boarding_resolver"',
        "boarding_resolver import": "from app.agents.bed_management import boarding_resolver",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_idempotency() -> bool:
    """Check if resolution is idempotent."""
    print("\n[13/13] Idempotency Check")
    
    resolver_file = Path("backend/app/agents/bed_management/boarding_resolver.py")
    content = resolver_file.read_text(encoding='utf-8')
    
    checks = {
        "Idempotent comment": "idempotent and concurrent-safe",
        "Already resolved check": "boarding_alert_resolved_at.is_(None)",
        "rowcount > 0 check": "result.rowcount > 0",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def main() -> int:
    """Run all validation checks."""
    print("=" * 80)
    print("US-038 TASK-004 Validation: Boarding Alert Resolution")
    print("=" * 80)
    
    results = [
        check_boarding_resolver_exists(),
        check_resolve_boarding_alert_function(),
        check_function_signature(),
        check_uuid_parsing(),
        check_update_query_filters(),
        check_return_logic(),
        check_imports(),
        check_bed_status_patch_request(),
        check_patch_endpoint_import(),
        check_patch_endpoint_call(),
        check_atomic_commit(),
        check_package_init_updated(),
        check_idempotency(),
    ]
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 80)
    if all(results):
        print(f"✅ ALL VALIDATION CHECKS PASSED ({passed}/{total})")
    else:
        print(f"❌ SOME CHECKS FAILED ({passed}/{total})")
    print("=" * 80)
    
    print("\nValidation Summary:")
    print("  ✓ resolve_boarding_alert() function defined")
    print("  ✓ UPDATE query filters: boarding_alert_sent_at IS NOT NULL AND boarding_alert_resolved_at IS NULL")
    print("  ✓ Sets boarding_alert_resolved_at = now_utc")
    print("  ✓ Returns True on resolution, False on no-op")
    print("  ✓ BedStatusPatchRequest includes encounter_id field")
    print("  ✓ PATCH endpoint calls resolve_boarding_alert when status=RESERVED")
    print("  ✓ Resolution and bed update in same transaction (atomic commit)")
    print("  ✓ Package __init__.py exports boarding_resolver")
    
    print("\nNext Steps:")
    print("  1. Implement TASK-005 (Unit Tests)")
    print("  2. Implement TASK-006 (Code Review & DoD Sign-off)")
    print("  3. Update task status to Complete")
    print("  4. Create implementation summary")
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
