"""
Validation script for US-030 TASK-001: Medication ORM Models, Enums, and Alembic Migration

This script validates:
1. Enum definitions (ReconciliationCategory, ReconciliationFlag, MedicationListSource)
2. Pydantic schema serialization (MedicationReconciliationResult)
3. Migration file existence and structure

Run: python validate_us030_task001.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

print("=" * 80)
print("US-030 TASK-001 VALIDATION: Medication Reconciliation ORM & Schema")
print("=" * 80)
print()

# ============================================================================
# Step 1: Enum Validation
# ============================================================================
print("Step 1: Enum Validation")
print("-" * 80)

try:
    from app.models.medication import (
        ReconciliationCategory,
        ReconciliationFlag,
        MedicationListSource,
    )
    
    # Validate ReconciliationCategory
    expected_categories = {"CONTINUED", "NEW", "STOPPED", "DOSE_CHANGED"}
    actual_categories = {item.value for item in ReconciliationCategory}
    
    assert actual_categories == expected_categories, (
        f"ReconciliationCategory mismatch. "
        f"Expected: {expected_categories}, Got: {actual_categories}"
    )
    assert len(ReconciliationCategory) == 4, (
        f"ReconciliationCategory should have 4 values, got {len(ReconciliationCategory)}"
    )
    print(f"✓ ReconciliationCategory: {len(ReconciliationCategory)} values")
    for item in ReconciliationCategory:
        print(f"  - {item.value}")
    
    # Validate ReconciliationFlag
    expected_flags = {"DUPLICATE", "STOPPED_WITHOUT_ORDER"}
    actual_flags = {item.value for item in ReconciliationFlag}
    
    assert actual_flags == expected_flags, (
        f"ReconciliationFlag mismatch. "
        f"Expected: {expected_flags}, Got: {actual_flags}"
    )
    assert len(ReconciliationFlag) == 2, (
        f"ReconciliationFlag should have 2 values, got {len(ReconciliationFlag)}"
    )
    print(f"✓ ReconciliationFlag: {len(ReconciliationFlag)} values")
    for item in ReconciliationFlag:
        print(f"  - {item.value}")
    
    # Validate MedicationListSource
    expected_sources = {"PRE_ADMIT", "INPATIENT", "DISCHARGE"}
    actual_sources = {item.value for item in MedicationListSource}
    
    assert actual_sources == expected_sources, (
        f"MedicationListSource mismatch. "
        f"Expected: {expected_sources}, Got: {actual_sources}"
    )
    assert len(MedicationListSource) == 3, (
        f"MedicationListSource should have 3 values, got {len(MedicationListSource)}"
    )
    print(f"✓ MedicationListSource: {len(MedicationListSource)} values")
    for item in MedicationListSource:
        print(f"  - {item.value}")
    
    print()
    print("✓ All enums validated successfully")
    print()
    
except Exception as e:
    print(f"✗ Enum validation failed: {e}")
    sys.exit(1)

# ============================================================================
# Step 2: Schema Serialization
# ============================================================================
print("Step 2: Pydantic Schema Serialization")
print("-" * 80)

try:
    from app.schemas.medication import (
        MedicationReconciliationResult,
        MedicationReconciliationResponse,
    )
    
    # Test MedicationReconciliationResult
    result = MedicationReconciliationResult(
        id=uuid.uuid4(),
        name="Metformin 500mg oral",
        rxnorm_cui="860975",
        reconciliation_category=ReconciliationCategory.CONTINUED,
        pre_admit=True,
        inpatient=True,
        discharge=True,
        flags=[],
        dose="500mg",
        route="oral",
        frequency="twice daily",
    )
    
    # Serialize to dict
    result_dict = result.model_dump()
    
    # Validate required fields
    assert result_dict["id"] is not None, "ID should not be None"
    assert result_dict["name"] == "Metformin 500mg oral", "Name mismatch"
    assert result_dict["rxnorm_cui"] == "860975", "RxNorm CUI mismatch"
    assert result_dict["reconciliation_category"] == "CONTINUED", "Category mismatch"
    assert result_dict["pre_admit"] is True, "pre_admit should be True"
    assert result_dict["inpatient"] is True, "inpatient should be True"
    assert result_dict["discharge"] is True, "discharge should be True"
    assert result_dict["flags"] == [], "flags should be empty list"
    assert result_dict["dose"] == "500mg", "dose mismatch"
    assert result_dict["route"] == "oral", "route mismatch"
    assert result_dict["frequency"] == "twice daily", "frequency mismatch"
    
    print("✓ MedicationReconciliationResult schema validated")
    print()
    print("Sample serialized JSON:")
    import json
    print(json.dumps(result_dict, indent=2, default=str))
    print()
    
    # Test MedicationReconciliationResponse
    response = MedicationReconciliationResponse(
        encounter_id=uuid.uuid4(),
        total_medications=1,
        reconciliation_completed_at="2026-07-26T12:00:00Z",
        medications=[result],
    )
    
    response_dict = response.model_dump()
    assert response_dict["encounter_id"] is not None, "encounter_id should not be None"
    assert response_dict["total_medications"] == 1, "total_medications mismatch"
    assert len(response_dict["medications"]) == 1, "medications list length mismatch"
    
    print("✓ MedicationReconciliationResponse schema validated")
    print()
    
except Exception as e:
    print(f"✗ Schema serialization failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Step 3: Migration File Validation
# ============================================================================
print("Step 3: Migration File Validation")
print("-" * 80)

try:
    migration_file = backend_path / "alembic" / "versions" / "n8k1j4f69i63_add_medication_reconciliation_fields.py"
    
    assert migration_file.exists(), f"Migration file not found: {migration_file}"
    print(f"✓ Migration file exists: {migration_file.name}")
    
    # Read migration file and validate structure
    migration_content = migration_file.read_text()
    
    # Check for required elements
    required_elements = [
        "revision = \"n8k1j4f69i63\"",
        "down_revision = \"m7j0i3e58h62\"",
        "def upgrade()",
        "def downgrade()",
        "reconciliationcategory",
        "reconciliationflag",
        "medicationlistsource",
        "rxnorm_cui",
        "reconciliation_category",
        "flags",
        "dose_value",
        "dose_unit",
        "sources",
        "reconciliation_completed_at",
    ]
    
    for element in required_elements:
        assert element in migration_content, f"Migration file missing: {element}"
        print(f"✓ Found: {element}")
    
    print()
    print("✓ Migration file structure validated")
    print()
    
except Exception as e:
    print(f"✗ Migration file validation failed: {e}")
    sys.exit(1)

# ============================================================================
# Summary
# ============================================================================
print("=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)
print()
print("✓ Step 1: Enum Validation - PASSED")
print("✓ Step 2: Pydantic Schema Serialization - PASSED")
print("✓ Step 3: Migration File Validation - PASSED")
print()
print("=" * 80)
print("All US-030 TASK-001 validations PASSED")
print("=" * 80)
print()
print("Next Steps:")
print("1. Set DATABASE_URL environment variable")
print("2. Run: cd backend && alembic upgrade head")
print("3. Verify migration applies without errors")
print("4. Run: cd backend && alembic downgrade -1")
print("5. Verify rollback works correctly")
print("6. Run: cd backend && alembic upgrade head")
print("7. Migration is ready for TASK-002 (FHIR Medication Fetcher)")
print()
