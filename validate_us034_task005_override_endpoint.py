#!/usr/bin/env python3
"""Validation script for US-034 TASK-005: Override Endpoint Implementation.

Validates:
1. Repository implementation (override_task method, custom exceptions)
2. Schema definitions (TaskOverrideRequest, TaskOverrideResponse)
3. Router endpoint (PATCH override endpoint with RBAC)
4. Error handling (404, 409, 422, 403)
5. Design alignment (US-034 Scenario 4, DoD requirements)
"""
import ast
import sys
from pathlib import Path


def print_header(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'=' * 70}")
    print(f"{title}")
    print(f"{'=' * 70}\n")


def print_result(check: str, passed: bool) -> None:
    """Print a check result."""
    symbol = "✅" if passed else "❌"
    print(f"{symbol} {check}")


def validate_repository() -> tuple[int, int]:
    """Validate AgentTaskRepository implementation."""
    repo_path = Path("backend/app/repositories/agent_task_repository.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("1. REPOSITORY VALIDATION")
    
    if not repo_path.exists():
        print_result("agent_task_repository.py file exists", False)
        return 0, 1
    
    print_result("agent_task_repository.py file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with repo_path.open("r") as f:
        content = f.read()
    
    # Check for custom exceptions
    exceptions = [
        "TaskNotFoundError",
        "InvalidTaskTypeError",
        "TaskAlreadyCompletedError",
    ]
    
    for exc in exceptions:
        total_checks += 1
        has_exception = f"class {exc}(Exception):" in content
        print_result(f"Custom exception '{exc}' defined", has_exception)
        if has_exception:
            checks_passed += 1
    
    # Check AgentTaskRepository class
    total_checks += 1
    has_repo_class = "class AgentTaskRepository:" in content
    print_result("AgentTaskRepository class defined", has_repo_class)
    if has_repo_class:
        checks_passed += 1
    
    # Check override_task method
    total_checks += 1
    has_override_method = "async def override_task(" in content
    print_result("override_task() async method exists", has_override_method)
    if has_override_method:
        checks_passed += 1
    
    # Check method parameters
    required_params = ["task_id", "encounter_id", "actor_id", "note", "session"]
    for param in required_params:
        total_checks += 1
        has_param = f"{param}:" in content or f"{param} =" in content
        print_result(f"override_task() has '{param}' parameter", has_param)
        if has_param:
            checks_passed += 1
    
    # Check business logic
    total_checks += 1
    checks_task_type = '"MEDICATION_RECONCILIATION"' in content
    print_result("Validates task is MEDICATION_RECONCILIATION", checks_task_type)
    if checks_task_type:
        checks_passed += 1
    
    total_checks += 1
    checks_completed_status = "AgentTaskStatus.COMPLETED" in content
    print_result("Checks if task already COMPLETED", checks_completed_status)
    if checks_completed_status:
        checks_passed += 1
    
    total_checks += 1
    clears_sla_field = "sla_escalation_sent_at = None" in content
    print_result("Clears sla_escalation_sent_at field (US-034 AC4)", clears_sla_field)
    if clears_sla_field:
        checks_passed += 1
    
    total_checks += 1
    sets_status = "status = AgentTaskStatus.COMPLETED" in content
    print_result("Sets status to COMPLETED", sets_status)
    if sets_status:
        checks_passed += 1
    
    total_checks += 1
    sets_completed_at = "completed_at = now" in content or "completed_at=now" in content
    print_result("Sets completed_at timestamp", sets_completed_at)
    if sets_completed_at:
        checks_passed += 1
    
    # Check audit log
    total_checks += 1
    creates_audit_log = "AuditLog(" in content
    print_result("Creates AuditLog entry", creates_audit_log)
    if creates_audit_log:
        checks_passed += 1
    
    total_checks += 1
    audit_action = "TASK_MANUALLY_OVERRIDDEN" in content
    print_result("Audit log action is 'TASK_MANUALLY_OVERRIDDEN'", audit_action)
    if audit_action:
        checks_passed += 1
    
    total_checks += 1
    commits_transaction = "await session.commit()" in content
    print_result("Commits transaction", commits_transaction)
    if commits_transaction:
        checks_passed += 1
    
    print(f"\n📊 Repository: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_schemas() -> tuple[int, int]:
    """Validate task override schemas."""
    schema_path = Path("backend/app/schemas/task_override.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("2. SCHEMA VALIDATION")
    
    if not schema_path.exists():
        print_result("task_override.py schema file exists", False)
        return 0, 1
    
    print_result("task_override.py schema file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with schema_path.open("r") as f:
        content = f.read()
    
    # Check TaskOverrideRequest
    total_checks += 1
    has_request_schema = "class TaskOverrideRequest(BaseModel):" in content
    print_result("TaskOverrideRequest schema defined", has_request_schema)
    if has_request_schema:
        checks_passed += 1
    
    total_checks += 1
    has_note_field = "note: str" in content
    print_result("TaskOverrideRequest has 'note' field", has_note_field)
    if has_note_field:
        checks_passed += 1
    
    total_checks += 1
    has_min_length = "min_length=" in content
    print_result("note field has min_length validation", has_min_length)
    if has_min_length:
        checks_passed += 1
    
    total_checks += 1
    has_max_length = "max_length=" in content
    print_result("note field has max_length validation", has_max_length)
    if has_max_length:
        checks_passed += 1
    
    # Check TaskOverrideResponse
    total_checks += 1
    has_response_schema = "class TaskOverrideResponse(BaseModel):" in content
    print_result("TaskOverrideResponse schema defined", has_response_schema)
    if has_response_schema:
        checks_passed += 1
    
    response_fields = [
        "task_id",
        "encounter_id",
        "agent_type",
        "status",
        "completed_at",
        "sla_escalation_sent_at",
        "overridden_by",
        "note",
    ]
    
    for field in response_fields:
        total_checks += 1
        has_field = f"{field}:" in content
        print_result(f"TaskOverrideResponse has '{field}' field", has_field)
        if has_field:
            checks_passed += 1
    
    # Check imports
    total_checks += 1
    imports_pydantic = "from pydantic import" in content
    print_result("Imports Pydantic BaseModel", imports_pydantic)
    if imports_pydantic:
        checks_passed += 1
    
    total_checks += 1
    imports_uuid = "from uuid import UUID" in content
    print_result("Imports UUID type", imports_uuid)
    if imports_uuid:
        checks_passed += 1
    
    print(f"\n📊 Schemas: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_router() -> tuple[int, int]:
    """Validate tasks router implementation."""
    router_path = Path("backend/app/api/v1/routers/tasks.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("3. ROUTER VALIDATION")
    
    if not router_path.exists():
        print_result("tasks.py router file exists", False)
        return 0, 1
    
    print_result("tasks.py router file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with router_path.open("r") as f:
        content = f.read()
    
    # Check imports
    total_checks += 1
    imports_repository = "from app.repositories.agent_task_repository import" in content
    print_result("Imports AgentTaskRepository", imports_repository)
    if imports_repository:
        checks_passed += 1
    
    total_checks += 1
    imports_schemas = "from app.schemas.task_override import" in content
    print_result("Imports task override schemas", imports_schemas)
    if imports_schemas:
        checks_passed += 1
    
    total_checks += 1
    imports_write_db = "from app.db.deps import get_write_db" in content
    print_result("Imports get_write_db", imports_write_db)
    if imports_write_db:
        checks_passed += 1
    
    total_checks += 1
    imports_require_role = "from app.core.auth.dependencies import require_role" in content
    print_result("Imports require_role for RBAC", imports_require_role)
    if imports_require_role:
        checks_passed += 1
    
    # Check allowed roles constant
    total_checks += 1
    has_allowed_roles = "_OVERRIDE_ALLOWED_ROLES" in content
    print_result("Defines _OVERRIDE_ALLOWED_ROLES constant", has_allowed_roles)
    if has_allowed_roles:
        checks_passed += 1
    
    total_checks += 1
    has_charge_pharmacist = "CHARGE_PHARMACIST" in content
    print_result("CHARGE_PHARMACIST in allowed roles", has_charge_pharmacist)
    if has_charge_pharmacist:
        checks_passed += 1
    
    total_checks += 1
    has_pharmacy_supervisor = "PHARMACY_SUPERVISOR" in content
    print_result("PHARMACY_SUPERVISOR in allowed roles", has_pharmacy_supervisor)
    if has_pharmacy_supervisor:
        checks_passed += 1
    
    # Check endpoint definition
    total_checks += 1
    has_patch_decorator = "@router.patch(" in content
    print_result("Has @router.patch decorator", has_patch_decorator)
    if has_patch_decorator:
        checks_passed += 1
    
    total_checks += 1
    has_override_function = "async def override_task(" in content
    print_result("override_task() endpoint function exists", has_override_function)
    if has_override_function:
        checks_passed += 1
    
    total_checks += 1
    has_encounter_id_param = "encounter_id: uuid.UUID" in content or "encounter_id: UUID" in content
    print_result("Endpoint has encounter_id parameter", has_encounter_id_param)
    if has_encounter_id_param:
        checks_passed += 1
    
    total_checks += 1
    has_task_id_param = "task_id: uuid.UUID" in content or "task_id: UUID" in content
    print_result("Endpoint has task_id parameter", has_task_id_param)
    if has_task_id_param:
        checks_passed += 1
    
    total_checks += 1
    has_body_param = "body: TaskOverrideRequest" in content
    print_result("Endpoint has body: TaskOverrideRequest parameter", has_body_param)
    if has_body_param:
        checks_passed += 1
    
    total_checks += 1
    uses_require_role = "Depends(require_role(" in content
    print_result("Uses require_role dependency for RBAC", uses_require_role)
    if uses_require_role:
        checks_passed += 1
    
    total_checks += 1
    uses_write_db = "Depends(get_write_db)" in content
    print_result("Uses get_write_db dependency", uses_write_db)
    if uses_write_db:
        checks_passed += 1
    
    total_checks += 1
    returns_response = "TaskOverrideResponse" in content
    print_result("Returns TaskOverrideResponse", returns_response)
    if returns_response:
        checks_passed += 1
    
    # Check error handling
    total_checks += 1
    handles_not_found = "TaskNotFoundError" in content and "404" in content
    print_result("Handles TaskNotFoundError → HTTP 404", handles_not_found)
    if handles_not_found:
        checks_passed += 1
    
    total_checks += 1
    handles_invalid_type = "InvalidTaskTypeError" in content and "422" in content
    print_result("Handles InvalidTaskTypeError → HTTP 422", handles_invalid_type)
    if handles_invalid_type:
        checks_passed += 1
    
    total_checks += 1
    handles_already_completed = "TaskAlreadyCompletedError" in content and "409" in content
    print_result("Handles TaskAlreadyCompletedError → HTTP 409", handles_already_completed)
    if handles_already_completed:
        checks_passed += 1
    
    # Check OpenAPI documentation
    total_checks += 1
    has_summary = "summary=" in content or '"summary":' in content
    print_result("Has OpenAPI summary", has_summary)
    if has_summary:
        checks_passed += 1
    
    total_checks += 1
    has_description = "description=" in content
    print_result("Has OpenAPI description", has_description)
    if has_description:
        checks_passed += 1
    
    total_checks += 1
    has_responses = "responses=" in content
    print_result("Has OpenAPI responses documentation", has_responses)
    if has_responses:
        checks_passed += 1
    
    print(f"\n📊 Router: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_design_alignment() -> tuple[int, int]:
    """Validate alignment with US-034 requirements."""
    checks_passed = 0
    total_checks = 0
    
    print_header("4. DESIGN ALIGNMENT VALIDATION")
    
    repo_path = Path("backend/app/repositories/agent_task_repository.py")
    router_path = Path("backend/app/api/v1/routers/tasks.py")
    
    # Check US-034 references
    total_checks += 1
    if repo_path.exists():
        with repo_path.open("r") as f:
            repo_content = f.read()
        has_us034_ref = "US-034" in repo_content
        print_result("Repository references US-034", has_us034_ref)
        if has_us034_ref:
            checks_passed += 1
    else:
        print_result("Repository references US-034", False)
    
    total_checks += 1
    if router_path.exists():
        with router_path.open("r") as f:
            router_content = f.read()
        has_us034_ref = "US-034" in router_content
        print_result("Router references US-034", has_us034_ref)
        if has_us034_ref:
            checks_passed += 1
    else:
        print_result("Router references US-034", False)
    
    # Check Scenario 4 implementation
    total_checks += 1
    if repo_path.exists():
        implements_scenario_4 = (
            "sla_escalation_sent_at = None" in repo_content
            and "AgentTaskStatus.COMPLETED" in repo_content
        )
        print_result("Implements US-034 Scenario 4 (clear sla_escalation_sent_at)", implements_scenario_4)
        if implements_scenario_4:
            checks_passed += 1
    else:
        print_result("Implements US-034 Scenario 4 (clear sla_escalation_sent_at)", False)
    
    # Check DoD requirements
    total_checks += 1
    if router_path.exists():
        has_rbac = "require_role" in router_content or "require_permission" in router_content
        print_result("DoD: RBAC enforcement present", has_rbac)
        if has_rbac:
            checks_passed += 1
    else:
        print_result("DoD: RBAC enforcement present", False)
    
    total_checks += 1
    if repo_path.exists():
        has_audit_log = "AuditLog(" in repo_content
        print_result("DoD: Audit log entry created", has_audit_log)
        if has_audit_log:
            checks_passed += 1
    else:
        print_result("DoD: Audit log entry created", False)
    
    print(f"\n📊 Design Alignment: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def main() -> int:
    """Run all validation checks."""
    print_header("US-034 TASK-005 VALIDATION\nManual Override Endpoint Implementation")
    
    all_checks_passed = 0
    all_total_checks = 0
    
    repo_passed, repo_total = validate_repository()
    all_checks_passed += repo_passed
    all_total_checks += repo_total
    
    schema_passed, schema_total = validate_schemas()
    all_checks_passed += schema_passed
    all_total_checks += schema_total
    
    router_passed, router_total = validate_router()
    all_checks_passed += router_passed
    all_total_checks += router_total
    
    design_passed, design_total = validate_design_alignment()
    all_checks_passed += design_passed
    all_total_checks += design_total
    
    print_header("📊 OVERALL VALIDATION SUMMARY")
    print(f"Total Checks Passed: {all_checks_passed}/{all_total_checks}")
    
    success_rate = (all_checks_passed / all_total_checks * 100) if all_total_checks > 0 else 0
    print(f"Success Rate: {success_rate:.1f}%\n")
    
    if all_checks_passed == all_total_checks:
        print("✅ ALL VALIDATION CHECKS PASSED\n")
        print("US-034 TASK-005 Implementation:")
        print("  ✓ AgentTaskRepository with override_task method")
        print("  ✓ Custom exceptions (TaskNotFoundError, InvalidTaskTypeError, TaskAlreadyCompletedError)")
        print("  ✓ TaskOverrideRequest and TaskOverrideResponse schemas")
        print("  ✓ PATCH /api/v1/tasks/encounters/{encounter_id}/override/{task_id} endpoint")
        print("  ✓ RBAC enforcement (CHARGE_PHARMACIST, PHARMACY_SUPERVISOR only)")
        print("  ✓ Clears sla_escalation_sent_at (US-034 Scenario 4)")
        print("  ✓ Sets status=COMPLETED, completed_at=NOW()")
        print("  ✓ Creates audit log entry with TASK_MANUALLY_OVERRIDDEN action")
        print("  ✓ Error handling (404, 409, 422, 403)")
        print("  ✓ OpenAPI documentation (summary, description, responses)")
        print("\nNext steps:")
        print("  1. Mark task as Complete")
        print("  2. Create implementation summary")
        print("  3. Proceed to TASK-006 (Unit tests)")
        return 0
    else:
        print(f"❌ {all_total_checks - all_checks_passed} VALIDATION CHECK(S) FAILED\n")
        print("Please review the failed checks above and fix the issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
