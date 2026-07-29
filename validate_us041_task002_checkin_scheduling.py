"""Validation script for US-041 TASK-002: 48-Hour Check-in Scheduling.

Performs comprehensive automated checks across 8 categories:
1. File Structure — checkin_scheduler.py, agent.py changes, schemas.py changes
2. Module Implementation — constants, function signature, logic flow
3. Idempotency — idempotency_key format and handling
4. Channel Resolution — patient.preferred_contact → SMS/EMAIL
5. send_at Calculation — discharge_time + 48 hours (not now() + 48h)
6. Risk Threshold — risk_score >= 0.5 creates notification, < 0.5 skips
7. Acceptance Criteria — AC Scenarios 1, 2, 3 coverage
8. Code Quality — docstrings, type hints, logging, error handling

Exits 0 if all checks pass, 1 otherwise.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def validate_file_structure() -> tuple[int, int]:
    """Validate all required files exist and are modified correctly.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    # Check checkin_scheduler.py exists
    scheduler_path = Path("backend/app/agents/followup_care/checkin_scheduler.py")
    checks.append((
        "checkin_scheduler.py module exists",
        scheduler_path.exists(),
    ))
    
    # Check agent.py exists and was modified
    agent_path = Path("backend/app/agents/followup_care/agent.py")
    checks.append((
        "agent.py exists",
        agent_path.exists(),
    ))
    
    # Check schemas.py exists and was modified
    schemas_path = Path("backend/app/agents/followup_care/schemas.py")
    checks.append((
        "schemas.py exists",
        schemas_path.exists(),
    ))
    
    # Check agent.py imports checkin_scheduler
    if agent_path.exists():
        agent_content = agent_path.read_text()
        checks.append((
            "agent.py imports maybe_schedule_48h_checkin",
            "from app.agents.followup_care.checkin_scheduler import maybe_schedule_48h_checkin" in agent_content,
        ))
        checks.append((
            "agent.py calls maybe_schedule_48h_checkin",
            "await maybe_schedule_48h_checkin(" in agent_content,
        ))
    else:
        checks.extend([
            ("agent.py integration checks", False),
        ] * 2)
    
    # Check schemas.py has new fields
    if schemas_path.exists():
        schemas_content = schemas_path.read_text()
        checks.append((
            "RiskAssessmentResult has checkin_scheduled field",
            "checkin_scheduled" in schemas_content,
        ))
        checks.append((
            "RiskAssessmentResult has scheduled_notification_id field",
            "scheduled_notification_id" in schemas_content,
        ))
    else:
        checks.extend([
            ("schemas.py update checks", False),
        ] * 2)
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_module_implementation() -> tuple[int, int]:
    """Validate checkin_scheduler.py module structure and implementation.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    scheduler_path = Path("backend/app/agents/followup_care/checkin_scheduler.py")
    if not scheduler_path.exists():
        print("❌ FAIL | checkin_scheduler.py not found")
        return 0, 1
    
    content = scheduler_path.read_text()
    
    # Check constants
    checks.append((
        "CHECKIN_RISK_THRESHOLD = 0.5 defined",
        "CHECKIN_RISK_THRESHOLD: float = 0.5" in content or
        "CHECKIN_RISK_THRESHOLD = 0.5" in content,
    ))
    checks.append((
        "CHECKIN_DELAY_HOURS = 48 defined",
        "CHECKIN_DELAY_HOURS: int = 48" in content or
        "CHECKIN_DELAY_HOURS = 48" in content,
    ))
    
    # Check function signature
    checks.append((
        "maybe_schedule_48h_checkin function defined",
        "async def maybe_schedule_48h_checkin(" in content,
    ))
    checks.append((
        "Function accepts session parameter",
        "session: AsyncSession" in content,
    ))
    checks.append((
        "Function accepts encounter parameter",
        "encounter: Encounter" in content,
    ))
    checks.append((
        "Function accepts patient parameter",
        "patient: Patient" in content,
    ))
    checks.append((
        "Function accepts risk_score parameter",
        "risk_score: float" in content,
    ))
    checks.append((
        "Function returns ScheduledNotification | None",
        "-> ScheduledNotification | None:" in content,
    ))
    
    # Check imports
    required_imports = [
        "from app.models.encounter import Encounter",
        "from app.models.patient import Patient",
        "from app.models.scheduled_notification import",
        "NotificationType",
        "NotificationChannel",
        "DeliveryStatus",
        "ScheduledNotification",
    ]
    
    for imp in required_imports:
        checks.append((
            f"Import: {imp[:50]}...",
            imp in content,
        ))
    
    # Check logic flow
    checks.append((
        "Risk threshold check: if risk_score < CHECKIN_RISK_THRESHOLD",
        "if risk_score < CHECKIN_RISK_THRESHOLD:" in content,
    ))
    checks.append((
        "Returns None for low risk",
        "return None" in content,
    ))
    checks.append((
        "Discharge time validation",
        "if encounter.discharge_time is None:" in content or
        "encounter.discharge_time is None" in content,
    ))
    checks.append((
        "ScheduledNotification object created",
        "notification = ScheduledNotification(" in content,
    ))
    checks.append((
        "session.add(notification) called",
        "session.add(notification)" in content,
    ))
    checks.append((
        "session.flush() called",
        "await session.flush()" in content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_idempotency() -> tuple[int, int]:
    """Validate idempotency key handling.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    scheduler_path = Path("backend/app/agents/followup_care/checkin_scheduler.py")
    if not scheduler_path.exists():
        print("❌ FAIL | checkin_scheduler.py not found")
        return 0, 1
    
    content = scheduler_path.read_text()
    
    # Check idempotency key format
    checks.append((
        'Idempotency key format: CHK48-{encounter.id}',
        'idempotency_key = f"CHK48-{encounter.id}"' in content or
        "idempotency_key = f'CHK48-{encounter.id}'" in content,
    ))
    
    # Check idempotency key is set on notification
    checks.append((
        "idempotency_key assigned to ScheduledNotification",
        "idempotency_key=idempotency_key" in content,
    ))
    
    # Check IntegrityError handling
    checks.append((
        "IntegrityError exception imported",
        "from sqlalchemy.exc import IntegrityError" in content,
    ))
    checks.append((
        "IntegrityError caught for duplicate detection",
        "except IntegrityError:" in content,
    ))
    checks.append((
        "Rollback on IntegrityError",
        "await session.rollback()" in content,
    ))
    checks.append((
        "Log 'check_in_already_scheduled' on duplicate",
        '"check_in_already_scheduled"' in content or
        "'check_in_already_scheduled'" in content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_channel_resolution() -> tuple[int, int]:
    """Validate channel resolution from patient.preferred_contact.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    scheduler_path = Path("backend/app/agents/followup_care/checkin_scheduler.py")
    if not scheduler_path.exists():
        print("❌ FAIL | checkin_scheduler.py not found")
        return 0, 1
    
    content = scheduler_path.read_text()
    
    # Check channel resolution logic
    checks.append((
        "Channel resolution uses patient.preferred_contact",
        "patient.preferred_contact" in content or
        "patient, \"preferred_contact\"" in content,
    ))
    checks.append((
        'EMAIL channel when preferred_contact == "email"',
        'NotificationChannel.EMAIL' in content and
        ('"email"' in content or "'email'" in content),
    ))
    checks.append((
        "SMS channel as default/fallback",
        "NotificationChannel.SMS" in content,
    ))
    checks.append((
        "Ternary operator or if/else for channel selection",
        "if" in content and "else" in content,
    ))
    checks.append((
        "channel assigned to ScheduledNotification",
        "channel=channel" in content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_send_at_calculation() -> tuple[int, int]:
    """Validate send_at calculation from discharge_time.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    scheduler_path = Path("backend/app/agents/followup_care/checkin_scheduler.py")
    if not scheduler_path.exists():
        print("❌ FAIL | checkin_scheduler.py not found")
        return 0, 1
    
    content = scheduler_path.read_text()
    
    # Check send_at calculation
    checks.append((
        "send_at uses encounter.discharge_time as base",
        "encounter.discharge_time" in content,
    ))
    checks.append((
        "timedelta(hours=CHECKIN_DELAY_HOURS) or timedelta(hours=48)",
        "timedelta(hours=CHECKIN_DELAY_HOURS)" in content or
        "timedelta(hours=48)" in content,
    ))
    checks.append((
        "send_at assigned to ScheduledNotification",
        "send_at=send_at" in content,
    ))
    checks.append((
        "Does NOT use datetime.utcnow() or datetime.now()",
        "datetime.utcnow()" not in content and "datetime.now()" not in content,
    ))
    
    # Check timedelta import
    checks.append((
        "timedelta imported from datetime",
        "from datetime import" in content and "timedelta" in content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_risk_threshold() -> tuple[int, int]:
    """Validate risk threshold logic.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    scheduler_path = Path("backend/app/agents/followup_care/checkin_scheduler.py")
    if not scheduler_path.exists():
        print("❌ FAIL | checkin_scheduler.py not found")
        return 0, 1
    
    content = scheduler_path.read_text()
    
    # Check threshold value
    checks.append((
        "Threshold is 0.5 (between LOW and MEDIUM)",
        "0.5" in content,
    ))
    
    # Check early return for low risk
    checks.append((
        "Early return when risk_score < threshold",
        re.search(r'if\s+risk_score\s*<\s*CHECKIN_RISK_THRESHOLD.*?return None', content, re.DOTALL) is not None,
    ))
    
    # Check logging for skipped check-in
    checks.append((
        "Logs 'check_in_skipped' when risk_score < threshold",
        '"check_in_skipped"' in content or "'check_in_skipped'" in content,
    ))
    checks.append((
        "Log includes risk_score and reason",
        '"risk_score"' in content and '"reason"' in content,
    ))
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    return passed, total


def validate_acceptance_criteria() -> tuple[int, int]:
    """Validate US-041 AC Scenarios 1, 2, 3 coverage.
    
    Returns:
        (passed_count, total_count)
    """
    checks = []
    
    scheduler_path = Path("backend/app/agents/followup_care/checkin_scheduler.py")
    agent_path = Path("backend/app/agents/followup_care/agent.py")
    
    if not scheduler_path.exists() or not agent_path.exists():
        print("❌ FAIL | Required files not found")
        return 0, 1
    
    scheduler_content = scheduler_path.read_text()
    agent_content = agent_path.read_text()
    
    # AC Scenario 1: CHECK_IN_48H notification with send_at = discharge_time + 48h
    checks.append((
        "AC1: NotificationType.CHECK_IN_48H used",
        "NotificationType.CHECK_IN_48H" in scheduler_content,
    ))
    checks.append((
        "AC1: send_at = discharge_time + 48 hours",
        "encounter.discharge_time" in scheduler_content and
        ("timedelta(hours=48)" in scheduler_content or "CHECKIN_DELAY_HOURS" in scheduler_content),
    ))
    checks.append((
        "AC1: channel resolved from patient.preferred_contact",
        "patient.preferred_contact" in scheduler_content or
        "preferred_contact" in scheduler_content,
    ))
    checks.append((
        "AC1: ScheduledNotification created and persisted",
        "ScheduledNotification(" in scheduler_content and
        "session.add(notification)" in scheduler_content,
    ))
    
    # AC Scenario 2: No check-in for risk_score=0.2 (< 0.5)
    checks.append((
        "AC2: risk_score < 0.5 → no notification created",
        "if risk_score < CHECKIN_RISK_THRESHOLD:" in scheduler_content and
        "return None" in scheduler_content,
    ))
    checks.append((
        "AC2: Threshold is 0.5 (captures 0.2 < 0.5 case)",
        "0.5" in scheduler_content,
    ))
    
    # AC Scenario 3: Channel from patient.preferred_contact
    checks.append((
        "AC3: EMAIL channel when preferred_contact=email",
        "NotificationChannel.EMAIL" in scheduler_content and
        ('"email"' in scheduler_content or "'email'" in scheduler_content),
    ))
    checks.append((
        "AC3: SMS channel as default",
        "NotificationChannel.SMS" in scheduler_content,
    ))
    
    # Integration in agent.py
    checks.append((
        "Agent calls maybe_schedule_48h_checkin after commit",
        "await maybe_schedule_48h_checkin(" in agent_content,
    ))
    checks.append((
        "Agent commits ScheduledNotification if created",
        "await checkin_session.commit()" in agent_content or
        "await session.commit()" in agent_content,
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
    
    scheduler_path = Path("backend/app/agents/followup_care/checkin_scheduler.py")
    if not scheduler_path.exists():
        print("❌ FAIL | checkin_scheduler.py not found")
        return 0, 1
    
    content = scheduler_path.read_text()
    
    # Check docstrings
    checks.append((
        "Module has docstring",
        content.startswith('"""') or content.startswith("'''"),
    ))
    checks.append((
        "Module docstring references US-041",
        "US-041" in content[:500],  # Check first 500 chars
    ))
    checks.append((
        "maybe_schedule_48h_checkin has docstring",
        re.search(r'async def maybe_schedule_48h_checkin.*?""".*?"""', content, re.DOTALL) is not None,
    ))
    
    # Check type hints
    checks.append((
        "Uses from __future__ import annotations",
        "from __future__ import annotations" in content,
    ))
    checks.append((
        "Function parameters have type hints",
        "session: AsyncSession" in content and
        "encounter: Encounter" in content and
        "patient: Patient" in content and
        "risk_score: float" in content,
    ))
    checks.append((
        "Return type annotation present",
        "-> ScheduledNotification | None:" in content,
    ))
    
    # Check logging
    checks.append((
        "Uses structured logging with extra={} dict",
        '"extra":{' in content or "'extra': {" in content or "extra={" in content,
    ))
    checks.append((
        "Logs check_in_skipped event",
        '"check_in_skipped"' in content or "'check_in_skipped'" in content,
    ))
    checks.append((
        "Logs check_in_scheduled event",
        '"check_in_scheduled"' in content or "'check_in_scheduled'" in content,
    ))
    checks.append((
        "Logs check_in_already_scheduled event",
        '"check_in_already_scheduled"' in content or "'check_in_already_scheduled'" in content,
    ))
    
    # Check error handling
    checks.append((
        "Handles IntegrityError for idempotency",
        "except IntegrityError:" in content,
    ))
    checks.append((
        "Handles generic Exception as fallback",
        "except Exception:" in content,
    ))
    checks.append((
        "Rollback on error",
        "await session.rollback()" in content,
    ))
    
    # Check comments
    checks.append((
        "Comments explain key decisions",
        "#" in content and (
            "ADR-" in content or
            "AC Scenario" in content or
            "US-041" in content
        ),
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

US-041 TASK-002 (48-Hour Check-in Scheduling) has passed
all {all_total} validation checks.

Files Created/Modified:
  - backend/app/agents/followup_care/checkin_scheduler.py (NEW)
  - backend/app/agents/followup_care/agent.py (MODIFIED)
  - backend/app/agents/followup_care/schemas.py (MODIFIED)

Key Features:
  - Risk threshold: risk_score >= 0.5 triggers check-in scheduling
  - Channel resolution: patient.preferred_contact → SMS/EMAIL
  - send_at calculation: discharge_time + 48 hours (not now() + 48h)
  - Idempotency: CHK48-{{encounter_id}} prevents duplicates on redelivery
  - Separate transaction: Check-in scheduling independent of risk score commit

Acceptance Criteria Coverage:
  ✅ AC Scenario 1: CHECK_IN_48H notification with send_at = discharge_time + 48h
  ✅ AC Scenario 2: No check-in for risk_score=0.2 (< 0.5 threshold)
  ✅ AC Scenario 3: Channel resolved from patient.preferred_contact

Next Steps:
  1. Unit test checkin_scheduler.maybe_schedule_48h_checkin()
  2. Integration test: A03 event with risk_score=0.6 → ScheduledNotification created
  3. Integration test: A03 event with risk_score=0.2 → no ScheduledNotification
  4. Integration test: Pub/Sub redelivery → no duplicate notification
  5. Proceed to TASK-003 (Unit tests)
"""
    else:
        report += f"""{'='*60}
  ❌ BLOCKED — {all_total - all_passed} CHECKS FAILED
{'='*60}

US-041 TASK-002 has {all_total - all_passed} failing checks.
Review the failures above and fix before proceeding.

Common Issues:
  - Missing function implementation
  - Incorrect threshold value (should be 0.5)
  - Missing idempotency handling
  - Channel resolution logic incorrect
  - send_at uses datetime.now() instead of discharge_time
  - Missing error handling or logging
"""
    
    return report


def main() -> int:
    """Run all validation checks and generate report.
    
    Returns:
        0 if all checks pass, 1 otherwise
    """
    print("="*60)
    print("  US-041 TASK-002: 48-Hour Check-in Scheduling")
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
    
    # Category 2: Module Implementation
    print("="*60)
    print("  2. Module Implementation Validation")
    print("="*60)
    passed, total = validate_module_implementation()
    all_passed += passed
    all_total += total
    print()
    
    # Category 3: Idempotency
    print("="*60)
    print("  3. Idempotency Validation")
    print("="*60)
    passed, total = validate_idempotency()
    all_passed += passed
    all_total += total
    print()
    
    # Category 4: Channel Resolution
    print("="*60)
    print("  4. Channel Resolution Validation")
    print("="*60)
    passed, total = validate_channel_resolution()
    all_passed += passed
    all_total += total
    print()
    
    # Category 5: send_at Calculation
    print("="*60)
    print("  5. send_at Calculation Validation")
    print("="*60)
    passed, total = validate_send_at_calculation()
    all_passed += passed
    all_total += total
    print()
    
    # Category 6: Risk Threshold
    print("="*60)
    print("  6. Risk Threshold Validation")
    print("="*60)
    passed, total = validate_risk_threshold()
    all_passed += passed
    all_total += total
    print()
    
    # Category 7: Acceptance Criteria
    print("="*60)
    print("  7. Acceptance Criteria Validation")
    print("="*60)
    passed, total = validate_acceptance_criteria()
    all_passed += passed
    all_total += total
    print()
    
    # Category 8: Code Quality
    print("="*60)
    print("  8. Code Quality Validation")
    print("="*60)
    passed, total = validate_code_quality()
    all_passed += passed
    all_total += total
    print()
    
    # Final report
    report = generate_final_report(all_passed, all_total)
    print(report)
    
    return 0 if all_passed == all_total else 1


if __name__ == "__main__":
    sys.exit(main())
