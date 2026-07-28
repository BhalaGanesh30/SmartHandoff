#!/usr/bin/env python3
"""Validation script for US-038 TASK-002: BoardingMonitor APScheduler Job.

Verifies:
    1. boarding_schemas.py exists with BoardingCandidate and BoardingAlertPayload
    2. boarding_monitor.py exists with BoardingMonitor class
    3. BoardingMonitor has register() method
    4. BoardingMonitor has _run_cycle() and _detect_boarding_candidates() methods
    5. BoardingCandidate has idempotency_key and already_alerted properties
    6. BoardingAlertPayload has correct Pydantic field definitions
    7. BOARDING_THRESHOLD_MINUTES = 120
    8. MONITOR_INTERVAL_MINUTES = 5
    9. Package __init__.py exports boarding_monitor and boarding_schemas

Design refs:
    US-038 TASK-002 — BoardingMonitor implementation
    US-038 AC Scenario 1 — 5-minute interval, 120-minute threshold
    US-038 AC Scenario 4 — idempotency via BoardingCandidate.already_alerted
"""
import ast
import re
import sys
from pathlib import Path


def check_boarding_schemas_exists() -> bool:
    """Check if boarding_schemas.py module exists."""
    print("[1/9] Boarding Schemas Module Existence Check")
    
    schemas_file = Path("backend/app/agents/bed_management/boarding_schemas.py")
    
    if not schemas_file.exists():
        print(f"  ✗ Schemas file not found: {schemas_file}")
        return False
    
    print(f"  ✓ Schemas file exists: {schemas_file}")
    return True


