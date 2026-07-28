"""Validation script for TASK-006: Alembic Migration — pharmacist_alerts Table.

Validates:
    - Migration file structure and metadata
    - Upgrade function completeness
    - Downgrade function completeness
    - ENUM types definition
    - Table columns and constraints
    - Indexes
"""
import sys
from pathlib import Path


def validate_migration_metadata():
    """Validate migration file metadata and structure."""
    print("✓ Testing migration file metadata...")
    
    migration_path = Path(__file__).parent / "backend" / "alembic" / "versions" / "o9l2k5g80j74_add_pharmacist_alerts_table.py"
    
    assert migration_path.exists(), f"Migration file should exist at {migration_path}"
    code = migration_path.read_text(encoding='utf-8')
    
    # Check metadata
    assert 'revision = "o9l2k5g80j74"' in code, "Should have correct revision ID"
    assert 'down_revision = "n8k1j4f69i63"' in code, "Should revise previous migration"
    assert 'US-031 TASK-006' in code, "Should reference task in docstring"
    assert 'Add pharmacist_alerts table' in code, "Should describe migration purpose"
    print("  ✓ Revision IDs and docstring correct")
    
    # Check imports
    assert 'from __future__ import annotations' in code, "Should have future annotations"
    assert 'import sqlalchemy as sa' in code, "Should import sqlalchemy"
    assert 'from alembic import op' in code, "Should import op"
    assert 'from sqlalchemy.dialects import postgresql' in code, "Should import postgresql dialect"
    print("  ✓ All required imports present")


def validate_enum_types():
    """Validate ENUM type creation."""
    print("\n✓ Testing ENUM types...")
    
    migration_path = Path(__file__).parent / "backend" / "alembic" / "versions" / "o9l2k5g80j74_add_pharmacist_alerts_table.py"
    code = migration_path.read_text(encoding='utf-8')
    
    # Check alert_severity_enum
    assert 'alert_severity_enum = postgresql.ENUM(' in code, "Should create alert_severity_enum"
    assert '"HIGH", "MEDIUM", "LOW"' in code, "Should have severity values"
    assert 'name="alert_severity_enum"' in code, "Should name severity enum"
    assert 'alert_severity_enum.create(op.get_bind(), checkfirst=True)' in code, "Should create severity enum"
    print("  ✓ alert_severity_enum defined correctly")
    
    # Check check_status_enum
    assert 'check_status_enum = postgresql.ENUM(' in code, "Should create check_status_enum"
    assert '"COMPLETE", "INCOMPLETE"' in code, "Should have status values"
    assert 'name="check_status_enum"' in code, "Should name status enum"
    assert 'check_status_enum.create(op.get_bind(), checkfirst=True)' in code, "Should create status enum"
    print("  ✓ check_status_enum defined correctly")


def validate_table_creation():
    """Validate table creation in upgrade function."""
    print("\n✓ Testing table creation...")
    
    migration_path = Path(__file__).parent / "backend" / "alembic" / "versions" / "o9l2k5g80j74_add_pharmacist_alerts_table.py"
    code = migration_path.read_text(encoding='utf-8')
    
    # Check table creation
    assert 'op.create_table(' in code, "Should create table"
    assert '"pharmacist_alerts"' in code, "Should name table correctly"
    print("  ✓ Table creation command present")
    
    # Check columns
    required_columns = [
        '"id"',
        '"encounter_id"',
        '"alert_type"',
        '"severity"',
        '"drug_pair"',
        '"interaction_description"',
        '"source"',
        '"interaction_check_status"',
        '"metadata"',
        '"created_at"',
    ]
    for col in required_columns:
        assert col in code, f"Should have column: {col}"
    print("  ✓ All required columns present")
    
    # Check constraints
    assert 'primary_key=True' in code, "Should have primary key"
    assert 'sa.ForeignKey("encounter.id", ondelete="CASCADE")' in code, "Should have FK with CASCADE"
    assert 'server_default="PHARMACIST_ALERT"' in code, "Should have default for alert_type"
    assert 'server_default="RXNAV"' in code, "Should have default for source"
    assert 'server_default="COMPLETE"' in code, "Should have default for status"
    assert 'server_default=sa.text("NOW()")' in code, "Should have NOW() default for created_at"
    print("  ✓ Constraints and defaults defined")
    
    # Check data types
    assert 'postgresql.UUID(as_uuid=True)' in code, "Should use UUID type"
    assert 'sa.String(64)' in code, "Should use String for alert_type"
    assert 'sa.String(32)' in code, "Should use String for source"
    assert 'postgresql.JSON()' in code, "Should use JSON type"
    assert 'sa.Text()' in code, "Should use Text for description"
    assert 'sa.DateTime(timezone=True)' in code, "Should use DateTime with timezone"
    print("  ✓ Data types correct")


def validate_indexes():
    """Validate index creation."""
    print("\n✓ Testing index creation...")
    
    migration_path = Path(__file__).parent / "backend" / "alembic" / "versions" / "o9l2k5g80j74_add_pharmacist_alerts_table.py"
    code = migration_path.read_text(encoding='utf-8')
    
    # Check encounter_id index
    assert 'op.create_index(' in code, "Should create indexes"
    assert '"ix_pharmacist_alerts_encounter_id"' in code, "Should create encounter_id index"
    assert '["encounter_id"]' in code, "Should index encounter_id column"
    print("  ✓ encounter_id index defined")
    
    # Check severity index
    assert '"ix_pharmacist_alerts_severity"' in code, "Should create severity index"
    assert '["severity"]' in code, "Should index severity column"
    print("  ✓ severity index defined")


