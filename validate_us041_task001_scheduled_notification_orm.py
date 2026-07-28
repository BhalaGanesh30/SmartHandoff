"""Validation script for US-041 TASK-001: ScheduledNotification ORM + Migration.

Performs comprehensive automated checks across 7 categories:
1. File Structure — model file, migration file, __init__.py registration
2. Model Definition — class attributes, enums, type hints
3. Database Schema — column definitions, foreign keys, indexes
4. Migration Syntax — Alembic upgrade/downgrade structure
5. Acceptance Criteria — AC Scenario 1 and 4 field coverage
6. Code Quality — docstrings, type hints, comments
7. Design Requirements — DR-001 (Alembic), DR-005 (soft delete), ADR-007 (no PHI)

Exits 0 if all checks pass, 1 otherwise.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


def validate_file_structure() -> tuple[int, int]:
    """Validate all required files exist and are registered.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    # Check model file exists
    model_path = Path("backend/app/models/scheduled_notification.py")
    checks.append((
        "Model file exists",
        model_path.exists(),
    ))
    
    # Check migration file exists
    migration_files = list(Path("backend/alembic/versions").glob("*scheduled_notification*.py"))
    checks.append((
        "Migration file exists",
        len(migration_files) == 1,
    ))
    
    # Check __init__.py registration
    init_path = Path("backend/app/models/__init__.py")
    if init_path.exists():
        init_content = init_path.read_text()
        checks.append((
            "ScheduledNotification imported in __init__.py",
            "from app.models.scheduled_notification import" in init_content and
            "ScheduledNotification" in init_content,
        ))
        checks.append((
            "DeliveryStatus enum imported in __init__.py",
            "DeliveryStatus" in init_content,
        ))
        checks.append((
            "NotificationChannel enum imported in __init__.py",
            "NotificationChannel" in init_content,
        ))
        checks.append((
            "NotificationType enum imported in __init__.py",
            "NotificationType" in init_content,
        ))
        checks.append((
            "ScheduledNotification in __all__",
            '"ScheduledNotification"' in init_content,
        ))
    else:
        checks.extend([
            ("__init__.py registration checks", False),
        ] * 5)
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_model_definition() -> tuple[int, int]:
    """Validate ScheduledNotification model class structure.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    model_path = Path("backend/app/models/scheduled_notification.py")
    if not model_path.exists():
        print("❌ FAIL | Model file not found")
        return 0, 1
    
    content = model_path.read_text()
    
    # Check class definition
    checks.append((
        "ScheduledNotification class defined",
        "class ScheduledNotification(Base):" in content,
    ))
    
    # Check required fields
    required_fields = [
        "id: Mapped[uuid.UUID]",
        "idempotency_key: Mapped[str]",
        "type: Mapped[NotificationType]",
        "send_at: Mapped[datetime]",
        "channel: Mapped[NotificationChannel]",
        "delivery_status: Mapped[DeliveryStatus]",
        "patient_id: Mapped[uuid.UUID]",
        "encounter_id: Mapped[uuid.UUID]",
        "deleted_at: Mapped[datetime | None]",
        "created_at: Mapped[datetime]",
        "updated_at: Mapped[datetime]",
    ]
    
    for field in required_fields:
        checks.append((
            f"Field defined: {field.split(':')[0].strip()}",
            field in content,
        ))
    
    # Check enums
    checks.append((
        "NotificationType enum with CHECK_IN_48H",
        "class NotificationType(str, Enum):" in content and
        'CHECK_IN_48H = "CHECK_IN_48H"' in content,
    ))
    checks.append((
        "NotificationType enum with MEDICATION_REMINDER",
        'MEDICATION_REMINDER = "MEDICATION_REMINDER"' in content,
    ))
    checks.append((
        "NotificationChannel enum with SMS and EMAIL",
        "class NotificationChannel(str, Enum):" in content and
        'SMS = "SMS"' in content and
        'EMAIL = "EMAIL"' in content,
    ))
    checks.append((
        "DeliveryStatus enum with all 4 states",
        "class DeliveryStatus(str, Enum):" in content and
        'PENDING = "PENDING"' in content and
        'SENT = "SENT"' in content and
        'OPTED_OUT = "OPTED_OUT"' in content and
        'FAILED = "FAILED"' in content,
    ))
    
    # Check relationships
    checks.append((
        "Patient relationship with lazy='raise'",
        'patient = relationship("Patient", lazy="raise")' in content,
    ))
    checks.append((
        "Encounter relationship with lazy='raise'",
        'encounter = relationship("Encounter", lazy="raise")' in content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_database_schema() -> tuple[int, int]:
    """Validate migration creates correct schema.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    migration_files = list(Path("backend/alembic/versions").glob("*scheduled_notification*.py"))
    if not migration_files:
        print("❌ FAIL | Migration file not found")
        return 0, 1
    
    migration_path = migration_files[0]
    content = migration_path.read_text()
    
    # Check table creation
    checks.append((
        'Table name is "scheduled_notification"',
        '"scheduled_notification"' in content and 'op.create_table' in content,
    ))
    
    # Check columns
    required_columns = [
        "id",
        "idempotency_key",
        "type",
        "send_at",
        "channel",
        "delivery_status",
        "patient_id",
        "encounter_id",
        "deleted_at",
        "created_at",
        "updated_at",
    ]
    
    for col in required_columns:
        checks.append((
            f'Column "{col}" in migration',
            f'"{col}"' in content or f"'{col}'" in content,
        ))
    
    # Check enums creation
    checks.append((
        "NotificationType enum created",
        "notificationtype" in content.lower() and
        "CHECK_IN_48H" in content,
    ))
    checks.append((
        "NotificationChannel enum created",
        "notificationchannel" in content.lower() and
        "SMS" in content and "EMAIL" in content,
    ))
    checks.append((
        "DeliveryStatus enum created",
        "deliverystatus" in content.lower() and
        "PENDING" in content and "SENT" in content,
    ))
    
    # Check unique constraint
    checks.append((
        "Unique constraint on idempotency_key",
        "uq_scheduled_notification_idempotency_key" in content or
        "unique=True" in content.lower(),
    ))
    
    # Check indexes
    indexes = [
        "ix_scheduled_notification_send_at",
        "ix_scheduled_notification_delivery_status",
        "ix_scheduled_notification_patient_id",
        "ix_scheduled_notification_encounter_id",
    ]
    
    for idx in indexes:
        checks.append((
            f"Index {idx} created",
            idx in content,
        ))
    
    # Check foreign keys
    checks.append((
        "Foreign key to patient.id",
        'ForeignKey("patient.id"' in content,
    ))
    checks.append((
        "Foreign key to encounter.id",
        'ForeignKey("encounter.id"' in content,
    ))
    
    # Check downgrade
    checks.append((
        "Downgrade function drops table",
        "def downgrade()" in content and "drop_table" in content.lower(),
    ))
    checks.append((
        "Downgrade function drops enums",
        "DROP TYPE" in content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_migration_syntax() -> tuple[int, int]:
    """Validate Alembic migration syntax and structure.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    migration_files = list(Path("backend/alembic/versions").glob("*scheduled_notification*.py"))
    if not migration_files:
        print("❌ FAIL | Migration file not found")
        return 0, 1
    
    migration_path = migration_files[0]
    content = migration_path.read_text()
    
    # Check revision metadata
    checks.append((
        "revision variable defined",
        re.search(r'revision\s*=\s*["\'][\w]+["\']', content) is not None,
    ))
    checks.append((
        "down_revision variable defined",
        re.search(r'down_revision\s*=\s*["\'][\w]+["\']', content) is not None,
    ))
    
    # Check function signatures
    checks.append((
        "upgrade() function defined with -> None return type",
        "def upgrade() -> None:" in content,
    ))
    checks.append((
        "downgrade() function defined with -> None return type",
        "def downgrade() -> None:" in content,
    ))
    
    # Check imports
    checks.append((
        "Imports sqlalchemy as sa",
        "import sqlalchemy as sa" in content,
    ))
    checks.append((
        "Imports from alembic",
        "from alembic import op" in content,
    ))
    checks.append((
        "Imports postgresql dialect",
        "from sqlalchemy.dialects import postgresql" in content,
    ))
    
    # Check enum creation pattern
    checks.append((
        "Enums created with .create() method",
        ".create(op.get_bind()" in content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_acceptance_criteria() -> tuple[int, int]:
    """Validate US-041 AC Scenario 1 and 4 coverage.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    model_path = Path("backend/app/models/scheduled_notification.py")
    if not model_path.exists():
        print("❌ FAIL | Model file not found")
        return 0, 1
    
    content = model_path.read_text()
    
    # AC Scenario 1: CHECK_IN_48H notification with send_at = discharge_time + 48 hours
    checks.append((
        "AC1: type field supports CHECK_IN_48H",
        'CHECK_IN_48H = "CHECK_IN_48H"' in content,
    ))
    checks.append((
        "AC1: send_at field for scheduling dispatch time",
        "send_at: Mapped[datetime]" in content,
    ))
    checks.append((
        "AC1: channel field for SMS/EMAIL routing",
        "channel: Mapped[NotificationChannel]" in content,
    ))
    checks.append((
        "AC1: patient_id FK for contact info lookup",
        "patient_id: Mapped[uuid.UUID]" in content and
        'ForeignKey("patient.id"' in content,
    ))
    checks.append((
        "AC1: encounter_id FK for audit traceability",
        "encounter_id: Mapped[uuid.UUID]" in content and
        'ForeignKey("encounter.id"' in content,
    ))
    
    # AC Scenario 4: delivery_status=OPTED_OUT when patient.notification_opt_out=True
    checks.append((
        "AC4: delivery_status field exists",
        "delivery_status: Mapped[DeliveryStatus]" in content,
    ))
    checks.append((
        "AC4: OPTED_OUT status in DeliveryStatus enum",
        'OPTED_OUT = "OPTED_OUT"' in content,
    ))
    
    # Check idempotency for Pub/Sub redelivery
    checks.append((
        "Idempotency: idempotency_key field with unique constraint",
        "idempotency_key: Mapped[str]" in content and
        "unique=True" in content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_code_quality() -> tuple[int, int]:
    """Validate code quality standards.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    model_path = Path("backend/app/models/scheduled_notification.py")
    if not model_path.exists():
        print("❌ FAIL | Model file not found")
        return 0, 1
    
    content = model_path.read_text()
    
    # Check docstrings
    checks.append((
        "Module has docstring",
        content.startswith('"""') or content.startswith("'''"),
    ))
    checks.append((
        "ScheduledNotification class has docstring",
        re.search(r'class ScheduledNotification.*?""".*?"""', content, re.DOTALL) is not None,
    ))
    
    # Check type hints
    checks.append((
        "Uses from __future__ import annotations",
        "from __future__ import annotations" in content,
    ))
    checks.append((
        "All mapped columns use Mapped[] type hints",
        "Mapped[" in content and
        content.count("Mapped[") >= 11,  # 11 fields
    ))
    
    # Check enum documentation
    checks.append((
        "NotificationType enum has docstring",
        re.search(r'class NotificationType.*?""".*?"""', content, re.DOTALL) is not None,
    ))
    checks.append((
        "NotificationChannel enum has docstring",
        re.search(r'class NotificationChannel.*?""".*?"""', content, re.DOTALL) is not None,
    ))
    checks.append((
        "DeliveryStatus enum has docstring",
        re.search(r'class DeliveryStatus.*?""".*?"""', content, re.DOTALL) is not None,
    ))
    
    # Check comments on key fields
    checks.append((
        "idempotency_key has comment explaining format",
        'comment=' in content and "CHK48" in content,
    ))
    checks.append((
        "send_at has comment explaining calculation",
        'comment=' in content and "discharge_time + 48 hours" in content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_design_requirements() -> tuple[int, int]:
    """Validate design.md requirements.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    model_path = Path("backend/app/models/scheduled_notification.py")
    migration_files = list(Path("backend/alembic/versions").glob("*scheduled_notification*.py"))
    
    if not model_path.exists() or not migration_files:
        print("❌ FAIL | Required files not found")
        return 0, 1
    
    model_content = model_path.read_text()
    migration_content = migration_files[0].read_text()
    
    # DR-001: All DDL via Alembic
    checks.append((
        "DR-001: Table created via Alembic migration",
        "op.create_table" in migration_content,
    ))
    checks.append((
        "DR-001: Indexes created via Alembic",
        "op.create_index" in migration_content,
    ))
    
    # DR-005: Soft delete
    checks.append((
        "DR-005: deleted_at column for soft delete",
        "deleted_at: Mapped[datetime | None]" in model_content,
    ))
    checks.append((
        "DR-005: deleted_at nullable=True",
        "nullable=True" in model_content and "deleted_at" in model_content,
    ))
    
    # ADR-007: No PHI duplication
    checks.append((
        "ADR-007: No patient_phone field (PHI in patient table only)",
        "patient_phone" not in model_content.lower(),
    ))
    checks.append((
        "ADR-007: No patient_email field (PHI in patient table only)",
        "patient_email" not in model_content.lower(),
    ))
    checks.append((
        "ADR-007: No patient_name field (PHI in patient table only)",
        "patient_name" not in model_content.lower(),
    ))
    
    # Check design references in docstring
    checks.append((
        "Model docstring references US-041",
        "US-041" in model_content,
    ))
    checks.append((
        "Migration docstring references design.md DR-001",
        "DR-001" in migration_content or "design.md" in migration_content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def generate_final_report(all_passed: int, all_total: int) -> str:
    """Generate final validation report with approval status.
    
    Args:
        all_passed: Total checks passed
        all_total: Total checks run
    
    Returns:
        Report text
    """
    success_rate = (all_passed / all_total * 100) if all_total > 0 else 0
    
    report = f"""
{'='*60}
  VALIDATION SUMMARY
{'='*60}
Total Checks: {all_total}
Passed: {all_passed}
Failed: {all_total - all_passed}
Success Rate: {success_rate:.1f}%

"""
    
    if all_passed == all_total:
        report += f"""{'='*60}
  ✅ APPROVED FOR NEXT TASK
{'='*60}

US-041 TASK-001 (ScheduledNotification ORM + Migration) has passed
all {all_total} validation checks.

Files Created:
  - backend/app/models/scheduled_notification.py (ScheduledNotification ORM)
  - backend/alembic/versions/*_add_scheduled_notification_table.py (Migration)
  - backend/app/models/__init__.py (updated with new imports)

Schema Ready:
  - Table: scheduled_notification (11 columns)
  - Enums: NotificationType, NotificationChannel, DeliveryStatus
  - Indexes: send_at, delivery_status, patient_id, encounter_id
  - Constraints: unique(idempotency_key), FK(patient_id), FK(encounter_id)

Next Steps:
  1. Review migration with: alembic check
  2. Apply to dev DB: cd backend && alembic upgrade head
  3. Verify table: SELECT * FROM scheduled_notification LIMIT 0
  4. Proceed to TASK-002 (Notification scheduling service)
"""
    else:
        report += f"""{'='*60}
  ❌ BLOCKED — {all_total - all_passed} CHECKS FAILED
{'='*60}

US-041 TASK-001 has {all_total - all_passed} failing checks.
Review the failures above and fix before proceeding.

Common Issues:
  - Missing model fields or incorrect types
  - Migration syntax errors
  - Missing enum values
  - Indexes not created
  - Design requirements not met (DR-001, DR-005, ADR-007)
"""
    
    return report


def main() -> int:
    """Run all validation checks and generate report.
    
    Returns:
        0 if all checks pass, 1 otherwise
    """
    print("="*60)
    print("  US-041 TASK-001: ScheduledNotification ORM + Migration")
    print("  VALIDATION SCRIPT")
    print("="*60)
    print()
    
    all_passed = 0
    all_total = 0
    
    # Category 1: File Structure
    print("="*60)
    print("  1. File Structure Validation")
    print("="*60)
    passed, total = validate_file_structure()
    all_passed += passed
    all_total += total
    print()
    
    # Category 2: Model Definition
    print("="*60)
    print("  2. Model Definition Validation")
    print("="*60)
    passed, total = validate_model_definition()
    all_passed += passed
    all_total += total
    print()
    
    # Category 3: Database Schema
    print("="*60)
    print("  3. Database Schema Validation")
    print("="*60)
    passed, total = validate_database_schema()
    all_passed += passed
    all_total += total
    print()
    
    # Category 4: Migration Syntax
    print("="*60)
    print("  4. Migration Syntax Validation")
    print("="*60)
    passed, total = validate_migration_syntax()
    all_passed += passed
    all_total += total
    print()
    
    # Category 5: Acceptance Criteria
    print("="*60)
    print("  5. Acceptance Criteria Validation")
    print("="*60)
    passed, total = validate_acceptance_criteria()
    all_passed += passed
    all_total += total
    print()
    
    # Category 6: Code Quality
    print("="*60)
    print("  6. Code Quality Validation")
    print("="*60)
    passed, total = validate_code_quality()
    all_passed += passed
    all_total += total
    print()
    
    # Category 7: Design Requirements
    print("="*60)
    print("  7. Design Requirements Validation")
    print("="*60)
    passed, total = validate_design_requirements()
    all_passed += passed
    all_total += total
    print()
    
    # Final report
    report = generate_final_report(all_passed, all_total)
    print(report)
    
    return 0 if all_passed == all_total else 1


if __name__ == "__main__":
    sys.exit(main())
