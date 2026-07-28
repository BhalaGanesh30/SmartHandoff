#!/usr/bin/env python3
"""Validation script for US-034 TASK-004: ChargePharmacistEscalationPublisher with Pydantic Schema.

Validates:
1. ChargePharmacistEscalationPayload Pydantic schema exists
2. Schema contains all required fields
3. Publisher uses schema for payload creation
4. Publisher uses model_dump_json() for serialization
5. priority="HIGH" set as Pub/Sub message attribute
6. future.result(timeout=10) for error handling
7. No PHI in logs
8. Export from __init__.py
"""
import ast
import re
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


def validate_pydantic_schema() -> tuple[int, int]:
    """Validate ChargePharmacistEscalationPayload Pydantic schema."""
    schema_path = Path("services/sla-monitor/app/publisher/schemas.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("1. PYDANTIC SCHEMA VALIDATION")
    
    if not schema_path.exists():
        print_result("schemas.py file exists", False)
        return 0, 1
    
    print_result("schemas.py file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with schema_path.open("r") as f:
        content = f.read()
    
    # Check for ChargePharmacistEscalationPayload class
    total_checks += 1
    has_class = "class ChargePharmacistEscalationPayload(BaseModel):" in content
    print_result("ChargePharmacistEscalationPayload(BaseModel) class defined", has_class)
    if has_class:
        checks_passed += 1
    else:
        return checks_passed, total_checks
    
    # Check required fields
    required_fields = [
        "notification_type",
        "priority",
        "encounter_id",
        "task_id",
        "patient_unit",
        "hours_elapsed",
        "sent_at",
    ]
    
    for field in required_fields:
        total_checks += 1
        has_field = f"{field}:" in content
        print_result(f"Schema has '{field}' field", has_field)
        if has_field:
            checks_passed += 1
    
    # Check Literal types for notification_type and priority
    total_checks += 1
    has_notification_literal = 'Literal["CHARGE_PHARMACIST_ESCALATION"]' in content
    print_result("notification_type uses Literal['CHARGE_PHARMACIST_ESCALATION']", has_notification_literal)
    if has_notification_literal:
        checks_passed += 1
    
    total_checks += 1
    has_priority_literal = 'Literal["HIGH"]' in content
    print_result("priority uses Literal['HIGH']", has_priority_literal)
    if has_priority_literal:
        checks_passed += 1
    
    # Check default for sent_at
    total_checks += 1
    has_sent_at_default = "Field(default_factory" in content or "default_factory=lambda" in content
    print_result("sent_at has default_factory for automatic timestamp", has_sent_at_default)
    if has_sent_at_default:
        checks_passed += 1
    
    # Check imports
    total_checks += 1
    has_pydantic_import = "from pydantic import" in content
    print_result("Imports Pydantic BaseModel and Field", has_pydantic_import)
    if has_pydantic_import:
        checks_passed += 1
    
    total_checks += 1
    has_uuid_import = "from uuid import UUID" in content
    print_result("Imports UUID type", has_uuid_import)
    if has_uuid_import:
        checks_passed += 1
    
    print(f"\n📊 Pydantic Schema: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_publisher_uses_schema() -> tuple[int, int]:
    """Validate ChargePharmacistEscalationPublisher uses Pydantic schema."""
    publisher_path = Path("services/sla-monitor/app/publisher/charge_pharmacist_escalation_publisher.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("2. PUBLISHER SCHEMA USAGE VALIDATION")
    
    if not publisher_path.exists():
        print_result("charge_pharmacist_escalation_publisher.py file exists", False)
        return 0, 1
    
    print_result("charge_pharmacist_escalation_publisher.py file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with publisher_path.open("r") as f:
        content = f.read()
    
    # Check imports schema
    total_checks += 1
    imports_schema = "from app.publisher.schemas import ChargePharmacistEscalationPayload" in content
    print_result("Imports ChargePharmacistEscalationPayload from schemas", imports_schema)
    if imports_schema:
        checks_passed += 1
    
    # Check does NOT import json (no longer needed)
    total_checks += 1
    no_json_import = "import json" not in content
    print_result("No longer imports json (uses Pydantic serialization)", no_json_import)
    if no_json_import:
        checks_passed += 1
    
    # Check creates payload with schema
    total_checks += 1
    creates_payload = "ChargePharmacistEscalationPayload(" in content
    print_result("Creates payload using ChargePharmacistEscalationPayload schema", creates_payload)
    if creates_payload:
        checks_passed += 1
    
    # Check uses model_dump_json()
    total_checks += 1
    uses_model_dump_json = "model_dump_json()" in content
    print_result("Uses model_dump_json() for JSON serialization", uses_model_dump_json)
    if uses_model_dump_json:
        checks_passed += 1
    
    # Check does NOT use json.dumps (old pattern)
    total_checks += 1
    no_json_dumps = "json.dumps" not in content
    print_result("No longer uses json.dumps (replaced with model_dump_json)", no_json_dumps)
    if no_json_dumps:
        checks_passed += 1
    
    # Check publish() method parameters
    required_params = ["encounter_id", "task_id", "patient_unit", "hours_elapsed"]
    for param in required_params:
        total_checks += 1
        has_param = f"{param}:" in content or f"{param} =" in content
        print_result(f"publish() has '{param}' parameter", has_param)
        if has_param:
            checks_passed += 1
    
    # Check Pub/Sub attributes
    total_checks += 1
    has_notification_attr = 'notification_type="CHARGE_PHARMACIST_ESCALATION"' in content
    print_result("Sets notification_type message attribute", has_notification_attr)
    if has_notification_attr:
        checks_passed += 1
    
    total_checks += 1
    has_priority_attr = 'priority="HIGH"' in content
    print_result("Sets priority='HIGH' message attribute", has_priority_attr)
    if has_priority_attr:
        checks_passed += 1
    
    # Check future.result(timeout=10)
    total_checks += 1
    has_timeout = "future.result(timeout=10)" in content
    print_result("Uses future.result(timeout=10) for blocking publish", has_timeout)
    if has_timeout:
        checks_passed += 1
    
    # Check error handling
    total_checks += 1
    has_try_except = "try:" in content and "except" in content
    print_result("Has try-except error handling", has_try_except)
    if has_try_except:
        checks_passed += 1
    
    # Check re-raises exception
    total_checks += 1
    # Look for 'raise' after 'except' block - should be standalone raise to re-raise
    except_blocks = content.split("except")
    reraises_exception = False
    if len(except_blocks) > 1:
        # Check if any except block has a standalone 'raise'
        for block in except_blocks[1:]:
            # Look for raise on its own line (re-raise pattern)
            if re.search(r'\n\s+raise\s*$', block, re.MULTILINE):
                reraises_exception = True
                break
    print_result("Re-raises exception after logging", reraises_exception)
    if reraises_exception:
        checks_passed += 1
    
    # Check no PHI in logs
    total_checks += 1
    phi_keywords = ["patient_name", "mrn", "ssn", "date_of_birth", "dob"]
    has_phi = any(keyword in content.lower() for keyword in phi_keywords)
    print_result("No PHI (patient_name, mrn, ssn, dob) in logs", not has_phi)
    if not has_phi:
        checks_passed += 1
    
    print(f"\n📊 Publisher Schema Usage: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_exports() -> tuple[int, int]:
    """Validate __init__.py exports."""
    init_path = Path("services/sla-monitor/app/publisher/__init__.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("3. EXPORT VALIDATION")
    
    if not init_path.exists():
        print_result("__init__.py file exists", False)
        return 0, 1
    
    print_result("__init__.py file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with init_path.open("r") as f:
        content = f.read()
    
    # Check imports ChargePharmacistEscalationPublisher
    total_checks += 1
    imports_publisher = "ChargePharmacistEscalationPublisher" in content
    print_result("Imports ChargePharmacistEscalationPublisher", imports_publisher)
    if imports_publisher:
        checks_passed += 1
    
    # Check exports in __all__
    total_checks += 1
    has_all = "__all__" in content
    print_result("Has __all__ export list", has_all)
    if has_all:
        checks_passed += 1
    
    total_checks += 1
    exports_publisher = '"ChargePharmacistEscalationPublisher"' in content or "'ChargePharmacistEscalationPublisher'" in content
    print_result("ChargePharmacistEscalationPublisher in __all__", exports_publisher)
    if exports_publisher:
        checks_passed += 1
    
    print(f"\n📊 Exports: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_design_references() -> tuple[int, int]:
    """Validate design references and documentation."""
    checks_passed = 0
    total_checks = 0
    
    print_header("4. DESIGN REFERENCE VALIDATION")
    
    schema_path = Path("services/sla-monitor/app/publisher/schemas.py")
    publisher_path = Path("services/sla-monitor/app/publisher/charge_pharmacist_escalation_publisher.py")
    
    # Check schema references US-034
    total_checks += 1
    if schema_path.exists():
        with schema_path.open("r") as f:
            schema_content = f.read()
        has_us034_ref = "US-034" in schema_content
        print_result("schemas.py references US-034", has_us034_ref)
        if has_us034_ref:
            checks_passed += 1
    else:
        print_result("schemas.py references US-034", False)
    
    # Check publisher references US-034
    total_checks += 1
    if publisher_path.exists():
        with publisher_path.open("r") as f:
            publisher_content = f.read()
        has_us034_ref = "US-034" in publisher_content
        print_result("charge_pharmacist_escalation_publisher.py references US-034", has_us034_ref)
        if has_us034_ref:
            checks_passed += 1
    else:
        print_result("charge_pharmacist_escalation_publisher.py references US-034", False)
    
    # Check docstrings present
    total_checks += 1
    if schema_path.exists():
        has_schema_docstring = '"""' in schema_content and "ChargePharmacistEscalationPayload" in schema_content
        print_result("ChargePharmacistEscalationPayload has docstring", has_schema_docstring)
        if has_schema_docstring:
            checks_passed += 1
    else:
        print_result("ChargePharmacistEscalationPayload has docstring", False)
    
    print(f"\n📊 Design References: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def main() -> int:
    """Run all validation checks."""
    print_header("US-034 TASK-004 VALIDATION\nChargePharmacistEscalationPublisher with Pydantic Schema")
    
    all_checks_passed = 0
    all_total_checks = 0
    
    schema_passed, schema_total = validate_pydantic_schema()
    all_checks_passed += schema_passed
    all_total_checks += schema_total
    
    publisher_passed, publisher_total = validate_publisher_uses_schema()
    all_checks_passed += publisher_passed
    all_total_checks += publisher_total
    
    exports_passed, exports_total = validate_exports()
    all_checks_passed += exports_passed
    all_total_checks += exports_total
    
    design_passed, design_total = validate_design_references()
    all_checks_passed += design_passed
    all_total_checks += design_total
    
    print_header("📊 OVERALL VALIDATION SUMMARY")
    print(f"Total Checks Passed: {all_checks_passed}/{all_total_checks}")
    
    success_rate = (all_checks_passed / all_total_checks * 100) if all_total_checks > 0 else 0
    print(f"Success Rate: {success_rate:.1f}%\n")
    
    if all_checks_passed == all_total_checks:
        print("✅ ALL VALIDATION CHECKS PASSED\n")
        print("US-034 TASK-004 Implementation:")
        print("  ✓ ChargePharmacistEscalationPayload Pydantic schema created")
        print("  ✓ Schema contains all required fields with correct types")
        print("  ✓ notification_type and priority use Literal types")
        print("  ✓ sent_at has automatic timestamp default")
        print("  ✓ Publisher uses schema for payload creation")
        print("  ✓ Publisher uses model_dump_json() for serialization")
        print("  ✓ priority='HIGH' set as Pub/Sub message attribute")
        print("  ✓ future.result(timeout=10) for error handling")
        print("  ✓ No PHI in logs")
        print("  ✓ ChargePharmacistEscalationPublisher exported from __init__.py")
        print("\nNext steps:")
        print("  1. Mark task as Complete")
        print("  2. Create implementation summary")
        print("  3. Proceed to TASK-005 (Override endpoint) or TASK-006 (Unit tests)")
        return 0
    else:
        print(f"❌ {all_total_checks - all_checks_passed} VALIDATION CHECK(S) FAILED\n")
        print("Please review the failed checks above and fix the issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
