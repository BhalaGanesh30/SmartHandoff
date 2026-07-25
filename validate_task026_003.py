"""Validation script for TASK-026-003: Document Model Completeness Columns

Verifies:
1. Document model has completeness_status and missing_fields columns
2. Alembic migration file exists and has correct structure
3. DocumentRepository has update_completeness() method
4. All imports are correct
5. Column types and constraints match spec
"""

import ast
import pathlib
import sys


def validate_document_model():
    """Verify Document model has new columns with correct types."""
    print("1. Validating Document model...")
    
    model_file = pathlib.Path("backend/app/models/document.py")
    if not model_file.exists():
        print(f"   ✗ {model_file} not found")
        return False
    
    content = model_file.read_text()
    
    # Check JSONB import
    if "from sqlalchemy.dialects.postgresql import JSONB" not in content:
        print("   ✗ Missing JSONB import")
        return False
    print("   ✓ JSONB import present")
    
    # Check completeness_status column
    if "completeness_status: Mapped[str | None]" not in content:
        print("   ✗ completeness_status column missing or wrong type")
        return False
    if "sa.String(20)" not in content:
        print("   ✗ completeness_status should be String(20)")
        return False
    print("   ✓ completeness_status column present with correct type")
    
    # Check missing_fields column
    if "missing_fields: Mapped[list | None]" not in content:
        print("   ✗ missing_fields column missing or wrong type")
        return False
    if "JSONB" not in content or "server_default=\"'[]'::jsonb\"" not in content:
        print("   ✗ missing_fields should be JSONB with default '[]'")
        return False
    print("   ✓ missing_fields column present with correct type")
    
    return True


def validate_migration():
    """Verify Alembic migration exists and has correct structure."""
    print("\n2. Validating Alembic migration...")
    
    migration_file = pathlib.Path("backend/alembic/versions/k5h8g1c46f50_add_completeness_columns_to_document.py")
    if not migration_file.exists():
        print(f"   ✗ {migration_file} not found")
        return False
    print(f"   ✓ Migration file exists")
    
    content = migration_file.read_text()
    
    # Check revision IDs
    if 'revision: str = "k5h8g1c46f50"' not in content:
        print("   ✗ Incorrect revision ID")
        return False
    if 'down_revision: Union[str, None] = "j4g7f0b35e49"' not in content:
        print("   ✗ Incorrect down_revision ID")
        return False
    print("   ✓ Revision IDs correct")
    
    # Check upgrade function
    if "def upgrade() -> None:" not in content:
        print("   ✗ upgrade() function missing")
        return False
    if 'op.add_column(\n        "document",' not in content:
        print("   ✗ upgrade() should add columns to document table")
        return False
    if '"completeness_status"' not in content or '"missing_fields"' not in content:
        print("   ✗ upgrade() should add both completeness_status and missing_fields")
        return False
    print("   ✓ upgrade() function correct")
    
    # Check downgrade function
    if "def downgrade() -> None:" not in content:
        print("   ✗ downgrade() function missing")
        return False
    if 'op.drop_column("document", "missing_fields")' not in content:
        print("   ✗ downgrade() should drop missing_fields")
        return False
    if 'op.drop_column("document", "completeness_status")' not in content:
        print("   ✗ downgrade() should drop completeness_status")
        return False
    print("   ✓ downgrade() function correct")
    
    return True


def validate_repository():
    """Verify DocumentRepository has update_completeness() method."""
    print("\n3. Validating DocumentRepository...")
    
    repo_file = pathlib.Path("backend/app/db/repositories/document_repository.py")
    if not repo_file.exists():
        print(f"   ✗ {repo_file} not found")
        return False
    
    content = repo_file.read_text()
    
    # Check imports
    if "from agents.documentation.completeness_validator import CompletenessResult, CompletenessStatus" not in content:
        print("   ✗ Missing CompletenessResult/CompletenessStatus imports")
        return False
    print("   ✓ Imports present")
    
    # Check method exists
    if "async def update_completeness(" not in content:
        print("   ✗ update_completeness() method missing")
        return False
    print("   ✓ update_completeness() method present")
    
    # Check method signature
    if "document: Document" not in content or "result: CompletenessResult" not in content:
        print("   ✗ update_completeness() has incorrect parameters")
        return False
    print("   ✓ Method signature correct")
    
    # Check status logic
    if "document.completeness_status = result.status.value" not in content:
        print("   ✗ Should set document.completeness_status from result")
        return False
    if "document.missing_fields = result.missing_fields" not in content:
        print("   ✗ Should set document.missing_fields from result")
        return False
    if "if result.status == CompletenessStatus.INCOMPLETE:" not in content:
        print("   ✗ Should check for INCOMPLETE status")
        return False
    if 'document.status = DocumentStatus.DRAFT.value' not in content:
        print("   ✗ Should set status to DRAFT on INCOMPLETE")
        return False
    print("   ✓ Status update logic correct")
    
    # Check commit/refresh
    if "await self._session.commit()" not in content or "await self._session.refresh(document)" not in content:
        print("   ✗ Should commit and refresh document")
        return False
    print("   ✓ Commit and refresh logic present")
    
    return True


def validate_syntax():
    """Check Python syntax in all modified files."""
    print("\n4. Validating Python syntax...")
    
    files_to_check = [
        "backend/app/models/document.py",
        "backend/app/db/repositories/document_repository.py",
        "backend/alembic/versions/k5h8g1c46f50_add_completeness_columns_to_document.py",
    ]
    
    all_valid = True
    for filepath in files_to_check:
        p = pathlib.Path(filepath)
        if not p.exists():
            print(f"   ✗ {filepath} not found")
            all_valid = False
            continue
        
        try:
            ast.parse(p.read_text())
            print(f"   ✓ {filepath}")
        except SyntaxError as e:
            print(f"   ✗ {filepath}: {e}")
            all_valid = False
    
    return all_valid


def main():
    print("=" * 80)
    print("TASK-026-003 Implementation Validation")
    print("=" * 80)
    print()
    
    results = [
        ("Document Model", validate_document_model()),
        ("Alembic Migration", validate_migration()),
        ("DocumentRepository", validate_repository()),
        ("Python Syntax", validate_syntax()),
    ]
    
    print("\n" + "=" * 80)
    print("Validation Summary")
    print("=" * 80)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status:12} {name}")
        if not passed:
            all_passed = False
    
    print("=" * 80)
    
    if all_passed:
        print("\n✓ ALL CHECKS PASSED - TASK-026-003 COMPLETE")
        print("\nFiles Modified:")
        print("  1. backend/app/models/document.py")
        print("  2. backend/app/db/repositories/document_repository.py")
        print("\nFiles Created:")
        print("  3. backend/alembic/versions/k5h8g1c46f50_add_completeness_columns_to_document.py")
        print("\nNext Steps:")
        print("  1. Run migration: cd backend && alembic upgrade head")
        print("  2. Verify database schema: psql -c '\\d document'")
        print("  3. Test with CompletenessValidator integration")
        return 0
    else:
        print("\n✗ VALIDATION FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
