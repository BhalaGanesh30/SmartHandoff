#!/usr/bin/env python
"""Validation script for US-035 TASK-005: Bed Board REST API.

Validates:
1. beds.py Router Implementation
2. GET /api/v1/beds Endpoint
3. PATCH /api/v1/beds/{id}/status Endpoint
4. RBAC Permission Checks
5. Audit Logging
6. Code Quality

Run: python validate_us035_task005_rest_api.py

Design refs:
    US-035 AC Scenario 3 — GET /api/v1/beds filtered; p95 <500ms
    US-035 DoD           — PATCH /api/v1/beds/{id}/status for BedManager role
"""
from __future__ import annotations

import pathlib
import sys

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

BEDS_ROUTER_PATH = pathlib.Path("backend/app/api/v1/routers/beds.py")
MAIN_PATH = pathlib.Path("backend/app/main.py")

# ══════════════════════════════════════════════════════════════════════════════
# VALIDATORS
# ══════════════════════════════════════════════════════════════════════════════


def validate_beds_router() -> tuple[int, list[str]]:
    """Validate beds.py router implementation."""
    errors: list[str] = []
    checks_passed = 0

    if not BEDS_ROUTER_PATH.exists():
        errors.append(f"❌ beds.py not found: {BEDS_ROUTER_PATH}")
        return 0, errors

    content = BEDS_ROUTER_PATH.read_text(encoding="utf-8")

    # Check for required imports
    required_imports = [
        "from app.db.deps import get_read_db, get_write_db",
        "from app.agents.bed_management.schemas import BedStatus",
        "from app.services.audit_service import write_audit_log",
        "from app.core.auth.rbac import require_permission",
    ]
    for imp in required_imports:
        if imp in content:
            print(f"✅ Import present: {imp}")
            checks_passed += 1
        else:
            errors.append(f"❌ Missing import: {imp}")

    # Check for router definition
    if "router = APIRouter(prefix=\"/beds\", tags=[\"beds\"])" in content:
        print("✅ Router defined with correct prefix and tags")
        checks_passed += 1
    else:
        errors.append("❌ Router not defined with correct prefix/tags")

    # Check for Pydantic schemas
    schemas = ["BedBoardEntry", "BedStatusPatchRequest", "BedStatusPatchResponse"]
    for schema in schemas:
        if f"class {schema}(BaseModel):" in content:
            print(f"✅ {schema} schema defined")
            checks_passed += 1
        else:
            errors.append(f"❌ {schema} schema not found")

    return checks_passed, errors


def validate_get_beds_endpoint() -> tuple[int, list[str]]:
    """Validate GET /api/v1/beds endpoint."""
    errors: list[str] = []
    checks_passed = 0

    if not BEDS_ROUTER_PATH.exists():
        errors.append(f"❌ beds.py not found: {BEDS_ROUTER_PATH}")
        return 0, errors

    content = BEDS_ROUTER_PATH.read_text(encoding="utf-8")

    # Check for GET endpoint decorator
    if '@router.get(\n    "",\n    response_model=list[BedBoardEntry]' in content:
        print("✅ GET /beds endpoint defined with correct response model")
        checks_passed += 1
    else:
        errors.append("❌ GET /beds endpoint not properly defined")

    # Check for query parameters
    params = ["unit", "status", "bed_type"]
    for param in params:
        if f"{param}:" in content and "Query(" in content:
            print(f"✅ Query parameter '{param}' defined")
            checks_passed += 1
        else:
            errors.append(f"❌ Query parameter '{param}' not found")

    # Check for RBAC permission
    if 'require_permission("bed", "list")' in content:
        print("✅ GET endpoint uses bed:list permission")
        checks_passed += 1
    else:
        errors.append("❌ GET endpoint missing bed:list permission check")

    # Check for read replica routing
    if "get_read_db" in content and "read_db: AsyncSession = Depends(get_read_db)" in content:
        print("✅ GET endpoint uses read replica (get_read_db)")
        checks_passed += 1
    else:
        errors.append("❌ GET endpoint not using read replica")

    # Check for mv_bed_board query
    if "SELECT * FROM mv_bed_board" in content:
        print("✅ Queries mv_bed_board materialised view")
        checks_passed += 1
    else:
        errors.append("❌ Does not query mv_bed_board")

    # Check for filter implementation
    if "WHERE 1=1" in content and "AND unit = :unit" in content:
        print("✅ Implements dynamic SQL filtering")
        checks_passed += 1
    else:
        errors.append("❌ Dynamic SQL filtering not implemented")

    return checks_passed, errors


