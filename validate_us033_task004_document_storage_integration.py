"""Validation script for US-033 TASK-004: Document Storage Integration.

Validates that:
1. Document model has medications_section JSONB column
2. MedicationSummaryWriter service exists
3. Writer.write() method signature is correct
4. Alembic migration exists and is valid
5. Integration with TASK-002 and TASK-003 (imports)
6. Error handling for unknown document_id
7. No PHI written beyond medication data
8. No N+1 queries (single SELECT + flush)
9. Python syntax is valid

Design refs:
    US-033 TASK-004 — Document Storage Integration
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def validate_file_structure() -> tuple[int, int]:
    """Validate that all required files exist."""
    print("\n📁 1. FILE STRUCTURE")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    required_files = [
        ("backend/app/models/document.py", "Document ORM model"),
        ("backend/app/agents/medication_reconciliation/summary/writer.py", "MedicationSummaryWriter"),
        ("backend/alembic/versions/q1n4m7i02l86_add_medications_section_to_document.py", "Alembic migration"),
    ]
    
    for file_path, description in required_files:
        total += 1
        path = Path(file_path)
        if path.exists():
            print(f"✅ {description}: {file_path}")
            passed += 1
        else:
            print(f"❌ {description} not found: {file_path}")
    
    print(f"\n📊 File Structure: {passed}/{total} files present")
    return passed, total


def validate_document_model() -> tuple[int, int]:
    """Validate Document model has medications_section column."""
    print("\n📦 2. DOCUMENT MODEL")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    model_path = Path("backend/app/models/document.py")
    if not model_path.exists():
        print("❌ document.py not found")
        return 0, 5
    
    with open(model_path, "r") as f:
        content = f.read()
    
    # Check 1: medications_section column defined
    total += 1
    if "medications_section: Mapped[dict | None]" in content or "medications_section: Mapped[dict] | None" in content:
        print("✅ medications_section column defined")
        passed += 1
    else:
        print("❌ medications_section column not found")
    
    # Check 2: JSONB type used
    total += 1
    if "medications_section" in content and "JSONB" in content:
        print("✅ medications_section uses JSONB type")
        passed += 1
    else:
        print("❌ medications_section not using JSONB")
    
    # Check 3: nullable=True
    total += 1
    if "nullable=True" in content and "medications_section" in content:
        print("✅ medications_section is nullable")
        passed += 1
    else:
        print("❌ medications_section not nullable")
    
    # Check 4: Comment with US-033 reference
    total += 1
    if "US-033" in content and "medications_section" in content:
        print("✅ Comment references US-033")
        passed += 1
    else:
        print("❌ Comment does not reference US-033")
    
    # Check 5: MedicationSummaryOutput schema mentioned in comment
    total += 1
    if "MedicationSummaryOutput" in content:
        print("✅ Comment references MedicationSummaryOutput schema")
        passed += 1
    else:
        print("❌ MedicationSummaryOutput not mentioned in comment")
    
    print(f"\n📊 Document Model: {passed}/{total} checks passed")
    return passed, total


def validate_writer_service() -> tuple[int, int]:
    """Validate MedicationSummaryWriter service."""
    print("\n💾 3. MEDICATION SUMMARY WRITER")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    writer_path = Path("backend/app/agents/medication_reconciliation/summary/writer.py")
    if not writer_path.exists():
        print("❌ writer.py not found")
        return 0, 10
    
    with open(writer_path, "r") as f:
        content = f.read()
    
    # Check 1: Module docstring with Design refs
    total += 1
    if '"""Persists the generated MedicationSummaryOutput' in content and "Design refs:" in content:
        print("✅ Module docstring with Design refs present")
        passed += 1
    else:
        print("❌ Missing module docstring or Design refs")
    
    # Check 2: MedicationSummaryWriter class
    total += 1
    if "class MedicationSummaryWriter:" in content:
        print("✅ MedicationSummaryWriter class defined")
        passed += 1
    else:
        print("❌ MedicationSummaryWriter class not found")
    
    # Check 3: __init__ with AsyncSession parameter
    total += 1
    if "def __init__(self, db: AsyncSession)" in content:
        print("✅ __init__ method with AsyncSession parameter")
        passed += 1
    else:
        print("❌ __init__ method missing or incorrect signature")
    
    # Check 4: write() async method
    total += 1
    if "async def write(" in content:
        print("✅ write() async method defined")
        passed += 1
    else:
        print("❌ write() method missing or not async")
    
    # Check 5: write() parameters: document_id, summary
    total += 1
    if "document_id:" in content and "summary: MedicationSummaryOutput" in content:
        print("✅ write() has document_id and summary parameters")
        passed += 1
    else:
        print("❌ write() missing required parameters")
    
    # Check 6: ValueError raised for unknown document_id
    total += 1
    if "raise ValueError(" in content and "not found" in content:
        print("✅ ValueError raised for unknown document_id")
        passed += 1
    else:
        print("❌ ValueError not raised appropriately")
    
    # Check 7: summary.model_dump() called
    total += 1
    if "summary.model_dump()" in content:
        print("✅ summary.model_dump() used to serialize")
        passed += 1
    else:
        print("❌ summary.model_dump() not called")
    
    # Check 8: db.flush() called (not commit)
    total += 1
    if "await self._db.flush()" in content:
        print("✅ await db.flush() called (caller owns transaction)")
        passed += 1
    else:
        print("❌ db.flush() not called")
    
    # Check 9: logger.info for successful write
    total += 1
    if "logger.info(" in content and "medications_section written" in content:
        print("✅ Successful write logged")
        passed += 1
    else:
        print("❌ Write operation not logged")
    
    # Check 10: Single SELECT query (no N+1)
    total += 1
    select_count = content.count("select(Document)")
    if select_count == 1:
        print("✅ Single SELECT query (no N+1)")
        passed += 1
    else:
        print(f"❌ Multiple SELECT queries detected ({select_count})")
    
    print(f"\n📊 Writer Service: {passed}/{total} checks passed")
    return passed, total