def validate_downgrade():
    """Validate downgrade function."""
    print("\n✓ Testing downgrade function...")
    
    migration_path = Path(__file__).parent / "backend" / "alembic" / "versions" / "o9l2k5g80j74_add_pharmacist_alerts_table.py"
    code = migration_path.read_text(encoding='utf-8')
    
    # Check downgrade function
    assert 'def downgrade() -> None:' in code, "Should have downgrade function"
    print("  ✓ Downgrade function present")
    
    # Check index drops
    assert 'op.drop_index(' in code, "Should drop indexes"
    assert 'op.drop_index(\n        "ix_pharmacist_alerts_severity"' in code, "Should drop severity index"
    assert 'op.drop_index(\n        "ix_pharmacist_alerts_encounter_id"' in code, "Should drop encounter_id index"
    print("  ✓ Index drops present")
    
    # Check table drop
    assert 'op.drop_table("pharmacist_alerts")' in code, "Should drop table"
    print("  ✓ Table drop present")
    
    # Check enum drops
    assert 'op.execute("DROP TYPE IF EXISTS check_status_enum")' in code, "Should drop check_status_enum"
    assert 'op.execute("DROP TYPE IF EXISTS alert_severity_enum")' in code, "Should drop alert_severity_enum"
    print("  ✓ ENUM drops present")
    
    # Verify order (indexes → table → enums)
    lines = code.split('\n')
    drop_index_line = next(i for i, line in enumerate(lines) if 'op.drop_index(' in line)
    drop_table_line = next(i for i, line in enumerate(lines) if 'op.drop_table("pharmacist_alerts")' in line)
    drop_enum_line = next(i for i, line in enumerate(lines) if 'DROP TYPE IF EXISTS check_status_enum' in line)
    
    assert drop_index_line < drop_table_line < drop_enum_line, "Should drop in correct order: indexes → table → enums"
    print("  ✓ Downgrade operations in correct order")


def validate_revision_chain():
    """Validate revision chain integrity."""
    print("\n✓ Testing revision chain...")
    
    migration_path = Path(__file__).parent / "backend" / "alembic" / "versions" / "o9l2k5g80j74_add_pharmacist_alerts_table.py"
    code = migration_path.read_text(encoding='utf-8')
    
    # Check this migration's revision
    assert 'revision = "o9l2k5g80j74"' in code, "Should have unique revision ID"
    
    # Check it revises the previous migration
    assert 'down_revision = "n8k1j4f69i63"' in code, "Should revise n8k1j4f69i63 (medication reconciliation)"
    
    # Verify previous migration exists
    prev_migration_path = Path(__file__).parent / "backend" / "alembic" / "versions" / "n8k1j4f69i63_add_medication_reconciliation_fields.py"
    assert prev_migration_path.exists(), "Previous migration should exist"
    print("  ✓ Revision chain valid (revises n8k1j4f69i63)")


def validate_models_import():
    """Validate PharmacistAlert is imported in models __init__.py."""
    print("\n✓ Testing models __init__.py import...")
    
    models_init_path = Path(__file__).parent / "backend" / "app" / "models" / "__init__.py"
    code = models_init_path.read_text(encoding='utf-8')
    
    # Check import
    assert 'from app.models.pharmacist_alert import PharmacistAlert' in code, "Should import PharmacistAlert"
    assert '"PharmacistAlert"' in code, "Should export PharmacistAlert in __all__"
    print("  ✓ PharmacistAlert imported and exported")


def main():
    """Run all validation tests."""
    print("=" * 70)
    print("TASK-006 Validation: Alembic Migration — pharmacist_alerts Table")
    print("=" * 70)
    
    try:
        validate_migration_metadata()
        validate_enum_types()
        validate_table_creation()
        validate_indexes()
        validate_downgrade()
        validate_revision_chain()
        validate_models_import()
        
        print("\n" + "=" * 70)
        print("✅ ALL VALIDATION CHECKS PASSED")
        print("=" * 70)
        print("\nValidation Summary:")
        print("  ✓ Migration file created with correct revision IDs")
        print("  ✓ Two ENUM types created (alert_severity_enum, check_status_enum)")
        print("  ✓ pharmacist_alerts table with 10 columns")
        print("  ✓ Foreign key to encounter with CASCADE delete")
        print("  ✓ Two indexes created (encounter_id, severity)")
        print("  ✓ Downgrade function properly reverses all changes")
        print("  ✓ Revision chain valid (revises n8k1j4f69i63)")
        print("  ✓ PharmacistAlert model imported in models/__init__.py")
        print("\nAcceptance Criteria Coverage:")
        print("  ✓ AC Scenario 1: pharmacist_alerts table schema defined")
        print("\nDefinition of Done:")
        print("  ✓ Migration file committed to version control (ready)")
        print("  ℹ alembic upgrade head — requires DATABASE_URL")
        print("  ℹ Downgrade path — requires DATABASE_URL for testing")
        print("\nNext Steps:")
        print("  1. Set DATABASE_URL environment variable")
        print("  2. Run: alembic upgrade head")
        print("  3. Verify table in PostgreSQL: \\d pharmacist_alerts")
        print("  4. Test downgrade: alembic downgrade -1")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
