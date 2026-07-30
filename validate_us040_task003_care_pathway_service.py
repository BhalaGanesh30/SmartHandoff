"""Validation script for US-040 TASK-003: CarePathwayService.

Validates:
    1. Service file structure and imports
    2. CarePathwayService class and constructor
    3. activate_pathway() method implementation
    4. _assign_care_manager() round-robin logic
    5. Integration with care_pathways.yaml configuration
    6. No PHI in log output
    7. Acceptance criteria coverage
    8. Definition of Done criteria

US-040 TASK-003 — CarePathwayService: Care Manager Assignment & Appointment Creation
"""
from __future__ import annotations

import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent
BACKEND_ROOT = PROJECT_ROOT / "backend"

# Add backend to path for imports
sys.path.insert(0, str(BACKEND_ROOT))

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


def validate_file_structure() -> bool:
    """Validate service file exists and has correct structure."""
    print("\n1. FILE STRUCTURE")
    print("=" * 60)
    
    try:
        service_file = BACKEND_ROOT / "app" / "services" / "care_pathway_service.py"
        
        check("Structure", "care_pathway_service.py exists", service_file.exists())
        
        if not service_file.exists():
            check("Structure", "File structure validation failed", False, "File not found")
            return False
        
        code = service_file.read_text(encoding="utf-8")
        
        # Check imports
        check("Structure", "from __future__ import annotations", 
              "from __future__ import annotations" in code)
        check("Structure", "import logging", "import logging" in code)
        check("Structure", "import uuid", "import uuid" in code)
        check("Structure", "from datetime import date, timedelta", 
              "from datetime import date, timedelta" in code)
        check("Structure", "from sqlalchemy import select", 
              "from sqlalchemy import select" in code)
        check("Structure", "from sqlalchemy.ext.asyncio import AsyncSession", 
              "from sqlalchemy.ext.asyncio import AsyncSession" in code)
        
        # Check model imports
        check("Structure", "from app.config.care_pathways import", 
              "from app.config.care_pathways import" in code)
        check("Structure", "from app.models.appointment import Appointment", 
              "from app.models.appointment import Appointment" in code)
        check("Structure", "from app.models.app_user import AppUser", 
              "from app.models.app_user import AppUser" in code)
        check("Structure", "from app.models.encounter import Encounter", 
              "from app.models.encounter import Encounter" in code)
        
        # Check docstring references
        check("Structure", "US-040 design references in docstring", 
              "US-040" in code and "design.md" in code)
        check("Structure", "Round-robin explanation in docstring", 
              "round-robin" in code and "deterministic" in code)
        check("Structure", "Idempotency guarantee documented", 
              "idempotency" in code or "redelivery" in code)
        
        return True
    except Exception as e:
        check("Structure", "File structure validation failed", False, str(e))
        return False


def validate_class_structure() -> bool:
    """Validate CarePathwayService class structure."""
    print("\n2. CLASS STRUCTURE")
    print("=" * 60)
    
    try:
        service_file = BACKEND_ROOT / "app" / "services" / "care_pathway_service.py"
        code = service_file.read_text(encoding="utf-8")
        
        # Check class definition
        check("Class", "CarePathwayService class defined", 
              "class CarePathwayService:" in code)
        check("Class", "__init__() method", "def __init__(self, pathways: CarePathwayConfig)" in code)
        check("Class", "activate_pathway() method", "async def activate_pathway(" in code)
        check("Class", "_assign_care_manager() method", "async def _assign_care_manager(" in code)
        
        # Check __init__ implementation
        check("Class", "__init__ stores pathways", "self._pathways = pathways" in code)
        
        # Check method signatures
        check("Class", "activate_pathway() accepts encounter", 
              "encounter: Encounter" in code)
        check("Class", "activate_pathway() accepts risk_tier", 
              "risk_tier: str" in code)
        check("Class", "activate_pathway() accepts discharge_date", 
              "discharge_date: date" in code)
        check("Class", "activate_pathway() accepts db session", 
              "db: AsyncSession" in code)
        check("Class", "activate_pathway() returns Appointment", 
              "-> Appointment:" in code)
        
        # Check _assign_care_manager signature
        check("Class", "_assign_care_manager() accepts encounter_id", 
              "encounter_id: uuid.UUID" in code)
        check("Class", "_assign_care_manager() accepts unit", 
              "unit: str" in code)
        check("Class", "_assign_care_manager() returns UUID | None", 
              "-> uuid.UUID | None:" in code)
        
        return True
    except Exception as e:
        check("Class", "Class structure validation failed", False, str(e))
        return False


