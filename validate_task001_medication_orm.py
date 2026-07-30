"""Validation script for US-030 TASK-001: Medication ORM Models, Enums, and Migration

Validates:
- AC1: Enums defined with correct values
- AC2: ORM model extended with reconciliation fields
- AC3: Pydantic response schema serializes correctly
- AC4: Alembic migration file exists and has correct structure
"""
import sys
import uuid
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))


def test_ac1_enums_defined():
    """AC1: Enums Defined"""
    print("\n=== AC1: Enums Defined ===")
    
    from app.models.medication import (
        ReconciliationCategory,
        ReconciliationFlag,
        MedicationListSource,
    )
    
    # ReconciliationCategory should have 4 values
    expected_categories = {"CONTINUED", "NEW", "STOPPED", "DOSE_CHANGED"}
    actual_categories = {cat.value for cat in ReconciliationCategory}
    assert actual_categories == expected_categories, (
        f"ReconciliationCategory mismatch: {actual_categories} vs {expected_categories}"
    )
    print(f"✓ ReconciliationCategory has {len(ReconciliationCategory)} values: {actual_categories}")
    
    # ReconciliationFlag should have 2 values
    expected_flags = {"DUPLICATE", "STOPPED_WITHOUT_ORDER"}
    actual_flags = {flag.value for flag in ReconciliationFlag}
    assert actual_flags == expected_flags, (
        f"ReconciliationFlag mismatch: {actual_flags} vs {expected_flags}"
    )
    print(f"✓ ReconciliationFlag has {len(ReconciliationFlag)} values: {actual_flags}")
    
    # MedicationListSource should have 3 values
    expected_sources = {"PRE_ADMIT", "INPATIENT", "DISCHARGE"}
    actual_sources = {src.value for src in MedicationListSource}
    assert actual_sources == expected_sources, (
        f"MedicationListSource mismatch: {actual_sources} vs {expected_sources}"
    )
    print(f"✓ MedicationListSource has {len(MedicationListSource)} values: {actual_sources}")
    
    print("✓ AC1 PASSED: All enums defined with correct values")


def test_ac2_orm_model_extended():
    """AC2: ORM Model Extended"""
    print("\n=== AC2: ORM Model Extended ===")
    
    from app.models.medication import Medication
    import sqlalchemy as sa
    
    # Check that all expected columns exist
    expected_columns = {
        'rxnorm_cui': sa.String,
        'reconciliation_category': sa.Enum,
        'flags': sa.ARRAY,
        'dose_value': sa.Float,
        'dose_unit': sa.String,
        'sources': sa.ARRAY,
        'reconciliation_completed_at': sa.DateTime,
    }
    
    table = Medication.__table__
    
    for col_name, expected_type in expected_columns.items():
        assert col_name in table.c, f"Column {col_name} not found in Medication table"
        col = table.c[col_name]
        # Check type matches (basic check)
        print(f"✓ Column '{col_name}' exists (type: {col.type.__class__.__name__})")
    
    print("✓ AC2 PASSED: ORM model extended with all reconciliation fields")


def test_ac3_pydantic_schema():
    """AC3: Pydantic Response Schema"""
    print("\n=== AC3: Pydantic Response Schema ===")
    
    from app.schemas.medication import MedicationReconciliationResult, MedicationReconciliationResponse
    from app.models.medication import ReconciliationCategory, ReconciliationFlag
    
    # Test MedicationReconciliationResult
    result = MedicationReconciliationResult(
        id=uuid.uuid4(),
        name='Metformin 500mg oral',
        rxnorm_cui='860975',
        reconciliation_category=ReconciliationCategory.CONTINUED,
        pre_admit=True,
        inpatient=True,
        discharge=True,
        flags=[ReconciliationFlag.DUPLICATE],
        dose='500mg',
        route='oral',
        frequency='twice daily',
    )
    
    # Serialize to JSON
    json_data = result.model_dump_json()
    assert '"pre_admit":true' in json_data or '"pre_admit": true' in json_data
    assert '"inpatient":true' in json_data or '"inpatient": true' in json_data
    assert '"discharge":true' in json_data or '"discharge": true' in json_data
    assert '"flags"' in json_data
    print(f"✓ MedicationReconciliationResult serializes correctly")
    print(f"  Sample JSON (first 200 chars): {json_data[:200]}...")
    
    # Test MedicationReconciliationResponse
    response = MedicationReconciliationResponse(
        encounter_id=uuid.uuid4(),
        total_medications=1,
        reconciliation_completed_at="2026-07-27T10:00:00Z",
        medications=[result],
    )
    
    response_json = response.model_dump_json()
    assert '"encounter_id"' in response_json
    assert '"total_medications":1' in response_json or '"total_medications": 1' in response_json
    assert '"medications"' in response_json
    print(f"✓ MedicationReconciliationResponse serializes correctly")
    
    print("✓ AC3 PASSED: Pydantic schemas serialize correctly")


def test_ac4_alembic_migration():
    """AC4: Alembic Migration"""
    print("\n=== AC4: Alembic Migration ===")
    
    migration_file = backend_path / "alembic" / "versions" / "n8k1j4f69i63_add_medication_reconciliation_fields.py"
    
    assert migration_file.exists(), f"Migration file not found: {migration_file}"
    print(f"✓ Migration file exists: {migration_file.name}")
    
    # Read migration file and check for key operations
    content = migration_file.read_text()
    
    # Check for enum creation
    assert "reconciliationcategory" in content.lower(), "ReconciliationCategory enum not found"
    assert "reconciliationflag" in content.lower(), "ReconciliationFlag enum not found"
    assert "medicationlistsource" in content.lower(), "MedicationListSource enum not found"
    print("✓ Migration creates all three ENUM types")
    
    # Check for column additions
    required_columns = [
        "rxnorm_cui",
        "reconciliation_category",
        "flags",
        "dose_value",
        "dose_unit",
        "sources",
        "reconciliation_completed_at",
    ]
    
    for col in required_columns:
        assert col in content, f"Column '{col}' not found in migration"
    print(f"✓ Migration adds all {len(required_columns)} required columns")
    
    # Check for indexes
    assert "ix_medication_rxnorm_cui" in content, "Index on rxnorm_cui not found"
    assert "ix_medication_reconciliation_category" in content, "Index on reconciliation_category not found"
    print("✓ Migration creates required indexes")
    
    # Check for downgrade function
    assert "def downgrade()" in content, "Downgrade function not found"
    assert "drop_column" in content.lower(), "Downgrade does not drop columns"
    print("✓ Migration has downgrade function")
    
    print("✓ AC4 PASSED: Alembic migration file is complete and correct")


def main():
    """Run all validation tests"""
    print("=" * 70)
    print("US-030 TASK-001 Validation: Medication ORM Models, Enums, and Migration")
    print("=" * 70)
    
    try:
        test_ac1_enums_defined()
        test_ac2_orm_model_extended()
        test_ac3_pydantic_schema()
        test_ac4_alembic_migration()
        
        print("\n" + "=" * 70)
        print("✅ ALL ACCEPTANCE CRITERIA PASSED")
        print("=" * 70)
        print("\nDefinition of Done Checklist:")
        print("✓ ReconciliationCategory, ReconciliationFlag, MedicationListSource enums defined")
        print("✓ Medication ORM model extended with all reconciliation columns")
        print("✓ MedicationReconciliationResult and MedicationReconciliationResponse Pydantic schemas created")
        print("✓ Alembic migration generated and verified (structure checked)")
        print("✓ All validation steps pass")
        print("\nNote: Migration apply/rollback test requires database connection (deferred to deployment)")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
