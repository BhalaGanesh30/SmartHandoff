"""Validation script for US-035 TASK-002: BedBoardRefreshService.

Validates:
1. Alembic migration for unique index
2. BedBoardRefreshService implementation
3. Integration with agent entrypoint
4. SQL correctness (REFRESH MATERIALIZED VIEW CONCURRENTLY)
5. Code quality

Date: 2026-07-28
Task: US-035 TASK-002
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).parent
BACKEND_DIR = BASE_DIR / "backend"
AGENT_DIR = BACKEND_DIR / "app" / "agents" / "bed_management"
ALEMBIC_DIR = BACKEND_DIR / "alembic" / "versions"

# Expected files
REQUIRED_FILES = [
    AGENT_DIR / "refresh_service.py",
    AGENT_DIR / "main.py",  # Should be updated from TASK-001
]

# ============================================================================
# Validation Functions
# ============================================================================

def validate_migration_exists() -> list[str]:
    """Check for unique index migration on mv_bed_board."""
    errors = []
    
    if not ALEMBIC_DIR.exists():
        return [f"❌ Alembic versions directory not found: {ALEMBIC_DIR}"]
    
    # Look for migration file with unique index creation
    migration_found = False
    migration_file = None
    
    for file_path in ALEMBIC_DIR.glob("*.py"):
        if file_path.name == "__pycache__":
            continue
        content = file_path.read_text()
        if "uix_mv_bed_board_bed_id" in content or "mv_bed_board" in content and "UNIQUE INDEX" in content:
            migration_found = True
            migration_file = file_path
            print(f"✅ Migration file found: {file_path.name}")
            
            # Check for CREATE UNIQUE INDEX
            if "CREATE UNIQUE INDEX" in content:
                print("✅ Migration creates UNIQUE INDEX")
            else:
                errors.append("❌ Migration missing CREATE UNIQUE INDEX statement")
            
            # Check for CONCURRENTLY
            if "CONCURRENTLY" in content:
                print("✅ Migration uses CONCURRENTLY")
            else:
                errors.append("⚠️  Migration should use CONCURRENTLY for non-blocking creation")
            
            # Check for IF NOT EXISTS
            if "IF NOT EXISTS" in content:
                print("✅ Migration uses IF NOT EXISTS (idempotent)")
            else:
                errors.append("⚠️  Migration should use IF NOT EXISTS for idempotency")
            
            # Check for downgrade
            if "DROP INDEX" in content or "DROP MATERIALIZED VIEW" in content:
                print("✅ Migration has downgrade (DROP INDEX or DROP MATERIALIZED VIEW)")
            else:
                errors.append("❌ Migration missing downgrade logic")
            
            # Check for bed_id column
            if "bed_id" in content:
                print("✅ Index on bed_id column")
            else:
                errors.append("❌ Index should be on bed_id column")
            
            break
    
    if not migration_found:
        errors.append("❌ No migration file found for mv_bed_board unique index")
        print("❌ Migration file not found")
    
    return errors


def validate_refresh_service_py() -> list[str]:
    """Validate refresh_service.py implementation."""
    errors = []
    file_path = AGENT_DIR / "refresh_service.py"
    
    if not file_path.exists():
        return [f"❌ File not found: {file_path}"]
    
    content = file_path.read_text()
    tree = ast.parse(content)
    
    # Check for BedBoardRefreshService class
    service_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "BedBoardRefreshService":
            service_found = True
            print("✅ BedBoardRefreshService class defined")
            
            # Check for required methods
            methods = [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
            
            if "__init__" in methods:
                print("✅ Has __init__ method")
            else:
                errors.append("❌ Missing __init__ method")
            
            if "refresh_async" in methods:
                print("✅ Has refresh_async method")
                # Check if it's async
                for m in node.body:
                    if isinstance(m, ast.AsyncFunctionDef) and m.name == "refresh_async":
                        print("✅ refresh_async is async def")
                        break
                else:
                    errors.append("❌ refresh_async should be async def")
            else:
                errors.append("❌ Missing refresh_async method")
            
            if "refresh_sync" in methods:
                print("✅ Has refresh_sync method")
                # Check if it's async
                for m in node.body:
                    if isinstance(m, ast.AsyncFunctionDef) and m.name == "refresh_sync":
                        print("✅ refresh_sync is async def")
                        break
                else:
                    errors.append("❌ refresh_sync should be async def")
            else:
                errors.append("❌ Missing refresh_sync method")
            
            if "_do_refresh" in methods:
                print("✅ Has _do_refresh helper method")
            else:
                errors.append("⚠️  Consider adding _do_refresh helper method")
            
            break
    
    if not service_found:
        errors.append("❌ BedBoardRefreshService class not found")
    else:
        print("✅ BedBoardRefreshService class found")
    
    # Check for SQL constant
    if "_REFRESH_SQL" in content or "REFRESH MATERIALIZED VIEW" in content:
        print("✅ REFRESH MATERIALIZED VIEW SQL defined")
        
        # Check for CONCURRENTLY
        if "CONCURRENTLY" in content:
            print("✅ SQL uses CONCURRENTLY")
        else:
            errors.append("❌ SQL should use CONCURRENTLY")
        
        # Check for mv_bed_board
        if "mv_bed_board" in content:
            print("✅ SQL targets mv_bed_board")
        else:
            errors.append("❌ SQL should target mv_bed_board")
    else:
        errors.append("❌ REFRESH MATERIALIZED VIEW SQL not found")
    
    # Check for asyncio.create_task (fire-and-forget)
    if "asyncio.create_task" in content:
        print("✅ Uses asyncio.create_task for background refresh")
    else:
        errors.append("⚠️  refresh_async should use asyncio.create_task")
    
    # Check for exception handling
    if "try:" in content and "except" in content:
        print("✅ Has exception handling")
    else:
        errors.append("❌ Missing exception handling for refresh failures")
    
    # Check for logging
    if "logger" in content:
        print("✅ Uses logging")
    else:
        errors.append("⚠️  Should include logging for refresh events")
    
    # Check for future annotations
    if "from __future__ import annotations" in content:
        print("✅ Has future annotations")
    else:
        errors.append("❌ Missing 'from __future__ import annotations'")
    
    # Check for type hints
    if " -> " in content:
        print("✅ Uses return type hints")
    else:
        errors.append("❌ Missing return type hints")
    
    return errors


def validate_main_py_integration() -> list[str]:
    """Validate that main.py imports and uses BedBoardRefreshService."""
    errors = []
    file_path = AGENT_DIR / "main.py"
    
    if not file_path.exists():
        return [f"❌ File not found: {file_path}"]
    
    content = file_path.read_text()
    
    # Check for import
    if "BedBoardRefreshService" in content:
        print("✅ main.py imports BedBoardRefreshService")
    else:
        errors.append("❌ main.py should import BedBoardRefreshService")
    
    # Check for refresh_service import
    if "from app.agents.bed_management.refresh_service import" in content:
        print("✅ Correct import path")
    else:
        errors.append("⚠️  Verify import path for refresh_service")
    
    # Check for instantiation
    if "refresh_service" in content.lower() or "BedBoardRefreshService(" in content:
        print("✅ BedBoardRefreshService instantiated in main")
    else:
        errors.append("❌ BedBoardRefreshService not instantiated in main")
    
    # Check for write session factory
    if "write_session_factory" in content or "get_write_db" in content:
        print("✅ References write session factory")
    else:
        errors.append("⚠️  Should pass write_session_factory to BedBoardRefreshService")
    
    return errors


def validate_code_quality() -> list[str]:
    """Validate code quality standards."""
    errors = []
    file_path = AGENT_DIR / "refresh_service.py"
    
    if not file_path.exists():
        return []
    
    content = file_path.read_text()
    tree = ast.parse(content)
    
    # Check for docstrings
    module_docstring = ast.get_docstring(tree)
    if module_docstring:
        print("✅ Module has docstring")
    else:
        errors.append("⚠️  refresh_service.py should have module docstring")
    
    # Check for class docstrings
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "BedBoardRefreshService":
            if ast.get_docstring(node):
                print("✅ BedBoardRefreshService has docstring")
            else:
                errors.append("⚠️  BedBoardRefreshService should have docstring")
    
    return errors


# ============================================================================
# Main Validation
# ============================================================================

def main() -> None:
    """Run all validation checks."""
    print("=" * 70)
    print("US-035 TASK-002 VALIDATION")
    print("mv_bed_board CONCURRENTLY Refresh Service")
    print("=" * 70)
    print()
    
    all_errors = []
    
    # 1. Migration
    print("=" * 70)
    print("1. ALEMBIC MIGRATION (UNIQUE INDEX)")
    print("=" * 70)
    errors = validate_migration_exists()
    all_errors.extend(errors)
    print(f"\n📊 Migration: {'✅ All checks passed' if not errors else f'❌ {len(errors)} error(s)'}\n")
    
    # 2. Refresh Service
    print("=" * 70)
    print("2. BEDBOARDREFRESHSERVICE (refresh_service.py)")
    print("=" * 70)
    errors = validate_refresh_service_py()
    all_errors.extend(errors)
    print(f"\n📊 Refresh Service: {'✅ All checks passed' if not errors else f'❌ {len(errors)} error(s)'}\n")
    
    # 3. Main.py Integration
    print("=" * 70)
    print("3. AGENT ENTRYPOINT INTEGRATION (main.py)")
    print("=" * 70)
    errors = validate_main_py_integration()
    all_errors.extend(errors)
    print(f"\n📊 Integration: {'✅ All checks passed' if not errors else f'❌ {len(errors)} error(s)'}\n")
    
    # 4. Code Quality
    print("=" * 70)
    print("4. CODE QUALITY")
    print("=" * 70)
    errors = validate_code_quality()
    all_errors.extend(errors)
    print(f"\n📊 Code Quality: {'✅ All checks passed' if not errors else f'⚠️  {len(errors)} warning(s)'}\n")
    
    # Summary
    print("=" * 70)
    print("📊 OVERALL VALIDATION SUMMARY")
    print("=" * 70)
    
    # Filter out warnings (⚠️) for pass/fail determination
    critical_errors = [e for e in all_errors if e.startswith("❌")]
    
    if critical_errors:
        print(f"\n❌ VALIDATION FAILED: {len(critical_errors)} critical error(s) found\n")
        print("Critical Errors:")
        for error in critical_errors:
            print(f"  {error}")
        if len(all_errors) > len(critical_errors):
            print(f"\n⚠️  {len(all_errors) - len(critical_errors)} warning(s):")
            for error in all_errors:
                if error.startswith("⚠️"):
                    print(f"  {error}")
        print("\nNext steps:")
        print("  1. Fix the critical errors listed above")
        print("  2. Re-run this validation script")
        print("  3. Ensure 100% pass rate before marking task Complete")
    else:
        print("\n✅ ALL VALIDATION CHECKS PASSED\n")
        print("US-035 TASK-002 Implementation Status:")
        print("  ✓ Alembic migration for unique index")
        print("  ✓ BedBoardRefreshService implemented")
        print("  ✓ Integration with agent entrypoint")
        print("  ✓ Code quality standards met")
        if all_errors:
            print(f"\n⚠️  {len(all_errors)} warning(s) - non-critical")
        print("\nNext steps:")
        print("  1. Update task_002 status to Complete")
        print("  2. Create implementation summary")
        print("  3. Proceed to US-035 TASK-003")


if __name__ == "__main__":
    main()
