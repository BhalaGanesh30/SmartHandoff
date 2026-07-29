"""Validation script for US-042 TASK-001: care_escalation ORM model and migration.

This script validates:
1. CareEscalation model structure and fields
2. CareEscalationStatus enum definition
3. Model registration in __init__.py
4. Alembic migration file structure
5. Foreign key relationships
6. Idempotency key uniqueness constraint
7. Soft delete support
8. PHI compliance

Usage:
    python validate_us042_task001_care_escalation.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

# Base paths
REPO_ROOT = Path(__file__).parent
BACKEND_BASE = REPO_ROOT / "backend"
MODELS_DIR = BACKEND_BASE / "app" / "models"
MIGRATION_FILE = BACKEND_BASE / "alembic" / "versions" / "w7t0s3r68p22_add_care_escalation_table_us042.py"


class ValidationResult:
    """Tracks validation check results."""
    
    def __init__(self) -> None:
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors: list[str] = []
        self.warning_msgs: list[str] = []
    
    def check(self, condition: bool, success_msg: str, failure_msg: str, is_warning: bool = False) -> None:
        """Record a validation check result."""
        self.total += 1
        if condition:
            self.passed += 1
            print(f"✓ {success_msg}")
        else:
            if is_warning:
                self.warnings += 1
                self.warning_msgs.append(failure_msg)
                print(f"⚠ {failure_msg}")
            else:
                self.failed += 1
                self.errors.append(failure_msg)
                print(f"✗ {failure_msg}")
    
    def summary(self) -> None:
        """Print validation summary and exit with appropriate code."""
        print("\n" + "=" * 80)
        print(f"Validation Results: {self.passed}/{self.total} checks passed")
        if self.warnings > 0:
            print(f"\n⚠ {self.warnings} warnings:")
            for warning in self.warning_msgs:
                print(f"  - {warning}")
        if self.failed > 0:
            print(f"\n✗ {self.failed} checks failed:")
            for error in self.errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print("\n✓ All validation checks passed!")
            print("✓ US-042 TASK-001 implementation complete - ready for migration testing.")
            sys.exit(0)


def validate_model_structure(result: ValidationResult) -> None:
    """Category 1: CareEscalation Model Structure."""
    print("\n" + "=" * 80)
    print("Category 1: CareEscalation Model Structure")
    print("=" * 80)
    
    model_file = MODELS_DIR / "care_escalation.py"
    result.check(
        model_file.exists(),
        "care_escalation.py model file exists",
        "care_escalation.py model file not found",
    )
    
    if not model_file.exists():
        return
    
    content = model_file.read_text(encoding="utf-8")
    
    # Check enum definition
    result.check(
        "class CareEscalationStatus(str, enum.Enum):" in content,
        "CareEscalationStatus enum defined",
        "CareEscalationStatus enum not found",
    )
    
    # Check enum values
    result.check(
        'PENDING = "PENDING"' in content,
        "Enum value PENDING defined",
        "Enum value PENDING missing",
    )
    
    result.check(
        'ACKNOWLEDGED = "ACKNOWLEDGED"' in content,
        "Enum value ACKNOWLEDGED defined",
        "Enum value ACKNOWLEDGED missing",
    )
    
    result.check(
        'ESCALATED_TO_SUPERVISOR = "ESCALATED_TO_SUPERVISOR"' in content,
        "Enum value ESCALATED_TO_SUPERVISOR defined",
        "Enum value ESCALATED_TO_SUPERVISOR missing",
    )
    
    # Check class definition
    result.check(
        "class CareEscalation(Base):" in content,
        "CareEscalation class inherits from Base",
        "CareEscalation class definition incorrect",
    )
    
    # Check required fields
    required_fields = [
        "id",
        "encounter_id",
        "patient_id",
        "notified_nurse_user_id",
        "status",
        "sent_at",
        "acknowledged_at",
        "acknowledged_by",
        "escalated_to_supervisor",
        "escalated_at",
        "idempotency_key",
        "created_at",
        "updated_at",
        "deleted_at",
    ]
    
    for field in required_fields:
        result.check(
            f"{field}: Mapped[" in content or f'"{field}"' in content,
            f"Field '{field}' defined in model",
            f"Field '{field}' missing from model",
        )
    
    # Check foreign key relationships
    result.check(
        'ForeignKey("encounter.id"' in content,
        "Foreign key to encounter.id defined",
        "Foreign key to encounter.id missing",
    )
    
    result.check(
        'ForeignKey("patient.id"' in content,
        "Foreign key to patient.id defined",
        "Foreign key to patient.id missing",
    )
    
    result.check(
        'ForeignKey("app_user.id"' in content,
        "Foreign key to app_user.id defined",
        "Foreign key to app_user.id missing",
    )
    
    # Check unique constraint on idempotency_key
    result.check(
        'UniqueConstraint("idempotency_key"' in content,
        "Unique constraint on idempotency_key defined",
        "Unique constraint on idempotency_key missing",
    )
    
    # Check soft delete field
    result.check(
        "deleted_at" in content and "Mapped[datetime | None]" in content,
        "Soft delete support (deleted_at) present",
        "Soft delete support (deleted_at) missing",
    )


def validate_model_registration(result: ValidationResult) -> None:
    """Category 2: Model Registration in __init__.py."""
    print("\n" + "=" * 80)
    print("Category 2: Model Registration")
    print("=" * 80)
    
    init_file = MODELS_DIR / "__init__.py"
    result.check(
        init_file.exists(),
        "__init__.py file exists",
        "__init__.py file not found",
    )
    
    if not init_file.exists():
        return
    
    content = init_file.read_text(encoding="utf-8")
    
    # Check import statement
    result.check(
        "from app.models.care_escalation import CareEscalation, CareEscalationStatus" in content,
        "CareEscalation and CareEscalationStatus imported in __init__.py",
        "CareEscalation import missing from __init__.py",
    )
    
    # Check __all__ export
    result.check(
        '"CareEscalation"' in content,
        "CareEscalation in __all__ list",
        "CareEscalation missing from __all__ list",
    )
    
    result.check(
        '"CareEscalationStatus"' in content,
        "CareEscalationStatus in __all__ list",
        "CareEscalationStatus missing from __all__ list",
    )


def validate_migration(result: ValidationResult) -> None:
    """Category 3: Alembic Migration Structure."""
    print("\n" + "=" * 80)
    print("Category 3: Alembic Migration")
    print("=" * 80)
    
    result.check(
        MIGRATION_FILE.exists(),
        "Migration file w7t0s3r68p22_add_care_escalation_table_us042.py exists",
        "Migration file not found",
    )
    
    if not MIGRATION_FILE.exists():
        return
    
    content = MIGRATION_FILE.read_text(encoding="utf-8")
    
    # Check revision identifiers
    result.check(
        'revision = "w7t0s3r68p22"' in content,
        "Migration revision ID correct",
        "Migration revision ID incorrect",
    )
    
    result.check(
        'down_revision = "v6s9r2q57o21"' in content,
        "Migration down_revision points to previous migration",
        "Migration down_revision incorrect",
    )
    
    # Check enum creation
    result.check(
        'postgresql.ENUM' in content and 'name="care_escalation_status"' in content,
        "PostgreSQL ENUM care_escalation_status created",
        "PostgreSQL ENUM creation missing",
    )
    
    result.check(
        '"PENDING"' in content and '"ACKNOWLEDGED"' in content and '"ESCALATED_TO_SUPERVISOR"' in content,
        "All enum values present in migration",
        "Enum values missing from migration",
    )
    
    # Check table creation
    result.check(
        'op.create_table(\n        "care_escalation",' in content,
        "care_escalation table creation command present",
        "Table creation command missing",
    )
    
    # Check unique constraint
    result.check(
        'op.create_unique_constraint(\n        "uq_care_escalation_idempotency_key",' in content,
        "Unique constraint on idempotency_key in migration",
        "Unique constraint missing from migration",
    )
    
    # Check indexes
    result.check(
        'op.create_index(\n        "ix_care_escalation_encounter_id",' in content,
        "Index on encounter_id created",
        "Index on encounter_id missing",
    )
    
    result.check(
        'op.create_index(\n        "ix_care_escalation_patient_id",' in content,
        "Index on patient_id created",
        "Index on patient_id missing",
    )
    
    # Check downgrade function
    result.check(
        "def downgrade()" in content,
        "Downgrade function defined",
        "Downgrade function missing",
    )
    
    result.check(
        'op.drop_table("care_escalation")' in content,
        "Downgrade drops table",
        "Downgrade table drop missing",
    )
    
    result.check(
        'DROP TYPE IF EXISTS care_escalation_status' in content,
        "Downgrade drops enum",
        "Downgrade enum drop missing",
    )


def validate_phi_compliance(result: ValidationResult) -> None:
    """Category 4: PHI Compliance."""
    print("\n" + "=" * 80)
    print("Category 4: PHI Compliance (ADR-007)")
    print("=" * 80)
    
    model_file = MODELS_DIR / "care_escalation.py"
    if not model_file.exists():
        return
    
    content = model_file.read_text(encoding="utf-8")
    
    # Check that no PHI fields are stored
    phi_fields = ["phone", "email", "first_name", "last_name", "patient_name", "mrn", "dob"]
    has_phi = False
    for field in phi_fields:
        if f'"{field}"' in content or f"'{field}'" in content:
            has_phi = True
            break
    
    result.check(
        not has_phi,
        "No PHI fields in care_escalation model",
        "PHI VIOLATION: PHI fields detected in model",
    )
    
    # Check that only UUIDs are used for patient/encounter references
    result.check(
        "patient_id: Mapped[uuid.UUID]" in content,
        "Uses patient_id UUID (not PHI)",
        "patient_id not using UUID",
    )
    
    result.check(
        "encounter_id: Mapped[uuid.UUID]" in content,
        "Uses encounter_id UUID (not PHI)",
        "encounter_id not using UUID",
    )


def validate_idempotency(result: ValidationResult) -> None:
    """Category 5: Idempotency (ADR-001)."""
    print("\n" + "=" * 80)
    print("Category 5: Idempotency (ADR-001)")
    print("=" * 80)
    
    model_file = MODELS_DIR / "care_escalation.py"
    if not model_file.exists():
        return
    
    content = model_file.read_text(encoding="utf-8")
    
    # Check idempotency_key field
    result.check(
        "idempotency_key" in content,
        "idempotency_key field present",
        "idempotency_key field missing",
    )
    
    # Check unique constraint
    result.check(
        "unique=True" in content or 'UniqueConstraint("idempotency_key"' in content,
        "idempotency_key has unique constraint",
        "idempotency_key unique constraint missing",
    )
    
    # Check comment mentions ESC-{encounter_id} format
    result.check(
        "ESC-{encounter" in content or "Format: ESC-" in content,
        "idempotency_key format documented (ESC-{encounter_id})",
        "idempotency_key format not documented",
    )


def main() -> None:
    """Run all validation checks."""
    print("US-042 TASK-001 Validation: care_escalation ORM Model + Alembic Migration")
    print("=" * 80)
    
    result = ValidationResult()
    
    # Category 1: Model Structure
    validate_model_structure(result)
    
    # Category 2: Model Registration
    validate_model_registration(result)
    
    # Category 3: Migration
    validate_migration(result)
    
    # Category 4: PHI Compliance
    validate_phi_compliance(result)
    
    # Category 5: Idempotency
    validate_idempotency(result)
    
    # Print summary and exit
    result.summary()


if __name__ == "__main__":
    main()
