"""Automated validation for US-042 TASK-004: PATCH /api/v1/care/escalations/{id}/acknowledge Implementation.

Validates:
1. Schema file exists (care_escalation.py)
2. Schema structure (CareEscalationAcknowledgeResponse fields)
3. Router file exists (care_escalations.py)
4. Router endpoint defined (PATCH /care/escalations/{escalation_id}/acknowledge)
5. RBAC enforcement (allowed roles check)
6. Business logic (404, 409, 200 status codes)
7. Main.py integration (router import and registration)
8. Python syntax validation
9. PHI compliance (UUID-only logging and response)
10. Dependencies (get_write_db, get_current_user)

DoD Checklist:
- [x] care_escalation.py schema created with CareEscalationAcknowledgeResponse
- [x] care_escalations.py router created with PATCH endpoint
- [x] RBAC enforced via role checking dependency
- [x] 403 Forbidden returned for patient and pharmacist roles
- [x] 404 Not Found returned for unknown or soft-deleted escalation
- [x] 409 Conflict returned for already-acknowledged escalation
- [x] acknowledged_by set to current_user["sub"] (UUID from JWT sub claim)
- [x] Router registered in backend/app/main.py
- [x] No PHI in response body or log lines
- [x] Python syntax validated
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any


class ValidationResult:
    """Track validation check results."""

    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.warnings: int = 0
        self.checks: list[dict[str, Any]] = []

    def add_pass(self, check: str, detail: str = "") -> None:
        self.passed += 1
        self.checks.append({"status": "PASS", "check": check, "detail": detail})
        print(f"✓ {check}")
        if detail:
            print(f"  → {detail}")

    def add_fail(self, check: str, detail: str) -> None:
        self.failed += 1
        self.checks.append({"status": "FAIL", "check": check, "detail": detail})
        print(f"✗ {check}")
        print(f"  → {detail}")

    def add_warning(self, check: str, detail: str) -> None:
        self.warnings += 1
        self.checks.append({"status": "WARN", "check": check, "detail": detail})
        print(f"⚠ {check}")
        print(f"  → {detail}")

    def summary(self) -> str:
        total = self.passed + self.failed + self.warnings
        return (
            f"\n{'=' * 80}\n"
            f"Validation Summary: {self.passed}/{total} checks passed\n"
            f"  Passed: {self.passed}\n"
            f"  Failed: {self.failed}\n"
            f"  Warnings: {self.warnings}\n"
            f"{'=' * 80}\n"
        )


def validate_schema_file(result: ValidationResult, base_path: Path) -> None:
    """Validate that care_escalation.py schema file exists."""
    print("\n=== Schema File Validation ===\n")

    schema_path = base_path / "backend" / "app" / "schemas" / "care_escalation.py"

    if schema_path.exists():
        result.add_pass("care_escalation.py schema file exists", str(schema_path))
    else:
        result.add_fail("care_escalation.py schema file missing", str(schema_path))


def validate_schema_structure(result: ValidationResult, base_path: Path) -> None:
    """Validate CareEscalationAcknowledgeResponse schema structure."""
    print("\n=== Schema Structure Validation ===\n")

    schema_path = base_path / "backend" / "app" / "schemas" / "care_escalation.py"

    if not schema_path.exists():
        result.add_fail("Schema file not found for validation", str(schema_path))
        return

    content = schema_path.read_text(encoding="utf-8")
    tree = ast.parse(content)

    # Find CareEscalationAcknowledgeResponse class
    response_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CareEscalationAcknowledgeResponse":
            response_class = node
            break

    if response_class:
        result.add_pass("CareEscalationAcknowledgeResponse class defined")

        # Check for required fields
        required_fields = {
            "id",
            "encounter_id",
            "patient_id",
            "status",
            "sent_at",
            "acknowledged_at",
            "acknowledged_by",
            "escalated_to_supervisor",
            "escalated_at",
        }
        found_fields = {
            node.target.id
            for node in response_class.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }

        missing = required_fields - found_fields
        if not missing:
            result.add_pass(
                "CareEscalationAcknowledgeResponse has all required fields",
                f"Fields: {len(found_fields)}",
            )
        else:
            result.add_fail(
                "CareEscalationAcknowledgeResponse missing fields",
                f"Missing: {', '.join(sorted(missing))}",
            )

        # Check for BaseModel inheritance
        if "BaseModel" in content:
            result.add_pass("BaseModel inheritance present")
        else:
            result.add_fail("BaseModel inheritance missing", "Check Pydantic schema")

        # Check for from_attributes config
        if "from_attributes" in content or "ConfigDict" in content:
            result.add_pass("Pydantic config present (from_attributes or ConfigDict)")
        else:
            result.add_warning(
                "Pydantic config not found",
                "Verify from_attributes is configured",
            )
    else:
        result.add_fail("CareEscalationAcknowledgeResponse class not found", "Check schema file")


def validate_router_file(result: ValidationResult, base_path: Path) -> None:
    """Validate that care_escalations.py router file exists."""
    print("\n=== Router File Validation ===\n")

    router_path = (
        base_path / "backend" / "app" / "api" / "v1" / "routers" / "care_escalations.py"
    )

    if router_path.exists():
        result.add_pass("care_escalations.py router file exists", str(router_path))
    else:
        result.add_fail("care_escalations.py router file missing", str(router_path))


def validate_router_endpoint(result: ValidationResult, base_path: Path) -> None:
    """Validate router endpoint definition."""
    print("\n=== Router Endpoint Validation ===\n")

    router_path = (
        base_path / "backend" / "app" / "api" / "v1" / "routers" / "care_escalations.py"
    )

    if not router_path.exists():
        result.add_fail("Router file not found for validation", str(router_path))
        return

    content = router_path.read_text(encoding="utf-8")

    # Check for router initialization
    if "router = APIRouter(" in content:
        result.add_pass("APIRouter initialization present")
    else:
        result.add_fail("APIRouter initialization missing", "Check router definition")

    # Check for PATCH endpoint
    if '@router.patch(' in content and '/escalations/{escalation_id}/acknowledge' in content:
        result.add_pass("PATCH /escalations/{escalation_id}/acknowledge endpoint defined")
    else:
        result.add_fail("PATCH endpoint missing or incorrect", "Check @router.patch decorator")

    # Check for async function
    if "async def acknowledge_escalation(" in content:
        result.add_pass("acknowledge_escalation function defined as async")
    else:
        result.add_fail("acknowledge_escalation function missing or not async", "Check function definition")

    # Check for response_model
    if "response_model=CareEscalationAcknowledgeResponse" in content:
        result.add_pass("response_model configured correctly")
    else:
        result.add_fail("response_model missing or incorrect", "Check @router.patch decorator")

    # Check for status_code
    if "status_code=status.HTTP_200_OK" in content:
        result.add_pass("status_code configured correctly (200)")
    else:
        result.add_warning("status_code not explicitly set", "Verify HTTP 200 is returned")


def validate_rbac_enforcement(result: ValidationResult, base_path: Path) -> None:
    """Validate RBAC enforcement logic."""
    print("\n=== RBAC Enforcement Validation ===\n")

    router_path = (
        base_path / "backend" / "app" / "api" / "v1" / "routers" / "care_escalations.py"
    )

    if not router_path.exists():
        result.add_fail("Router file not found for RBAC validation", str(router_path))
        return

    content = router_path.read_text(encoding="utf-8")

    # Check for allowed roles definition
    if "_ALLOWED_ROLES" in content:
        result.add_pass("_ALLOWED_ROLES constant defined")
    else:
        result.add_fail("_ALLOWED_ROLES constant missing", "Check role definition")

    # Check for specific allowed roles
    allowed_roles = ["admin", "physician", "nurse", "charge_nurse"]
    missing_roles = []
    for role in allowed_roles:
        if f'"{role}"' in content:
            pass
        else:
            missing_roles.append(role)

    if not missing_roles:
        result.add_pass(
            "All required roles present in _ALLOWED_ROLES",
            f"Roles: {', '.join(allowed_roles)}",
        )
    else:
        result.add_fail(
            "Missing roles in _ALLOWED_ROLES",
            f"Missing: {', '.join(missing_roles)}",
        )

    # Check for role checking dependency
    if "_require_any_role" in content or "require_any_role" in content or "current_user.role" in content:
        result.add_pass("Role checking mechanism present")
    else:
        result.add_fail("Role checking mechanism missing", "Check RBAC dependency")

    # Check for 403 Forbidden
    if "status.HTTP_403_FORBIDDEN" in content or "403" in content:
        result.add_pass("403 Forbidden status code present for RBAC denial")
    else:
        result.add_fail("403 Forbidden status code missing", "Check RBAC error handling")


def validate_business_logic(result: ValidationResult, base_path: Path) -> None:
    """Validate business logic implementation."""
    print("\n=== Business Logic Validation ===\n")

    router_path = (
        base_path / "backend" / "app" / "api" / "v1" / "routers" / "care_escalations.py"
    )

    if not router_path.exists():
        result.add_fail("Router file not found for business logic validation", str(router_path))
        return

    content = router_path.read_text(encoding="utf-8")

    # Check for 404 Not Found
    if "status.HTTP_404_NOT_FOUND" in content or "404" in content:
        result.add_pass("404 Not Found handling present")
    else:
        result.add_fail("404 Not Found handling missing", "Check escalation existence check")

    # Check for 409 Conflict
    if "status.HTTP_409_CONFLICT" in content or "409" in content:
        result.add_pass("409 Conflict handling present")
    else:
        result.add_fail("409 Conflict handling missing", "Check already-acknowledged check")

    # Check for soft-delete check
    if "deleted_at.is_(None)" in content or "deleted_at IS NULL" in content:
        result.add_pass("Soft-delete check present")
    else:
        result.add_warning("Soft-delete check not found", "Verify deleted records are filtered")

    # Check for status update to ACKNOWLEDGED
    if "CareEscalationStatus.ACKNOWLEDGED" in content:
        result.add_pass("Status update to ACKNOWLEDGED present")
    else:
        result.add_fail("Status update missing", "Check status assignment")

    # Check for acknowledged_at timestamp
    if "acknowledged_at" in content and "datetime.now" in content:
        result.add_pass("acknowledged_at timestamp setting present")
    else:
        result.add_fail("acknowledged_at timestamp missing", "Check timestamp assignment")

    # Check for acknowledged_by assignment
    if "acknowledged_by" in content and ("current_user.sub" in content or "UUID(" in content):
        result.add_pass("acknowledged_by assignment present")
    else:
        result.add_fail("acknowledged_by assignment missing", "Check user ID assignment")

    # Check for database commit
    if "await session.commit()" in content:
        result.add_pass("Database commit present")
    else:
        result.add_fail("Database commit missing", "Check session.commit()")


def validate_main_integration(result: ValidationResult, base_path: Path) -> None:
    """Validate main.py integration."""
    print("\n=== Main.py Integration Validation ===\n")

    main_path = base_path / "backend" / "app" / "main.py"

    if not main_path.exists():
        result.add_fail("main.py not found", str(main_path))
        return

    content = main_path.read_text(encoding="utf-8")

    # Check for router import
    if "from app.api.v1.routers.care_escalations import router as care_escalations_router" in content:
        result.add_pass("care_escalations_router import present")
    else:
        result.add_fail("care_escalations_router import missing", "Check import statements")

    # Check for router registration
    if "app.include_router(care_escalations_router" in content:
        result.add_pass("care_escalations_router registration present")
    else:
        result.add_fail("care_escalations_router registration missing", "Check app.include_router()")

    # Check for prefix
    if 'prefix="/api/v1"' in content and "care_escalations_router" in content:
        result.add_pass("Router registered with /api/v1 prefix")
    else:
        result.add_warning("Router prefix not verified", "Check prefix configuration")


def validate_python_syntax(result: ValidationResult, base_path: Path) -> None:
    """Validate Python syntax."""
    print("\n=== Python Syntax Validation ===\n")

    files_to_check = [
        "backend/app/schemas/care_escalation.py",
        "backend/app/api/v1/routers/care_escalations.py",
    ]

    for file_rel in files_to_check:
        file_path = base_path / file_rel
        if not file_path.exists():
            result.add_fail(f"Syntax check skipped: {file_rel}", "File not found")
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
            ast.parse(content)
            result.add_pass(f"Syntax valid: {file_rel}")
        except SyntaxError as e:
            result.add_fail(
                f"Syntax error in {file_rel}",
                f"Line {e.lineno}: {e.msg}",
            )


def validate_phi_compliance(result: ValidationResult, base_path: Path) -> None:
    """Validate PHI compliance."""
    print("\n=== PHI Compliance Validation ===\n")

    router_path = (
        base_path / "backend" / "app" / "api" / "v1" / "routers" / "care_escalations.py"
    )

    if not router_path.exists():
        result.add_fail("Router file not found for PHI validation", str(router_path))
        return

    content = router_path.read_text(encoding="utf-8")

    # PHI fields that should NOT appear in logs or response
    phi_fields = [
        "patient_name",
        "patient.name",
        "first_name",
        "last_name",
        "phone_number",
        "email",
        "mrn",
        "date_of_birth",
        "dob",
        "ssn",
    ]

    found_phi = []
    for field in phi_fields:
        # Skip if it's in a comment or docstring explaining what NOT to include
        if field in content and f"No {field}" not in content and "no PHI" not in content.lower():
            found_phi.append(field)

    if not found_phi:
        result.add_pass("No PHI fields found in router", "UUID-only response and logging")
    else:
        result.add_warning(
            "Potential PHI fields found",
            f"Review these occurrences: {', '.join(found_phi)}",
        )

    # Check that response uses UUIDs
    uuid_fields = ["escalation_id", "encounter_id", "patient_id", "acknowledged_by"]
    found_uuids = []
    for field in uuid_fields:
        if field in content:
            found_uuids.append(field)

    if len(found_uuids) >= 3:
        result.add_pass(
            "UUID-based fields present",
            f"Found: {', '.join(found_uuids)}",
        )
    else:
        result.add_warning(
            "Limited UUID fields",
            f"Found only: {', '.join(found_uuids)}",
        )


def validate_dependencies(result: ValidationResult, base_path: Path) -> None:
    """Validate dependency imports."""
    print("\n=== Dependencies Validation ===\n")

    router_path = (
        base_path / "backend" / "app" / "api" / "v1" / "routers" / "care_escalations.py"
    )

    if not router_path.exists():
        result.add_fail("Router file not found for dependencies validation", str(router_path))
        return

    content = router_path.read_text(encoding="utf-8")

    required_imports = [
        "from app.core.auth.jwt import TokenClaims, get_current_user",
        "from app.db.deps import get_write_db",
        "from app.models.care_escalation import CareEscalation",
        "from app.schemas.care_escalation import CareEscalationAcknowledgeResponse",
    ]

    for import_stmt in required_imports:
        if import_stmt in content:
            result.add_pass(f"Import present: {import_stmt.split()[-1]}")
        else:
            result.add_fail(f"Import missing: {import_stmt}", "Check import statements")

    # Check for Depends usage
    if "Depends(get_write_db)" in content:
        result.add_pass("get_write_db dependency used correctly")
    else:
        result.add_fail("get_write_db dependency missing or incorrect", "Check function parameters")

    if "Depends(get_current_user)" in content or "Depends(_require_any_role" in content:
        result.add_pass("Auth dependency present")
    else:
        result.add_fail("Auth dependency missing", "Check function parameters")


def main() -> None:
    """Run all validation checks."""
    result = ValidationResult()
    base_path = Path(__file__).parent

    print("\n" + "=" * 80)
    print("US-042 TASK-004 Validation: PATCH /api/v1/care/escalations/{id}/acknowledge")
    print("=" * 80)

    validate_schema_file(result, base_path)
    validate_schema_structure(result, base_path)
    validate_router_file(result, base_path)
    validate_router_endpoint(result, base_path)
    validate_rbac_enforcement(result, base_path)
    validate_business_logic(result, base_path)
    validate_main_integration(result, base_path)
    validate_python_syntax(result, base_path)
    validate_phi_compliance(result, base_path)
    validate_dependencies(result, base_path)

    print(result.summary())

    if result.failed > 0:
        print("❌ Validation FAILED. Address failures before proceeding.")
        exit(1)
    elif result.warnings > 0:
        print("⚠️  Validation PASSED with warnings. Review warnings before deployment.")
        exit(0)
    else:
        print("✅ All validation checks PASSED. Implementation ready for testing.")
        exit(0)


if __name__ == "__main__":
    main()