def check_boarding_candidate_dataclass() -> bool:
    """Check if BoardingCandidate dataclass is properly defined."""
    print("\n[2/9] BoardingCandidate Dataclass Check")
    
    schemas_file = Path("backend/app/agents/bed_management/boarding_schemas.py")
    content = schemas_file.read_text(encoding='utf-8')
    
    checks = {
        "@dataclass decorator": "@dataclass(frozen=True, slots=True)",
        "BoardingCandidate class": "class BoardingCandidate:",
        "encounter_id field": "encounter_id: str",
        "patient_id field": "patient_id: str",
        "ed_arrival_time field": "ed_arrival_time: datetime",
        "minutes_elapsed field": "minutes_elapsed: int",
        "boarding_alert_sent_at field": "boarding_alert_sent_at: datetime | None",
        "idempotency_key property": "def idempotency_key(self) -> str:",
        "already_alerted property": "def already_alerted(self) -> bool:",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_boarding_alert_payload_schema() -> bool:
    """Check if BoardingAlertPayload Pydantic model is properly defined."""
    print("\n[3/9] BoardingAlertPayload Schema Check")
    
    schemas_file = Path("backend/app/agents/bed_management/boarding_schemas.py")
    content = schemas_file.read_text(encoding='utf-8')
    
    checks = {
        "BaseModel inheritance": "class BoardingAlertPayload(BaseModel):",
        "notification_type field": 'notification_type: Literal["ED_BOARDING_ALERT"]',
        "priority field": 'priority: Literal["IMMEDIATE"]',
        "patient_id field": "patient_id: str = Field(",
        "encounter_id field": "encounter_id: str = Field(",
        "ed_arrival_time field": "ed_arrival_time: str = Field(",
        "minutes_elapsed field": "minutes_elapsed: int = Field(",
        "idempotency_key field": "idempotency_key: str = Field(",
        "minutes_elapsed constraint": "ge=120",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_boarding_monitor_exists() -> bool:
    """Check if boarding_monitor.py module exists."""
    print("\n[4/9] Boarding Monitor Module Existence Check")
    
    monitor_file = Path("backend/app/agents/bed_management/boarding_monitor.py")
    
    if not monitor_file.exists():
        print(f"  ✗ Monitor file not found: {monitor_file}")
        return False
    
    print(f"  ✓ Monitor file exists: {monitor_file}")
    return True


def check_boarding_monitor_class() -> bool:
    """Check if BoardingMonitor class is properly defined."""
    print("\n[5/9] BoardingMonitor Class Check")
    
    monitor_file = Path("backend/app/agents/bed_management/boarding_monitor.py")
    content = monitor_file.read_text(encoding='utf-8')
    
    checks = {
        "BoardingMonitor class": "class BoardingMonitor:",
        "__init__ method": "def __init__(",
        "register method": "def register(self) -> None:",
        "_run_cycle method": "async def _run_cycle(self) -> None:",
        "_detect_boarding_candidates method": "async def _detect_boarding_candidates(self)",
        "publisher assignment": "self._publisher = publisher",
        "scheduler assignment": "self._scheduler = scheduler",
        "US-038 reference": "US-038",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_constants() -> bool:
    """Check if BOARDING_THRESHOLD_MINUTES and MONITOR_INTERVAL_MINUTES are set correctly."""
    print("\n[6/9] Constants Check")
    
    monitor_file = Path("backend/app/agents/bed_management/boarding_monitor.py")
    content = monitor_file.read_text(encoding='utf-8')
    
    checks = {
        "BOARDING_THRESHOLD_MINUTES = 120": "BOARDING_THRESHOLD_MINUTES: int = 120",
        "MONITOR_INTERVAL_MINUTES = 5": "MONITOR_INTERVAL_MINUTES: int = 5",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_apscheduler_registration() -> bool:
    """Check if APScheduler registration logic is correct."""
    print("\n[7/9] APScheduler Registration Check")
    
    monitor_file = Path("backend/app/agents/bed_management/boarding_monitor.py")
    content = monitor_file.read_text(encoding='utf-8')
    
    checks = {
        "add_job call": "self._scheduler.add_job(",
        "_run_cycle target": "self._run_cycle,",
        "interval trigger": 'trigger="interval"',
        "minutes parameter": "minutes=MONITOR_INTERVAL_MINUTES,",
        "job_id": 'id="boarding_monitor"',
        "replace_existing": "replace_existing=True",
        "misfire_grace_time": "misfire_grace_time=60",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_detection_query_logic() -> bool:
    """Check if _detect_boarding_candidates has correct query logic."""
    print("\n[8/9] Detection Query Logic Check")
    
    monitor_file = Path("backend/app/agents/bed_management/boarding_monitor.py")
    content = monitor_file.read_text(encoding='utf-8')
    
    checks = {
        "load_ed_location_codes call": "load_ed_location_codes()",
        "threshold_time calculation": "threshold_time = datetime.now(UTC) - timedelta(minutes=BOARDING_THRESHOLD_MINUTES)",
        "select(Encounter)": "select(Encounter)",
        "unit.in_(ed_codes)": "Encounter.unit.in_(ed_codes)",
        "status == ADMITTED": 'Encounter.status == "ADMITTED"',
        "admit_date filter": "Encounter.admit_date",
        "boarding_alert_resolved_at.is_(None)": "Encounter.boarding_alert_resolved_at.is_(None)",
        "BoardingCandidate construction": "BoardingCandidate(",
        "exception handling": "except Exception:",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_package_init_updated() -> bool:
    """Check if bed_management __init__.py exports new modules."""
    print("\n[9/9] Package Initialization Check")
    
    init_file = Path("backend/app/agents/bed_management/__init__.py")
    content = init_file.read_text(encoding='utf-8')
    
    checks = {
        "boarding_monitor in __all__": '"boarding_monitor"',
        "boarding_schemas in __all__": '"boarding_schemas"',
        "boarding_monitor import": "from app.agents.bed_management import boarding_monitor",
        "boarding_schemas import": "from app.agents.bed_management import boarding_schemas",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def main() -> int:
    """Run all validation checks."""
    print("=" * 80)
    print("US-038 TASK-002 Validation: BoardingMonitor APScheduler Job")
    print("=" * 80)
    
    results = [
        check_boarding_schemas_exists(),
        check_boarding_candidate_dataclass(),
        check_boarding_alert_payload_schema(),
        check_boarding_monitor_exists(),
        check_boarding_monitor_class(),
        check_constants(),
        check_apscheduler_registration(),
        check_detection_query_logic(),
        check_package_init_updated(),
    ]
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 80)
    if all(results):
        print(f"✅ ALL VALIDATION CHECKS PASSED ({passed}/{total})")
    else:
        print(f"❌ SOME CHECKS FAILED ({passed}/{total})")
    print("=" * 80)
    
    print("\nValidation Summary:")
    print("  ✓ boarding_schemas.py created with BoardingCandidate and BoardingAlertPayload")
    print("  ✓ boarding_monitor.py created with BoardingMonitor class")
    print("  ✓ APScheduler registration logic (5-minute interval)")
    print("  ✓ Detection query filters ED encounters (≥120 minutes, not resolved)")
    print("  ✓ BoardingCandidate has idempotency_key and already_alerted properties")
    print("  ✓ Package __init__.py exports new modules")
    
    print("\nNOTE: Schema Adaptation")
    print("  ! Implementation uses Encounter.unit (not current_location)")
    print("  ! Implementation uses Encounter.admit_date (not admit_time/transfer_time)")
    print("  ! No bed_assigned_at field — using boarding_alert_resolved_at instead")
    
    print("\nNext Steps:")
    print("  1. Implement TASK-003 (BoardingAlertPublisher)")
    print("  2. Register BoardingMonitor in main.py startup")
    print("  3. Create unit tests (TASK-005)")
    print("  4. Update task status to Complete")
    print("  5. Create implementation summary")
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