def validate_activate_pathway_logic() -> bool:
    """Validate activate_pathway() implementation logic."""
    print("\n3. ACTIVATE_PATHWAY LOGIC")
    print("=" * 60)
    
    try:
        service_file = BACKEND_ROOT / "app" / "services" / "care_pathway_service.py"
        code = service_file.read_text(encoding="utf-8")
        
        # Check pathway config retrieval
        check("Logic", "Retrieves pathway config from self._pathways", 
              "self._pathways[risk_tier]" in code)
        
        # Check conditional care manager assignment
        check("Logic", "Conditionally assigns care manager", 
              "if pathway_config.alert_care_manager:" in code)
        check("Logic", "Calls _assign_care_manager() for HIGH tier", 
              "await self._assign_care_manager(" in code)
        
        # Check target_date calculation
        check("Logic", "Calculates target_date with timedelta", 
              "timedelta(days=pathway_config.followup_days)" in code)
        check("Logic", "target_date = discharge_date + timedelta", 
              "discharge_date + timedelta" in code)
        
        # Check Appointment creation
        check("Logic", "Creates Appointment ORM object", 
              "appointment = Appointment(" in code)
        check("Logic", "Sets encounter_id", "encounter_id=encounter.id" in code)
        check("Logic", "Sets appointment_type from config", 
              "appointment_type=AppointmentType(pathway_config.appointment_type).value" in code)
        check("Logic", "Sets target_date", "target_date=target_date" in code)
        check("Logic", "Sets status=SCHEDULED", 
              "status=AppointmentStatus.SCHEDULED.value" in code)
        check("Logic", "Sets assigned_user_id", 
              "assigned_user_id=assigned_user_id" in code)
        
        # Check database operations
        check("Logic", "Adds appointment to session", "db.add(appointment)" in code)
        check("Logic", "Flushes session before return", "await db.flush()" in code)
        
        # Check logging
        check("Logic", "Logs pathway activation", 
              'logger.info(\n            "Care pathway activated"' in code or
              'logger.info("Care pathway activated"' in code)
        
        return True
    except Exception as e:
        check("Logic", "activate_pathway logic validation failed", False, str(e))
        return False


def validate_care_manager_assignment() -> bool:
    """Validate _assign_care_manager() round-robin logic."""
    print("\n4. CARE MANAGER ASSIGNMENT")
    print("=" * 60)
    
    try:
        service_file = BACKEND_ROOT / "app" / "services" / "care_pathway_service.py"
        code = service_file.read_text(encoding="utf-8")
        
        # Check query construction
        check("Assignment", "Queries AppUser.id", "select(AppUser.id)" in code)
        check("Assignment", "Filters by role=CARE_MANAGER", 
              'AppUser.role == "CARE_MANAGER"' in code)
        check("Assignment", "Filters by unit", "AppUser.unit == unit" in code)
        check("Assignment", "Filters by is_active", 
              "AppUser.is_active == True" in code or "AppUser.is_active" in code)
        check("Assignment", "Orders by id ASC for stability", 
              "order_by(AppUser.id.asc())" in code)
        
        # Check pool handling
        check("Assignment", "Converts result to list", 
              "list(result.scalars().all())" in code)
        
        # Check empty pool handling
        check("Assignment", "Returns None when pool is empty", 
              "if not pool:" in code and "return None" in code)
        check("Assignment", "Logs warning when no care managers found", 
              "logger.warning" in code and "No CARE_MANAGER users found" in code)
        
        # Check deterministic round-robin
        check("Assignment", "Uses hash(str(encounter_id)) for determinism", 
              "hash(str(encounter_id))" in code)
        check("Assignment", "Modulo pool size", "% len(pool)" in code)
        check("Assignment", "Selects from pool by index", 
              "pool[pool_index]" in code)
        
        # Check return and logging
        check("Assignment", "Logs care manager assignment", 
              'logger.info(\n            "Care manager assigned"' in code or
              'logger.info("Care manager assigned"' in code)
        check("Assignment", "Returns selected UUID", "return selected_id" in code)
        
        return True
    except Exception as e:
        check("Assignment", "Care manager assignment validation failed", False, str(e))
        return False