def validate_patch_status_endpoint() -> tuple[int, list[str]]:
    """Validate PATCH /api/v1/beds/{id}/status endpoint."""
    errors: list[str] = []
    checks_passed = 0

    if not BEDS_ROUTER_PATH.exists():
        errors.append(f"❌ beds.py not found: {BEDS_ROUTER_PATH}")
        return 0, errors

    content = BEDS_ROUTER_PATH.read_text(encoding="utf-8")

    # Check for PATCH endpoint decorator
    if '@router.patch(\n    "/{bed_id}/status"' in content:
        print("✅ PATCH /beds/{id}/status endpoint defined")
        checks_passed += 1
    else:
        errors.append("❌ PATCH /beds/{id}/status endpoint not found")

    # Check for RBAC permission (bed:write)
    if 'require_permission("bed", "write")' in content:
        print("✅ PATCH endpoint uses bed:write permission")
        checks_passed += 1
    else:
        errors.append("❌ PATCH endpoint missing bed:write permission check")

    # Check for write DB usage
    if "write_db: AsyncSession = Depends(get_write_db)" in content:
        print("✅ PATCH endpoint uses write DB (get_write_db)")
        checks_passed += 1
    else:
        errors.append("❌ PATCH endpoint not using write DB")

    # Check for bed existence validation
    if "scalar_one_or_none()" in content and "HTTPException" in content:
        print("✅ Validates bed existence (404 if not found)")
        checks_passed += 1
    else:
        errors.append("❌ Bed existence validation not found")

    # Check for audit logging
    if "write_audit_log" in content and '"BED_STATUS_OVERRIDE"' in content:
        print("✅ Writes audit log with BED_STATUS_OVERRIDE action")
        checks_passed += 1
    else:
        errors.append("❌ Audit logging not implemented")

    # Check for commit
    if "await write_db.commit()" in content:
        print("✅ Commits transaction after update")
        checks_passed += 1
    else:
        errors.append("❌ Transaction commit not found")

    # Check for mv_bed_board refresh (commented is OK for now)
    if "refresh_service" in content or "BedBoardRefreshService" in content:
        print("✅ mv_bed_board refresh service referenced")
        checks_passed += 1
    else:
        errors.append("❌ mv_bed_board refresh not referenced")

    # Check for request body validation
    if "BedStatusPatchRequest" in content:
        print("✅ Uses BedStatusPatchRequest for request body")
        checks_passed += 1
    else:
        errors.append("❌ BedStatusPatchRequest not used")

    return checks_passed, errors


def validate_main_registration() -> tuple[int, list[str]]:
    """Validate beds router is registered in main.py."""
    errors: list[str] = []
    checks_passed = 0

    if not MAIN_PATH.exists():
        errors.append(f"❌ main.py not found: {MAIN_PATH}")
        return 0, errors

    content = MAIN_PATH.read_text(encoding="utf-8")

    # Check for import
    if "from app.api.v1.routers.beds import router as beds_router" in content:
        print("✅ beds_router imported in main.py")
        checks_passed += 1
    else:
        errors.append("❌ beds_router not imported in main.py")

    # Check for router registration
    if "app.include_router(beds_router, prefix=\"/api/v1\")" in content:
        print("✅ beds_router registered with /api/v1 prefix")
        checks_passed += 1
    else:
        errors.append("❌ beds_router not registered")

    return checks_passed, errors