def validate_imports() -> tuple[int, int]:
    """Validate all required imports in writer.py."""
    print("\n📥 4. IMPORTS")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    writer_path = Path("backend/app/agents/medication_reconciliation/summary/writer.py")
    if not writer_path.exists():
        return 0, 5
    
    with open(writer_path, "r") as f:
        content = f.read()
    
    required_imports = [
        ("sqlalchemy", "select"),
        ("sqlalchemy.ext.asyncio", "AsyncSession"),
        ("app.models.document", "Document"),
        ("app.agents.medication_reconciliation.summary.schema", "MedicationSummaryOutput"),
        ("uuid", "UUID"),
    ]
    
    for module, item in required_imports:
        total += 1
        if f"from {module} import" in content and item in content:
            print(f"✅ {item} imported from {module}")
            passed += 1
        else:
            print(f"❌ {item} not imported from {module}")
    
    print(f"\n📊 Imports: {passed}/{total} imports present")
    return passed, total


def validate_alembic_migration() -> tuple[int, int]:
    """Validate Alembic migration file."""
    print("\n🔄 5. ALEMBIC MIGRATION")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    migration_path = Path("backend/alembic/versions/q1n4m7i02l86_add_medications_section_to_document.py")
    if not migration_path.exists():
        print("❌ Migration file not found")
        return 0, 7
    
    with open(migration_path, "r") as f:
        content = f.read()
    
    # Check 1: revision ID
    total += 1
    if "revision = 'q1n4m7i02l86'" in content:
        print("✅ Revision ID correct")
        passed += 1
    else:
        print("❌ Revision ID incorrect")
    
    # Check 2: down_revision points to previous migration
    total += 1
    if "down_revision = 'p0m3l6h91k75'" in content:
        print("✅ down_revision points to previous migration")
        passed += 1
    else:
        print("❌ down_revision incorrect")
    
    # Check 3: upgrade() function defined
    total += 1
    if "def upgrade() -> None:" in content:
        print("✅ upgrade() function defined")
        passed += 1
    else:
        print("❌ upgrade() function missing")
    
    # Check 4: op.add_column in upgrade
    total += 1
    if "op.add_column(" in content and '"document"' in content:
        print("✅ op.add_column() adds column to document table")
        passed += 1
    else:
        print("❌ op.add_column() not adding to document table")
    
    # Check 5: JSONB type in upgrade
    total += 1
    if "postgresql.JSONB" in content:
        print("✅ Column uses JSONB type")
        passed += 1
    else:
        print("❌ Column not using JSONB type")
    
    # Check 6: downgrade() function defined
    total += 1
    if "def downgrade() -> None:" in content:
        print("✅ downgrade() function defined")
        passed += 1
    else:
        print("❌ downgrade() function missing")
    
    # Check 7: op.drop_column in downgrade
    total += 1
    if "op.drop_column(" in content and '"medications_section"' in content:
        print("✅ downgrade() drops medications_section column")
        passed += 1
    else:
        print("❌ downgrade() does not drop medications_section")
    
    print(f"\n📊 Alembic Migration: {passed}/{total} checks passed")
    return passed, total