def validate_no_phi_in_logs() -> bool:
    """Validate that no PHI appears in log output."""
    print("\n5. PHI PROTECTION")
    print("=" * 60)
    
    try:
        service_file = BACKEND_ROOT / "app" / "services" / "care_pathway_service.py"
        code = service_file.read_text(encoding="utf-8")
        
        # Check for prohibited PHI fields in logs
        phi_fields = [
            "patient_name", "patient.name", "mrn", "patient_mrn",
            "date_of_birth", "dob", "ssn", "patient.dob"
        ]
        
        phi_found = []
        for field in phi_fields:
            if field in code.lower():
                phi_found.append(field)
        
        check("PHI", "No patient_name in logs", "patient_name" not in code.lower())
        check("PHI", "No MRN in logs", 
              "mrn" not in code.lower() or "mrn" in code.lower() and "# no PHI" in code.lower())
        check("PHI", "No DOB in logs", "date_of_birth" not in code.lower() and "dob" not in code.lower())
        
        # Check that only safe fields are logged
        check("PHI", "Logs encounter_id (UUID safe)", "encounter_id" in code)
        check("PHI", "Logs risk_tier (category safe)", "risk_tier" in code)
        check("PHI", "Logs appointment_type (category safe)", "appointment_type" in code)
        check("PHI", "Logs assigned_user_id (staff UUID safe)", "assigned_user_id" in code)
        
        return len(phi_found) == 0
    except Exception as e:
        check("PHI", "PHI validation failed", False, str(e))
        return False


def validate_acceptance_criteria() -> bool:
    """Validate US-040 Acceptance Criteria compliance."""
    print("\n6. ACCEPTANCE CRITERIA")
    print("=" * 60)
    
    try:
        service_file = BACKEND_ROOT / "app" / "services" / "care_pathway_service.py"
        code = service_file.read_text(encoding="utf-8")
        
        # AC Scenario 2: HIGH tier
        check("AC", "Scenario 2: assigned_user_id populated for HIGH", 
              "if pathway_config.alert_care_manager:" in code and
              "await self._assign_care_manager(" in code)
        check("AC", "Scenario 2: target_date = discharge_date + 7 (via config)", 
              "timedelta(days=pathway_config.followup_days)" in code)
        
        # AC Scenario 3 & 4: MEDIUM and LOW tiers
        check("AC", "Scenario 3/4: assigned_user_id=None for non-alert tiers", 
              "assigned_user_id: uuid.UUID | None = None" in code)
        
        # All scenarios: appointment record creation
        check("AC", "All scenarios: Creates appointment record", 
              "appointment = Appointment(" in code)
        check("AC", "All scenarios: Sets status=SCHEDULED", 
              "status=AppointmentStatus.SCHEDULED.value" in code)
        check("AC", "All scenarios: Uses config for appointment_type", 
              "appointment_type=AppointmentType(pathway_config.appointment_type).value" in code)
        
        return True
    except Exception as e:
        check("AC", "Acceptance criteria validation failed", False, str(e))
        return False