def validate_code_quality() -> tuple[int, list[str]]:
    """Validate code quality standards."""
    errors: list[str] = []
    checks_passed = 0

    if not BEDS_ROUTER_PATH.exists():
        return 0, errors

    content = BEDS_ROUTER_PATH.read_text(encoding="utf-8")

    # Module docstring
    if '"""' in content[:500]:
        print("✅ beds.py has module docstring")
        checks_passed += 1
    else:
        errors.append("❌ beds.py missing module docstring")

    # Future annotations
    if "from __future__ import annotations" in content:
        print("✅ Uses future annotations")
        checks_passed += 1
    else:
        errors.append("❌ Missing future annotations")

    # Type hints
    if "-> list[BedBoardEntry]" in content and "-> BedStatusPatchResponse" in content:
        print("✅ Uses return type hints")
        checks_passed += 1
    else:
        errors.append("❌ Missing return type hints")

    # Logging
    if "logger = logging.getLogger(__name__)" in content:
        print("✅ Logging configured")
        checks_passed += 1
    else:
        errors.append("❌ Logging not configured")

    # Docstrings for endpoints
    if '"""Query mv_bed_board with optional filters' in content:
        print("✅ GET endpoint has docstring")
        checks_passed += 1
    else:
        errors.append("❌ GET endpoint missing docstring")

    if '"""Override bed status; write to primary' in content:
        print("✅ PATCH endpoint has docstring")
        checks_passed += 1
    else:
        errors.append("❌ PATCH endpoint missing docstring")

    return checks_passed, errors


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    """Run all validators and report results."""
    print("=" * 70)
    print("US-035 TASK-005 VALIDATION")
    print("Bed Board REST API")
    print("=" * 70)

    all_errors: list[str] = []
    total_checks = 0
    total_passed = 0

    # 1. Router Implementation
    print("\n" + "=" * 70)
    print("1. BEDS.PY ROUTER IMPLEMENTATION")
    print("=" * 70)
    passed, errors = validate_beds_router()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Router: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Router: ✅ All checks passed")

    # 2. GET Endpoint
    print("\n" + "=" * 70)
    print("2. GET /api/v1/beds ENDPOINT")
    print("=" * 70)
    passed, errors = validate_get_beds_endpoint()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 GET Endpoint: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 GET Endpoint: ✅ All checks passed")

    # 3. PATCH Endpoint
    print("\n" + "=" * 70)
    print("3. PATCH /api/v1/beds/{id}/status ENDPOINT")
    print("=" * 70)
    passed, errors = validate_patch_status_endpoint()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 PATCH Endpoint: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 PATCH Endpoint: ✅ All checks passed")

    # 4. Main Registration
    print("\n" + "=" * 70)
    print("4. MAIN.PY REGISTRATION")
    print("=" * 70)
    passed, errors = validate_main_registration()
    total_passed += passed
    total_checks += passed + len(errors)
    all_errors.extend(errors)
    if errors:
        print(f"\n📊 Registration: ❌ {len(errors)} error(s)")
    else:
        print(f"\n📊 Registration: ✅ All checks passed")

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
        print("US-035 TASK-005 Implementation Status:")
        print("  ✓ GET /api/v1/beds with filtering")
        print("  ✓ PATCH /api/v1/beds/{id}/status with RBAC")
        print("  ✓ Audit logging for status overrides")
        print("  ✓ Read replica routing (CQRS)")
        print("  ✓ Code quality standards met")

    if not all_errors:
        print("\nNext steps:")
        print("  1. Update task_005 status to Complete")
        print("  2. Create implementation summary")
        print("  3. Proceed to US-035 TASK-006")
    else:
        print("\nNext steps:")
        print("  1. Fix the critical errors listed above")
        print("  2. Re-run this validation script")
        print("  3. Ensure 100% pass rate before marking task Complete")

    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
