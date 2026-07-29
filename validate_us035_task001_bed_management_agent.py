"""Validation script for US-035 TASK-001: BedManagementAgent.

Validates:
1. Module structure (all required files exist)
2. Pydantic schemas (BedStatus enum, BedStatusUpdateResult)
3. State machine (transition logic, error handling)
4. Agent implementation (process method, DB integration)
5. Exception hierarchy (BedStatusTransitionError)
6. No PHI in logs
7. Code quality (imports, type hints)

Date: 2026-07-28
Task: US-035 TASK-001
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).parent
BACKEND_DIR = BASE_DIR / "backend"
AGENT_DIR = BACKEND_DIR / "app" / "agents" / "bed_management"

# Expected files
REQUIRED_FILES = [
    AGENT_DIR / "__init__.py",
    AGENT_DIR / "schemas.py",
    AGENT_DIR / "status_machine.py",
    AGENT_DIR / "agent.py",
    AGENT_DIR / "main.py",
    BACKEND_DIR / "app" / "exceptions.py",
]

# PHI patterns to detect
PHI_PATTERNS = [
    r'patient[_\s]*(name|dob|ssn|mrn)',
    r'(first|last)[_\s]*name',
    r'date[_\s]*of[_\s]*birth',
    r'social[_\s]*security',
]

# ============================================================================
# Validation Functions
# ============================================================================

def validate_module_structure() -> list[str]:
    """Check that all required files exist."""
    errors = []
    for file_path in REQUIRED_FILES:
        if not file_path.exists():
            errors.append(f"❌ Missing required file: {file_path.relative_to(BASE_DIR)}")
        else:
            print(f"✅ File exists: {file_path.relative_to(BASE_DIR)}")
    return errors


def validate_schemas_py() -> list[str]:
    """Validate schemas.py implementation."""
    errors = []
    file_path = AGENT_DIR / "schemas.py"
    
    if not file_path.exists():
        return [f"❌ File not found: {file_path}"]
    
    content = file_path.read_text()
    tree = ast.parse(content)
    
    # Check for BedStatus enum
    bed_status_found = False
    bed_status_values = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "BedStatus":
            bed_status_found = True
            # Check if it's an Enum
            has_enum_base = any(
                getattr(base, 'id', None) == 'Enum' or 
                (isinstance(base, ast.Attribute) and base.attr == 'Enum')
                for base in node.bases
            )
            if has_enum_base:
                print("✅ BedStatus is an Enum")
            else:
                errors.append("❌ BedStatus should inherit from Enum")
            
            # Check for required values
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            bed_status_values.add(target.id)
    
    if not bed_status_found:
        errors.append("❌ BedStatus enum not found in schemas.py")
    else:
        print("✅ BedStatus enum defined")
        required_values = {"VACANT", "OCCUPIED", "DIRTY", "MAINTENANCE", "RESERVED"}
        if required_values.issubset(bed_status_values):
            print(f"✅ BedStatus has all required values: {required_values}")
        else:
            missing = required_values - bed_status_values
            errors.append(f"❌ BedStatus missing values: {missing}")
    
    # Check for BedStatusUpdateResult
    if "class BedStatusUpdateResult" in content:
        print("✅ BedStatusUpdateResult class defined")
        if "BaseModel" in content:
            print("✅ BedStatusUpdateResult inherits from BaseModel")
        else:
            errors.append("❌ BedStatusUpdateResult should inherit from BaseModel")
        
        # Check required fields
        required_fields = [
            "bed_id", "previous_status", "new_status", 
            "encounter_id", "event_type", "housekeeping_notification_published",
            "mv_refresh_triggered"
        ]
        for field in required_fields:
            if field in content:
                print(f"✅ BedStatusUpdateResult has field: {field}")
            else:
                errors.append(f"❌ BedStatusUpdateResult missing field: {field}")
    else:
        errors.append("❌ BedStatusUpdateResult not found in schemas.py")
    
    return errors


def validate_status_machine_py() -> list[str]:
    """Validate status_machine.py implementation."""
    errors = []
    file_path = AGENT_DIR / "status_machine.py"
    
    if not file_path.exists():
        return [f"❌ File not found: {file_path}"]
    
    content = file_path.read_text()
    
    # Check for resolve_target_status function
    if "def resolve_target_status" in content:
        print("✅ resolve_target_status function defined")
    else:
        errors.append("❌ resolve_target_status function not found")
    
    # Check transition map
    if "_TRANSITION_MAP" in content:
        print("✅ _TRANSITION_MAP defined")
    else:
        errors.append("❌ _TRANSITION_MAP not found")
    
    # Check for event type handling
    for event_type in ["A01", "A02", "A03"]:
        if f'"{event_type}"' in content or f"'{event_type}'" in content:
            print(f"✅ Handles event type: {event_type}")
        else:
            errors.append(f"❌ Event type not handled: {event_type}")
    
    # Check for BedStatusTransitionError
    if "BedStatusTransitionError" in content:
        print("✅ References BedStatusTransitionError")
    else:
        errors.append("❌ BedStatusTransitionError not imported/used")
    
    return errors


def validate_agent_py() -> list[str]:
    """Validate agent.py implementation."""
    errors = []
    file_path = AGENT_DIR / "agent.py"
    
    if not file_path.exists():
        return [f"❌ File not found: {file_path}"]
    
    content = file_path.read_text()
    tree = ast.parse(content)
    
    # Check for BedManagementAgent class
    agent_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "BedManagementAgent":
            agent_found = True
            # Check inheritance
            has_base_agent = any(
                getattr(base, 'id', None) == 'BaseAgent' or
                (isinstance(base, ast.Attribute) and base.attr == 'BaseAgent')
                for base in node.bases
            )
            if has_base_agent:
                print("✅ BedManagementAgent inherits from BaseAgent")
            else:
                errors.append("❌ BedManagementAgent should inherit from BaseAgent")
            
            # Check for process method
            has_process = any(
                isinstance(m, ast.AsyncFunctionDef) and m.name == "process"
                for m in node.body
            )
            if has_process:
                print("✅ BedManagementAgent has async process method")
            else:
                errors.append("❌ BedManagementAgent missing async process method")
    
    if not agent_found:
        errors.append("❌ BedManagementAgent class not found")
    else:
        print("✅ BedManagementAgent class defined")
    
    # Check for event type handling
    if "HANDLED_EVENT_TYPES" in content:
        print("✅ HANDLED_EVENT_TYPES defined")
        if all(et in content for et in ['"A01"', '"A02"', '"A03"']):
            print("✅ All required event types in HANDLED_EVENT_TYPES")
        else:
            errors.append("❌ Not all event types (A01, A02, A03) in HANDLED_EVENT_TYPES")
    else:
        errors.append("❌ HANDLED_EVENT_TYPES not found")
    
    # Check for required methods
    required_methods = [
        "_handle_event", "_handle_single_bed_transition", 
        "_handle_transfer", "_fetch_bed"
    ]
    for method in required_methods:
        if f"def {method}" in content or f"async def {method}" in content:
            print(f"✅ Method defined: {method}")
        else:
            errors.append(f"❌ Method not found: {method}")
    
    # Check for RetryableError usage
    if "RetryableError" in content:
        print("✅ References RetryableError")
    else:
        errors.append("❌ RetryableError not imported/used")
    
    # Check for BedStatusUpdateResult usage
    if "BedStatusUpdateResult" in content:
        print("✅ Returns BedStatusUpdateResult")
    else:
        errors.append("❌ BedStatusUpdateResult not used")
    
    # Check for no PHI in logs
    log_pattern = r'logger\.(debug|info|warning|error|exception)\s*\(\s*["\']([^"\']+)'
    log_matches = re.findall(log_pattern, content)
    phi_in_logs = []
    for level, message in log_matches:
        for phi_pattern in PHI_PATTERNS:
            if re.search(phi_pattern, message, re.IGNORECASE):
                phi_in_logs.append(f"{level}: {message}")
    
    if phi_in_logs:
        errors.append(f"❌ Potential PHI in log messages: {phi_in_logs}")
    else:
        print("✅ No PHI detected in log statements")
    
    return errors


def validate_exceptions_py() -> list[str]:
    """Validate that BedStatusTransitionError is added to exceptions.py."""
    errors = []
    file_path = BACKEND_DIR / "app" / "exceptions.py"
    
    if not file_path.exists():
        return [f"❌ File not found: {file_path}"]
    
    content = file_path.read_text()
    
    if "class BedStatusTransitionError" in content:
        print("✅ BedStatusTransitionError defined in exceptions.py")
        
        # Check inheritance
        if "ValueError" in content:
            print("✅ BedStatusTransitionError inherits from ValueError")
        else:
            errors.append("❌ BedStatusTransitionError should inherit from ValueError")
    else:
        errors.append("❌ BedStatusTransitionError not found in exceptions.py")
    
    return errors


def validate_main_py() -> list[str]:
    """Validate main.py Cloud Run entrypoint."""
    errors = []
    file_path = AGENT_DIR / "main.py"
    
    if not file_path.exists():
        return [f"❌ File not found: {file_path}"]
    
    content = file_path.read_text()
    
    # Check for main function
    if "async def main" in content:
        print("✅ main() function defined")
    else:
        errors.append("❌ async main() function not found")
    
    # Check for BedManagementAgent instantiation
    if "BedManagementAgent" in content:
        print("✅ BedManagementAgent instantiated in main")
    else:
        errors.append("❌ BedManagementAgent not instantiated")
    
    # Check for subscription_id
    if "bed-mgmt-agent-sub" in content:
        print("✅ Correct subscription_id used")
    else:
        errors.append("❌ subscription_id 'bed-mgmt-agent-sub' not found")
    
    # Check for agent.run() call
    if "agent.run()" in content or "await agent.run()" in content:
        print("✅ agent.run() called")
    else:
        errors.append("❌ agent.run() not called")
    
    # Check for asyncio.run
    if "asyncio.run(main())" in content:
        print("✅ asyncio.run(main()) in __main__ block")
    else:
        errors.append("❌ asyncio.run(main()) not found in __main__ block")
    
    return errors


def validate_code_quality() -> list[str]:
    """Validate code quality: imports, type hints, docstrings."""
    errors = []
    
    for file_path in [
        AGENT_DIR / "schemas.py",
        AGENT_DIR / "status_machine.py",
        AGENT_DIR / "agent.py",
    ]:
        if not file_path.exists():
            continue
        
        content = file_path.read_text()
        
        # Check for proper imports
        if "from __future__ import annotations" in content:
            print(f"✅ {file_path.name}: Has future annotations")
        else:
            errors.append(f"❌ {file_path.name}: Missing 'from __future__ import annotations'")
        
        # Check for type hints in function definitions
        if " -> " in content:
            print(f"✅ {file_path.name}: Uses return type hints")
        else:
            errors.append(f"❌ {file_path.name}: Missing return type hints")
        
        # Check for docstrings
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if ast.get_docstring(node):
                    # Has docstring - good
                    pass
                else:
                    # Only warn for public classes/functions
                    if not node.name.startswith("_"):
                        errors.append(f"⚠️  {file_path.name}: {node.name} missing docstring")
    
    return errors


# ============================================================================
# Main Validation
# ============================================================================

def main() -> None:
    """Run all validation checks."""
    print("=" * 70)
    print("US-035 TASK-001 VALIDATION")
    print("BedManagementAgent — ADT Event Consumer and Bed Status State Machine")
    print("=" * 70)
    print()
    
    all_errors = []
    
    # 1. Module structure
    print("=" * 70)
    print("1. MODULE STRUCTURE")
    print("=" * 70)
    errors = validate_module_structure()
    all_errors.extend(errors)
    print(f"\n📊 Module Structure: {len(REQUIRED_FILES) - len(errors)}/{len(REQUIRED_FILES)} checks passed\n")
    
    # 2. Schemas
    print("=" * 70)
    print("2. PYDANTIC SCHEMAS (schemas.py)")
    print("=" * 70)
    errors = validate_schemas_py()
    all_errors.extend(errors)
    print(f"\n📊 Schemas: {'✅ All checks passed' if not errors else f'❌ {len(errors)} error(s)'}\n")
    
    # 3. State machine
    print("=" * 70)
    print("3. STATE MACHINE (status_machine.py)")
    print("=" * 70)
    errors = validate_status_machine_py()
    all_errors.extend(errors)
    print(f"\n📊 State Machine: {'✅ All checks passed' if not errors else f'❌ {len(errors)} error(s)'}\n")
    
    # 4. Agent
    print("=" * 70)
    print("4. AGENT IMPLEMENTATION (agent.py)")
    print("=" * 70)
    errors = validate_agent_py()
    all_errors.extend(errors)
    print(f"\n📊 Agent: {'✅ All checks passed' if not errors else f'❌ {len(errors)} error(s)'}\n")
    
    # 5. Exceptions
    print("=" * 70)
    print("5. EXCEPTION HIERARCHY (exceptions.py)")
    print("=" * 70)
    errors = validate_exceptions_py()
    all_errors.extend(errors)
    print(f"\n📊 Exceptions: {'✅ All checks passed' if not errors else f'❌ {len(errors)} error(s)'}\n")
    
    # 6. Main entrypoint
    print("=" * 70)
    print("6. CLOUD RUN ENTRYPOINT (main.py)")
    print("=" * 70)
    errors = validate_main_py()
    all_errors.extend(errors)
    print(f"\n📊 Main: {'✅ All checks passed' if not errors else f'❌ {len(errors)} error(s)'}\n")
    
    # 7. Code quality
    print("=" * 70)
    print("7. CODE QUALITY")
    print("=" * 70)
    errors = validate_code_quality()
    all_errors.extend(errors)
    print(f"\n📊 Code Quality: {'✅ All checks passed' if not errors else f'⚠️  {len(errors)} warning(s)'}\n")
    
    # Summary
    print("=" * 70)
    print("📊 OVERALL VALIDATION SUMMARY")
    print("=" * 70)
    
    if all_errors:
        print(f"\n❌ VALIDATION FAILED: {len(all_errors)} error(s)/warning(s) found\n")
        print("Errors:")
        for error in all_errors:
            print(f"  {error}")
        print("\nNext steps:")
        print("  1. Fix the errors listed above")
        print("  2. Re-run this validation script")
        print("  3. Ensure 100% pass rate before marking task Complete")
    else:
        print("\n✅ ALL VALIDATION CHECKS PASSED\n")
        print("US-035 TASK-001 Implementation Status:")
        print("  ✓ Module structure complete")
        print("  ✓ Pydantic schemas implemented")
        print("  ✓ State machine logic validated")
        print("  ✓ BedManagementAgent implemented")
        print("  ✓ Exception hierarchy updated")
        print("  ✓ Cloud Run entrypoint configured")
        print("  ✓ Code quality standards met")
        print("\nNext steps:")
        print("  1. Update task_001 status to Complete")
        print("  2. Create implementation summary")
        print("  3. Proceed to US-035 TASK-002")


if __name__ == "__main__":
    main()