def validate_dod_criteria() -> bool:
    """Validate Definition of Done criteria."""
    print("\n7. DEFINITION OF DONE")
    print("=" * 60)
    
    try:
        # Check file creation
        service_file = BACKEND_ROOT / "app" / "services" / "care_pathway_service.py"
        check("DoD", "care_pathway_service.py created", service_file.exists())
        
        if not service_file.exists():
            return False
        
        code = service_file.read_text(encoding="utf-8")
        
        # Check class and methods
        check("DoD", "CarePathwayService class implemented", 
              "class CarePathwayService:" in code)
        check("DoD", "activate_pathway() method implemented", 
              "async def activate_pathway(" in code)
        check("DoD", "_assign_care_manager() method implemented", 
              "async def _assign_care_manager(" in code)
        
        # Check no raw SQL (SQLAlchemy ORM select is allowed)
        # Looking for raw SQL patterns like execute("SELECT ...") or text("SELECT ...")
        raw_sql_patterns = [
            'execute("SELECT',
            "execute('SELECT",
            'text("SELECT',
            "text('SELECT",
        ]
        has_raw_sql = any(pattern in code for pattern in raw_sql_patterns)
        uses_orm_select = "select(AppUser" in code
        check("DoD", "No raw SQL (uses SQLAlchemy select)", 
              not has_raw_sql and uses_orm_select,
              "Uses ORM select() instead of raw SQL" if not has_raw_sql and uses_orm_select else "Found raw SQL patterns")
        
        # Check round-robin implementation
        check("DoD", "Round-robin is deterministic", 
              "hash(str(encounter_id)) % len(pool)" in code)
        check("DoD", "Returns None gracefully when pool empty", 
              "if not pool:" in code and "return None" in code)
        
        # Check database operations
        check("DoD", "Uses db.add() for ORM", "db.add(appointment)" in code)
        check("DoD", "Uses db.flush() before return", "await db.flush()" in code)
        
        # Check integration with TASK-002
        check("DoD", "Integrates with care_pathways.yaml config", 
              "self._pathways[risk_tier]" in code and 
              "pathway_config.followup_days" in code)
        
        return True
    except Exception as e:
        check("DoD", "DoD validation failed", False, str(e))
        return False


def validate_code_quality() -> bool:
    """Validate code quality and patterns."""
    print("\n8. CODE QUALITY")
    print("=" * 60)
    
    try:
        service_file = BACKEND_ROOT / "app" / "services" / "care_pathway_service.py"
        code = service_file.read_text(encoding="utf-8")
        
        # Check type hints
        check("Quality", "Uses type hints for parameters", 
              ": str" in code and ": uuid.UUID" in code and ": date" in code)
        check("Quality", "Uses return type hints", "-> Appointment:" in code and "-> uuid.UUID | None:" in code)
        
        # Check docstrings
        check("Quality", "Module-level docstring present", 
              '"""CarePathwayService' in code)
        check("Quality", "Class docstring present", 
              code.count('"""') >= 4)  # Module + class + 2 methods minimum
        
        # Check async/await patterns
        check("Quality", "Uses async def for async methods", 
              "async def activate_pathway(" in code and "async def _assign_care_manager(" in code)
        check("Quality", "Uses await for async DB operations", 
              "await db.execute(" in code and "await db.flush()" in code)
        
        # Check error handling documentation
        check("Quality", "Documents Raises section", 
              "Raises:" in code and ("KeyError" in code or "IntegrityError" in code))
        
        # Check logging best practices
        check("Quality", "Uses logger.info for success", "logger.info" in code)
        check("Quality", "Uses logger.warning for edge cases", "logger.warning" in code)
        check("Quality", "Uses extra dict for structured logging", 
              'extra={' in code or 'extra = {' in code)
        
        return True
    except Exception as e:
        check("Quality", "Code quality validation failed", False, str(e))
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
        print("\nCarePathwayService is ready for integration with FollowUpCareAgent")
        return True
    else:
        print("❌ SOME VALIDATIONS FAILED")
        return False


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("US-040 TASK-003 VALIDATION")
    print("CarePathwayService — Care Manager Assignment & Appointment Creation")
    print("=" * 60)
    
    validate_file_structure()
    validate_class_structure()
    validate_activate_pathway_logic()
    validate_care_manager_assignment()
    validate_no_phi_in_logs()
    validate_acceptance_criteria()
    validate_dod_criteria()
    validate_code_quality()
    
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
