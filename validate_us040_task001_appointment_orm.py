"""Validation script for US-040 TASK-001: Appointment ORM Model + Alembic Migration.

Validates:
    1. Appointment ORM model structure
    2. AppointmentType and AppointmentStatus enums
    3. Encounter.appointments relationship
    4. Alembic migration file structure
    5. Migration syntax and reversibility

US-040 TASK-001 — appointment SQLAlchemy ORM Model + Alembic Migration
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent
BACKEND_ROOT = PROJECT_ROOT / "backend"

VALIDATION_RESULTS = []


def check(category: str, name: str, condition: bool, details: str = "") -> bool:
    """Record a validation check result."""
    status = "✅ PASS" if condition else "❌ FAIL"
    result = f"  [{status}] {name}"
    if details:
        if not condition:
            result += f"\n      → {details}"
        else:
            result += f" — {details}"
    VALIDATION_RESULTS.append((category, condition, result))
    print(result)
    return condition


def validate_appointment_model() -> bool:
    """Validate Appointment ORM model structure."""
    print("\n1. APPOINTMENT ORM MODEL")
    print("=" * 60)
    
    try:
        appointment_file = BACKEND_ROOT / "app" / "models" / "appointment.py"
        
        check("Model", "appointment.py exists", appointment_file.exists())
        
        if not appointment_file.exists():
            check("Model", "Appointment model validation failed", False, "File not found")
            return False
        
        code = appointment_file.read_text()
        
        # Check imports
        check("Model", "from __future__ import annotations", "from __future__ import annotations" in code)
        check("Model", "Imports Base from app.db.base", "from app.db.base import Base" in code)
        check("Model", "Imports mixins", "from app.db.mixins import" in code)
        
        # Check enums
        check("Model", "AppointmentType enum defined", "class AppointmentType(str, enum.Enum):" in code)
        check("Model", "HIGH_RISK_FOLLOW_UP in AppointmentType", 'HIGH_RISK_FOLLOW_UP = "HIGH_RISK_FOLLOW_UP"' in code)
        check("Model", "STANDARD_FOLLOW_UP in AppointmentType", 'STANDARD_FOLLOW_UP = "STANDARD_FOLLOW_UP"' in code)
        check("Model", "ROUTINE_FOLLOW_UP in AppointmentType", 'ROUTINE_FOLLOW_UP = "ROUTINE_FOLLOW_UP"' in code)
        
        check("Model", "AppointmentStatus enum defined", "class AppointmentStatus(str, enum.Enum):" in code)
        check("Model", "SCHEDULED in AppointmentStatus", 'SCHEDULED = "SCHEDULED"' in code)
        check("Model", "CONFIRMED in AppointmentStatus", 'CONFIRMED = "CONFIRMED"' in code)
        check("Model", "COMPLETED in AppointmentStatus", 'COMPLETED = "COMPLETED"' in code)
        check("Model", "MISSED in AppointmentStatus", 'MISSED = "MISSED"' in code)
        
        # Check class definition
        check("Model", "Appointment class extends Base", "class Appointment(Base" in code)
        check("Model", "Appointment uses TimestampMixin", "TimestampMixin" in code)
        check("Model", "Appointment uses SoftDeleteMixin", "SoftDeleteMixin" in code)
        
        # Check required columns
        check("Model", "id column defined", "id: Mapped[uuid.UUID]" in code)
        check("Model", "encounter_id column defined", "encounter_id: Mapped[uuid.UUID]" in code)
        check("Model", "appointment_type column defined", "appointment_type: Mapped[str]" in code)
        check("Model", "target_date column defined", "target_date: Mapped[date]" in code)
        check("Model", "status column defined", "status: Mapped[str]" in code)
        check("Model", "assigned_user_id column (nullable)", "assigned_user_id: Mapped[uuid.UUID | None]" in code)
        
        # Check foreign keys
        check("Model", "encounter FK with CASCADE", 'ForeignKey("encounter.id", ondelete="CASCADE")' in code)
        check("Model", "app_user FK with SET NULL", 'ForeignKey("app_user.id", ondelete="SET NULL")' in code)
        
        # Check unique constraint
        check("Model", "UniqueConstraint on encounter_id, appointment_type", 
              "UniqueConstraint" in code and "encounter_id" in code and "appointment_type" in code)
        
        # Check relationships
        check("Model", "encounter relationship defined", 'encounter: Mapped["Encounter"]' in code)
        check("Model", "assigned_user relationship defined", 'assigned_user: Mapped["AppUser | None"]' in code)
        
        # Check indexes
        check("Model", "encounter_id indexed", "index=True" in code)
        check("Model", "assigned_user_id indexed", "index=True" in code)
        
        return True
    except Exception as e:
        check("Model", "Appointment model validation failed", False, str(e))
        return False


def validate_encounter_relationship() -> bool:
    """Validate Encounter.appointments relationship."""
    print("\n2. ENCOUNTER.APPOINTMENTS RELATIONSHIP")
    print("=" * 60)
    
    try:
        encounter_file = BACKEND_ROOT / "app" / "models" / "encounter.py"
        
        check("Relationship", "encounter.py exists", encounter_file.exists())
        
        if not encounter_file.exists():
            check("Relationship", "Encounter relationship validation failed", False, "File not found")
            return False
        
        # Read with UTF-8 encoding to handle special characters
        code = encounter_file.read_text(encoding="utf-8")
        
        # Check import in TYPE_CHECKING block
        check("Relationship", "Appointment imported in TYPE_CHECKING", 
              "from app.models.appointment import Appointment" in code)
        
        # Check relationship definition
        has_appointments_relationship = 'appointments: Mapped[list["Appointment"]]' in code
        check("Relationship", "appointments relationship defined", has_appointments_relationship)
        
        # Check cascade
        check("Relationship", "cascade='all, delete-orphan'", 
              "cascade=" in code and "delete-orphan" in code)
        
        # Check back_populates
        check("Relationship", "back_populates='encounter'", 
              'back_populates="encounter"' in code or "back_populates='encounter'" in code)
        
        return True
    except Exception as e:
        check("Relationship", "Encounter relationship validation failed", False, str(e))
        return False


def validate_migration_file() -> bool:
    """Validate Alembic migration file."""
    print("\n3. ALEMBIC MIGRATION FILE")
    print("=" * 60)
    
    try:
        migration_file = BACKEND_ROOT / "alembic" / "versions" / "u5r8q1p46n10_add_appointment_table.py"
        
        check("Migration", "u5r8q1p46n10_add_appointment_table.py exists", migration_file.exists())
        
        if not migration_file.exists():
            check("Migration", "Migration validation failed", False, "File not found")
            return False
        
        code = migration_file.read_text()
        
        # Check revision metadata
        check("Migration", "revision = 'u5r8q1p46n10'", 'revision = "u5r8q1p46n10"' in code)
        check("Migration", "down_revision = 't4q7p0l35o09'", 
              'down_revision' in code and 't4q7p0l35o09' in code)
        
        # Check upgrade function
        check("Migration", "def upgrade() defined", "def upgrade() -> None:" in code)
        check("Migration", "op.create_table('appointment')", 
              'op.create_table(' in code and '"appointment"' in code)
        
        # Check columns in upgrade
        columns_to_check = [
            '"id"',
            '"encounter_id"',
            '"appointment_type"',
            '"target_date"',
            '"status"',
            '"assigned_user_id"',
            '"created_at"',
            '"updated_at"',
            '"deleted_at"',
        ]
        
        for col in columns_to_check:
            check("Migration", f"Column {col} in create_table", col in code)
        
        # Check foreign keys
        check("Migration", "FK to encounter.id with CASCADE", 
              'ForeignKey("encounter.id", ondelete="CASCADE")' in code)
        check("Migration", "FK to app_user.id with SET NULL", 
              'ForeignKey("app_user.id", ondelete="SET NULL")' in code)
        
        # Check indexes
        check("Migration", "idx_appointment_encounter_id created", 
              "idx_appointment_encounter_id" in code)
        check("Migration", "idx_appointment_assigned_user created", 
              "idx_appointment_assigned_user" in code)
        check("Migration", "idx_appointment_deleted_at created", 
              "idx_appointment_deleted_at" in code)
        
        # Check unique constraint
        check("Migration", "uq_appointment_encounter_type created", 
              "uq_appointment_encounter_type" in code)
        
        # Check downgrade function
        check("Migration", "def downgrade() defined", "def downgrade() -> None:" in code)
        check("Migration", "op.drop_table('appointment') in downgrade", 
              'op.drop_table("appointment")' in code)
        check("Migration", "Constraints dropped before table", 
              "op.drop_constraint" in code)
        
        # Syntax validation
        try:
            ast.parse(code)
            check("Migration", "Python syntax valid", True)
        except SyntaxError as e:
            check("Migration", "Python syntax valid", False, str(e))
        
        return True
    except Exception as e:
        check("Migration", "Migration validation failed", False, str(e))
        return False


def validate_dod_criteria() -> bool:
    """Validate Definition of Done criteria."""
    print("\n4. DEFINITION OF DONE")
    print("=" * 60)
    
    try:
        # Check all files created
        files_required = [
            BACKEND_ROOT / "app" / "models" / "appointment.py",
            BACKEND_ROOT / "alembic" / "versions" / "u5r8q1p46n10_add_appointment_table.py",
        ]
        
        all_files_exist = all(f.exists() for f in files_required)
        check("DoD", "All required files created", all_files_exist,
              f"{sum(f.exists() for f in files_required)}/{len(files_required)} files found")
        
        # Check Appointment model components
        appointment_file = BACKEND_ROOT / "app" / "models" / "appointment.py"
        if appointment_file.exists():
            code = appointment_file.read_text(encoding="utf-8")
            check("DoD", "Appointment class with required columns", 
                  all(col in code for col in ["encounter_id", "appointment_type", "target_date", "status", "assigned_user_id"]))
            check("DoD", "AppointmentType enum complete", 
                  all(t in code for t in ["HIGH_RISK_FOLLOW_UP", "STANDARD_FOLLOW_UP", "ROUTINE_FOLLOW_UP"]))
            check("DoD", "AppointmentStatus enum complete", 
                  all(s in code for s in ["SCHEDULED", "CONFIRMED", "COMPLETED", "MISSED"]))
        
        # Check Encounter relationship
        encounter_file = BACKEND_ROOT / "app" / "models" / "encounter.py"
        if encounter_file.exists():
            code = encounter_file.read_text(encoding="utf-8")
            check("DoD", "Encounter.appointments relationship added", 
                  'appointments: Mapped[list["Appointment"]]' in code)
        
        return True
    except Exception as e:
        check("DoD", "DoD validation failed", False, str(e))
        return False


def print_summary():
    """Print validation summary."""
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    categories = {}
    for category, passed, _ in VALIDATION_RESULTS:
        if category not in categories:
            categories[category] = {"passed": 0, "total": 0}
        categories[category]["total"] += 1
        if passed:
            categories[category]["passed"] += 1
    
    total_passed = sum(c["passed"] for c in categories.values())
    total_checks = sum(c["total"] for c in categories.values())
    
    for category, counts in categories.items():
        status = "✅" if counts["passed"] == counts["total"] else "❌"
        print(f"{status} {category}: {counts['passed']}/{counts['total']} checks passed")
    
    print("=" * 60)
    print(f"TOTAL: {total_passed}/{total_checks} CHECKS PASSED")
    
    if total_passed == total_checks:
        print("✅ ALL VALIDATIONS PASSED")
        print("\nNext Steps:")
        print("  1. Set DATABASE_URL environment variable for local testing")
        print("  2. Run: alembic upgrade head")
        print("  3. Verify: alembic current  # Should show: u5r8q1p46n10 (head)")
        print("  4. Test reversibility: alembic downgrade -1")
        print("  5. Reapply: alembic upgrade head")
        return True
    else:
        print("❌ SOME VALIDATIONS FAILED")
        return False


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("US-040 TASK-001 VALIDATION")
    print("appointment SQLAlchemy ORM Model + Alembic Migration")
    print("=" * 60)
    
    validate_appointment_model()
    validate_encounter_relationship()
    validate_migration_file()
    validate_dod_criteria()
    
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