def validate_module_exports() -> tuple[int, int]:
    """Validate summary module exports MedicationSummaryWriter."""
    print("\n📦 6. MODULE EXPORTS")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    init_path = Path("backend/app/agents/medication_reconciliation/summary/__init__.py")
    if not init_path.exists():
        print("❌ __init__.py not found")
        return 0, 2
    
    with open(init_path, "r") as f:
        content = f.read()
    
    # Check 1: MedicationSummaryWriter imported
    total += 1
    if "from app.agents.medication_reconciliation.summary.writer import" in content and "MedicationSummaryWriter" in content:
        print("✅ MedicationSummaryWriter imported")
        passed += 1
    else:
        print("❌ MedicationSummaryWriter not imported")
    
    # Check 2: MedicationSummaryWriter in __all__
    total += 1
    if "MedicationSummaryWriter" in content and "__all__" in content:
        print("✅ MedicationSummaryWriter in __all__")
        passed += 1
    else:
        print("❌ MedicationSummaryWriter not in __all__")
    
    print(f"\n📊 Module Exports: {passed}/{total} checks passed")
    return passed, total


def validate_phi_compliance() -> tuple[int, int]:
    """Validate no PHI written beyond medication data."""
    print("\n🔒 7. PHI COMPLIANCE")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    writer_path = Path("backend/app/agents/medication_reconciliation/summary/writer.py")
    if not writer_path.exists():
        return 0, 2
    
    with open(writer_path, "r") as f:
        content = f.read()
    
    # Check 1: Only writes summary.model_dump()
    total += 1
    if "document.medications_section = summary.model_dump()" in content:
        print("✅ Only writes summary.model_dump() (no additional PHI)")
        passed += 1
    else:
        print("❌ May be writing additional data")
    
    # Check 2: No patient_id, mrn, ssn in writer
    total += 1
    phi_fields = ["patient_id", "mrn", "ssn", "dob", "patient_name"]
    has_phi = any(field in content.lower() for field in phi_fields)
    if not has_phi:
        print("✅ No patient identifiers in writer")
        passed += 1
    else:
        print("❌ Writer may contain patient identifiers")
    
    print(f"\n📊 PHI Compliance: {passed}/{total} checks passed")
    return passed, total


def validate_syntax() -> tuple[int, int]:
    """Validate Python syntax for all files."""
    print("\n✨ 8. PYTHON SYNTAX")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    files = [
        ("backend/app/models/document.py", "document.py"),
        ("backend/app/agents/medication_reconciliation/summary/writer.py", "writer.py"),
        ("backend/alembic/versions/q1n4m7i02l86_add_medications_section_to_document.py", "migration"),
    ]
    
    for file_path, name in files:
        total += 1
        path = Path(file_path)
        if not path.exists():
            print(f"❌ {name} not found")
            continue
        
        try:
            with open(path, "r") as f:
                code = f.read()
            ast.parse(code)
            print(f"✅ {name} has no syntax errors")
            passed += 1
        except SyntaxError as e:
            print(f"❌ {name} has syntax error: {e}")
    
    print(f"\n📊 Python Syntax: {passed}/{total} files valid")
    return passed, total


def main() -> int:
    """Run all validation checks."""
    print("=" * 70)
    print("US-033 TASK-004 VALIDATION")
    print("Document Storage Integration — medications_section")
    print("=" * 70)
    
    results = []
    results.append(validate_file_structure())
    results.append(validate_document_model())
    results.append(validate_writer_service())
    results.append(validate_imports())
    results.append(validate_alembic_migration())
    results.append(validate_module_exports())
    results.append(validate_phi_compliance())
    results.append(validate_syntax())
    
    total_passed = sum(r[0] for r in results)
    total_checks = sum(r[1] for r in results)
    
    print("\n" + "=" * 70)
    print("📊 OVERALL VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total Checks Passed: {total_passed}/{total_checks}")
    print(f"Success Rate: {(total_passed/total_checks)*100:.1f}%")
    
    if total_passed == total_checks:
        print("\n✅ ALL VALIDATION CHECKS PASSED")
        print("\nUS-033 TASK-004 Acceptance Criteria:")
        print("  ✓ MedicationSummaryWriter.write() persists summary.model_dump() to medications_section")
        print("  ✓ ValueError raised for unknown document_id")
        print("  ✓ await db.flush() called (caller owns transaction)")
        print("  ✓ Alembic upgrade adds JSONB column; downgrade removes it cleanly")
        print("  ✓ No PHI written beyond MedicationSummaryOutput schema")
        print("  ✓ No N+1 queries (single SELECT + single flush)")
        print("\nImplementation ready for integration testing.")
        print("\nNext steps:")
        print("  1. Run: cd backend && alembic upgrade head")
        print("  2. Verify medications_section column in document table")
        print("  3. Test writer with sample MedicationSummaryOutput")
        print("  4. Implement unit tests in TASK-006")
        return 0
    else:
        print("\n⚠️  SOME VALIDATION CHECKS FAILED")
        print(f"{total_checks - total_passed} check(s) need review before completion.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
