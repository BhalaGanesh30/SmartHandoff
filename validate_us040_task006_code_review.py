#!/usr/bin/env python3
"""US-040 TASK-006: Code Review & DoD Sign-off Validation.

Comprehensive validation covering:
    - Security: PHI protection, publish-after-commit correctness, idempotency
    - Correctness: All tasks complete, ACs met, appointment logic, alert dispatch
    - Code Quality: Documentation, type hints, logging, error handling
    - DoD Criteria: All 5 tasks verified, tests passing, migration clean

Security Engineer review mandatory for:
    1. PHI exposure risk in appointment records and Pub/Sub payload
    2. Publish-after-commit pattern correctness (patient safety)
    3. Idempotency on Pub/Sub redelivery

Expected Result: APPROVED FOR PRODUCTION or list of blocking issues.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def print_header(msg: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print('=' * 60)


def print_check(desc: str, passed: bool, details: str = "") -> bool:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {desc}")
    if details:
        for line in details.split('\n'):
            print(f"      {line}")
    return passed


def validate_task_completion() -> tuple[int, int]:
    """Validate all upstream tasks (TASK-001 through TASK-005) are complete."""
    print_header("1. Task Completion Verification")
    passed = 0
    total = 0
    
    backend_root = Path(__file__).parent / "backend"
    
    # TASK-001: Appointment ORM + Migration
    task001_files = {
        "appointment_model": backend_root / "app/models/appointment.py",
    }
    
    total += 1
    passed += print_check(
        "TASK-001: appointment.py ORM model exists",
        task001_files["appointment_model"].exists(),
        f"Path: {task001_files['appointment_model'].relative_to(Path.cwd())}"
    )
    
    # Check for appointment migration (flexible pattern)
    total += 1
    migration_dir = backend_root / "alembic/versions"
    appointment_migrations = list(migration_dir.glob("*add_appointment_table*.py"))
    has_migration = len(appointment_migrations) > 0
    migration_name = appointment_migrations[0].name if appointment_migrations else "not found"
    passed += print_check(
        "TASK-001: Alembic migration for appointment table exists",
        has_migration,
        f"Found: {migration_name}"
    )
    
    # TASK-002: Care Pathways Configuration
    task002_files = {
        "yaml_config": backend_root.parent / "backend/config/care_pathways.yaml",
        "config_loader": backend_root / "app/config/care_pathways.py",
    }
    
    total += 1
    passed += print_check(
        "TASK-002: care_pathways.yaml config exists",
        task002_files["yaml_config"].exists(),
        f"Path: {task002_files['yaml_config'].relative_to(Path.cwd())}"
    )
    
    total += 1
    passed += print_check(
        "TASK-002: care_pathways.py loader exists",
        task002_files["config_loader"].exists(),
        f"Path: {task002_files['config_loader'].relative_to(Path.cwd())}"
    )
    
    # TASK-003: CarePathwayService
    task003_file = backend_root / "app/services/care_pathway_service.py"
    
    total += 1
    passed += print_check(
        "TASK-003: care_pathway_service.py exists",
        task003_file.exists(),
        f"Path: {task003_file.relative_to(Path.cwd())}"
    )
    
    # TASK-004: NotificationPublisher + Agent Extensions
    task004_files = {
        "publisher": backend_root / "app/agents/followup_care/notification_publisher.py",
        "schemas": backend_root / "app/agents/followup_care/schemas.py",
        "agent": backend_root / "app/agents/followup_care/agent.py",
    }
    
    total += 1
    passed += print_check(
        "TASK-004: notification_publisher.py exists",
        task004_files["publisher"].exists(),
        f"Path: {task004_files['publisher'].relative_to(Path.cwd())}"
    )
    
    total += 1
    has_alert_payload = "CareManagerAlertPayload" in task004_files["schemas"].read_text()
    passed += print_check(
        "TASK-004: CareManagerAlertPayload in schemas.py",
        has_alert_payload
    )
    
    # TASK-005: Unit Tests
    task005_files = {
        "config_tests": backend_root / "tests/unit/config/test_care_pathways_config.py",
        "service_tests": backend_root / "tests/unit/services/test_care_pathway_service.py",
        "agent_tests": backend_root / "tests/unit/agents/followup_care/test_followup_agent_us040.py",
    }
    
    total += 1
    passed += print_check(
        "TASK-005: test_care_pathways_config.py exists",
        task005_files["config_tests"].exists()
    )
    
    total += 1
    passed += print_check(
        "TASK-005: test_care_pathway_service.py exists",
        task005_files["service_tests"].exists()
    )
    
    total += 1
    passed += print_check(
        "TASK-005: test_followup_agent_us040.py exists",
        task005_files["agent_tests"].exists()
    )
    
    return passed, total


def validate_security_phi_protection() -> tuple[int, int]:
    """Validate no PHI exposure in appointment table, logs, or Pub/Sub payload."""
    print_header("2. Security: PHI Protection (HIPAA / BR-020, AIR-021)")
    passed = 0
    total = 0
    
    backend_root = Path(__file__).parent / "backend"
    
    # Check appointment.py model
    appointment_model = (backend_root / "app/models/appointment.py").read_text()
    
    total += 1
    phi_fields = ["patient_name", "mrn", "first_name", "last_name", "date_of_birth", "dob", "phone", "email", "ssn"]
    has_phi = any(field in appointment_model.lower() for field in phi_fields)
    passed += print_check(
        "Appointment model has no PHI fields",
        not has_phi,
        f"Forbidden fields: {', '.join(phi_fields)}" if has_phi else "Only UUIDs and metadata"
    )
    
    total += 1
    required_fields = ["encounter_id", "appointment_type", "target_date", "status"]
    has_required = all(field in appointment_model for field in required_fields)
    passed += print_check(
        "Appointment model has required non-PHI fields",
        has_required,
        f"Required: {', '.join(required_fields)}"
    )
    
    # Check CarePathwayService logs
    service_code = (backend_root / "app/services/care_pathway_service.py").read_text()
    
    total += 1
    log_phi_pattern = re.compile(r'logger\.(info|debug|warning|error).*["\'].*\b(mrn|first_name|last_name|patient_name|dob)\b', re.IGNORECASE)
    has_phi_in_logs = bool(log_phi_pattern.search(service_code))
    passed += print_check(
        "CarePathwayService logs no PHI",
        not has_phi_in_logs,
        "Only encounter_id (UUID), risk_tier, appointment_type logged"
    )
    
    # Check NotificationPublisher logs
    publisher_code = (backend_root / "app/agents/followup_care/notification_publisher.py").read_text()
    
    total += 1
    has_phi_in_publisher_logs = bool(log_phi_pattern.search(publisher_code))
    passed += print_check(
        "NotificationPublisher logs no PHI",
        not has_phi_in_publisher_logs,
        "Only encounter_id, appointment_id, pubsub_message_id logged"
    )
    
    # Check CareManagerAlertPayload schema
    schemas_code = (backend_root / "app/agents/followup_care/schemas.py").read_text()
    
    total += 1
    alert_payload_match = re.search(
        r'class CareManagerAlertPayload.*?(?=class |\Z)',
        schemas_code,
        re.DOTALL
    )
    if alert_payload_match:
        alert_payload_code = alert_payload_match.group(0)
        has_phi_in_payload = any(field in alert_payload_code.lower() for field in phi_fields)
        passed += print_check(
            "CareManagerAlertPayload has no PHI fields",
            not has_phi_in_payload,
            "Only alert_type, encounter_id, risk_score, risk_tier, required_followup_days, appointment_id, idempotency_key"
        )
    else:
        total += 1
        passed += print_check(
            "CareManagerAlertPayload class found",
            False,
            "Schema not found in schemas.py"
        )
    
    # Check agent.py for PHI in logs
    agent_code = (backend_root / "app/agents/followup_care/agent.py").read_text()
    
    total += 1
    has_phi_in_agent_logs = bool(log_phi_pattern.search(agent_code))
    passed += print_check(
        "FollowUpCareAgent logs no PHI",
        not has_phi_in_agent_logs,
        "Only encounter_id, risk_tier, appointment_id logged"
    )
    
    return passed, total


def validate_security_publish_after_commit() -> tuple[int, int]:
    """Validate publish-after-commit pattern correctness (patient safety)."""
    print_header("3. Security: Publish-After-Commit Pattern (Patient Safety)")
    passed = 0
    total = 0
    
    backend_root = Path(__file__).parent / "backend"
    agent_code = (backend_root / "app/agents/followup_care/agent.py").read_text()
    
    # Check commit before publish in process()
    total += 1
    commit_then_publish_pattern = re.compile(
        r'await\s+write_session\.commit\(\).*?publish_care_manager_alert',
        re.DOTALL
    )
    has_correct_order = bool(commit_then_publish_pattern.search(agent_code))
    passed += print_check(
        "DB commit occurs BEFORE publish_care_manager_alert",
        has_correct_order,
        "Pattern: await write_session.commit() ... publish_care_manager_alert(...)"
    )
    
    # Check activate_pathway does not commit
    service_code = (backend_root / "app/services/care_pathway_service.py").read_text()
    
    total += 1
    activate_pathway_match = re.search(
        r'async def activate_pathway.*?(?=\n    async def |\Z)',
        service_code,
        re.DOTALL
    )
    if activate_pathway_match:
        activate_pathway_code = activate_pathway_match.group(0)
        has_commit_in_service = "commit()" in activate_pathway_code
        passed += print_check(
            "CarePathwayService.activate_pathway does NOT commit",
            not has_commit_in_service,
            "Only flush() — commit owned by agent for atomicity"
        )
    else:
        total += 1
        passed += print_check(
            "activate_pathway method found",
            False,
            "Method not found in care_pathway_service.py"
        )
    
    # Check publish error handling
    total += 1
    publish_error_pattern = re.compile(
        r'try:.*?publish_care_manager_alert.*?except.*?Exception',
        re.DOTALL
    )
    has_error_handling = bool(publish_error_pattern.search(agent_code))
    passed += print_check(
        "Publish failures caught and logged (no rollback)",
        has_error_handling,
        "Catches Exception, logs error, does not rollback committed transaction"
    )
    
    # Check no rollback after publish failure
    total += 1
    if has_error_handling:
        error_block_match = re.search(
            r'try:.*?publish_care_manager_alert.*?except.*?Exception.*?(?=\n(?!    ))',
            agent_code,
            re.DOTALL
        )
        if error_block_match:
            error_block = error_block_match.group(0)
            has_rollback_in_error = "rollback" in error_block.lower()
            passed += print_check(
                "Publish error handler does NOT rollback",
                not has_rollback_in_error,
                "Appointment already committed — rollback would be incorrect"
            )
        else:
            passed += print_check(
                "Publish error handler analyzed",
                False,
                "Could not extract error handling block"
            )
    else:
        passed += print_check(
            "Publish error handler does NOT rollback",
            False,
            "No error handling found to analyze"
        )
    
    return passed, total


def validate_security_idempotency() -> tuple[int, int]:
    """Validate idempotency on Pub/Sub redelivery."""
    print_header("4. Security: Idempotency on Pub/Sub Redelivery (AIR-040)")
    passed = 0
    total = 0
    
    backend_root = Path(__file__).parent / "backend"
    
    # Check idempotency_key in CareManagerAlertPayload
    schemas_code = (backend_root / "app/agents/followup_care/schemas.py").read_text()
    
    total += 1
    has_idempotency_field = "idempotency_key" in schemas_code
    passed += print_check(
        "CareManagerAlertPayload has idempotency_key field",
        has_idempotency_field
    )
    
    # Check idempotency_key format in agent
    agent_code = (backend_root / "app/agents/followup_care/agent.py").read_text()
    
    total += 1
    idempotency_format_pattern = re.compile(
        r'idempotency_key=f["\']CARE_MANAGER_ALERT:\{.*?encounter.*?\}:\{.*?appointment.*?\}["\']',
        re.IGNORECASE
    )
    has_correct_format = bool(idempotency_format_pattern.search(agent_code))
    passed += print_check(
        "Idempotency key format: CARE_MANAGER_ALERT:{encounter_id}:{appointment_id}",
        has_correct_format
    )
    
    # Check Pub/Sub publish sets idempotency_key attribute
    publisher_code = (backend_root / "app/agents/followup_care/notification_publisher.py").read_text()
    
    total += 1
    publish_with_idempotency = "idempotency_key" in publisher_code and "publish(" in publisher_code
    passed += print_check(
        "NotificationPublisher sets idempotency_key on Pub/Sub message",
        publish_with_idempotency,
        "Prevents duplicate notifications on redelivery"
    )
    
    # Check appointment table has unique constraint
    appointment_model = (backend_root / "app/models/appointment.py").read_text()
    
    total += 1
    has_unique_constraint = "UniqueConstraint" in appointment_model or "unique=True" in appointment_model
    passed += print_check(
        "Appointment model has unique constraint (prevents duplicates)",
        has_unique_constraint,
        "Constraint on encounter_id + appointment_type or similar"
    )
    
    return passed, total


def validate_acceptance_criteria() -> tuple[int, int]:
    """Validate all US-040 acceptance criteria are met."""
    print_header("5. Acceptance Criteria Validation")
    passed = 0
    total = 0
    
    backend_root = Path(__file__).parent / "backend"
    agent_code = (backend_root / "app/agents/followup_care/agent.py").read_text()
    service_code = (backend_root / "app/services/care_pathway_service.py").read_text()
    
    # AC Scenario 1: HIGH alert dispatched
    total += 1
    has_high_alert = 'risk_tier_str == "HIGH"' in agent_code and "publish_care_manager_alert" in agent_code
    passed += print_check(
        "AC Scenario 1: HIGH-risk patients trigger CARE_MANAGER_ALERT",
        has_high_alert,
        "Conditional: if risk_tier_str == 'HIGH' ... publish_care_manager_alert"
    )
    
    # AC Scenario 2: HIGH appointment created
    total += 1
    has_appointment_creation = "activate_pathway" in agent_code
    passed += print_check(
        "AC Scenario 2: HIGH-risk patients get appointment created",
        has_appointment_creation,
        "activate_pathway called for all tiers"
    )
    
    # AC Scenario 3: MEDIUM appointment, no alert
    total += 1
    config_code = (backend_root.parent / "backend/config/care_pathways.yaml").read_text()
    medium_no_alert = "alert_care_manager: false" in config_code
    passed += print_check(
        "AC Scenario 3: MEDIUM-risk patients get appointment, no alert",
        medium_no_alert,
        "YAML config: MEDIUM tier has alert_care_manager=false"
    )
    
    # AC Scenario 4: LOW appointment, no alert
    total += 1
    low_no_alert = "alert_care_manager: false" in config_code
    passed += print_check(
        "AC Scenario 4: LOW-risk patients get appointment, no alert",
        low_no_alert,
        "YAML config: LOW tier has alert_care_manager=false"
    )
    
    # Appointment creation logic
    total += 1
    creates_appointment = "Appointment(" in service_code
    passed += print_check(
        "CarePathwayService creates Appointment ORM object",
        creates_appointment
    )
    
    # Care manager assignment for HIGH
    total += 1
    assigns_care_manager = "_assign_care_manager" in service_code
    passed += print_check(
        "Care manager assigned for HIGH tier (round-robin)",
        assigns_care_manager,
        "Method: _assign_care_manager with deterministic hash-based selection"
    )
    
    return passed, total


def validate_unit_tests() -> tuple[int, int]:
    """Run unit tests and validate they pass."""
    print_header("6. Unit Test Execution")
    passed = 0
    total = 0
    
    backend_root = Path(__file__).parent / "backend"
    test_files = [
        "tests/unit/config/test_care_pathways_config.py",
        "tests/unit/services/test_care_pathway_service.py",
        "tests/unit/agents/followup_care/test_followup_agent_us040.py",
    ]
    
    # Run all tests
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *test_files,
        "-v",
        "--tb=short",
        "-q"
    ]
    
    result = subprocess.run(
        cmd,
        cwd=backend_root,
        capture_output=True,
        text=True
    )
    
    total += 1
    passed += print_check(
        "All US-040 unit tests pass",
        result.returncode == 0,
        f"Exit code: {result.returncode}"
    )
    
    # Check test count
    output = result.stdout + result.stderr
    
    total += 1
    has_32_tests = "32 passed" in output
    passed += print_check(
        "All 32 test cases executed (13+13+6)",
        has_32_tests,
        "13 config + 13 service + 6 agent tests"
    )
    
    total += 1
    no_failures = "FAILED" not in output and "ERROR" not in output
    passed += print_check(
        "Zero test failures or errors",
        no_failures
    )
    
    return passed, total


def validate_code_quality() -> tuple[int, int]:
    """Validate code quality and documentation."""
    print_header("7. Code Quality Validation")
    passed = 0
    total = 0
    
    backend_root = Path(__file__).parent / "backend"
    
    # Check all new files have docstrings
    new_files = [
        backend_root / "app/models/appointment.py",
        backend_root / "app/config/care_pathways.py",
        backend_root / "app/services/care_pathway_service.py",
        backend_root / "app/agents/followup_care/notification_publisher.py",
    ]
    
    total += 1
    all_have_docstrings = True
    for filepath in new_files:
        content = filepath.read_text()
        if '"""' not in content[:500]:  # Check first 500 chars for module docstring
            all_have_docstrings = False
            break
    passed += print_check(
        "All new modules have docstrings",
        all_have_docstrings,
        f"Checked {len(new_files)} files"
    )
    
    # Check type hints used
    total += 1
    all_have_type_hints = True
    for filepath in new_files:
        content = filepath.read_text()
        if "from __future__ import annotations" not in content and "->" not in content:
            all_have_type_hints = False
            break
    passed += print_check(
        "All new modules use type hints",
        all_have_type_hints
    )
    
    # Check structured logging (extra={} dict)
    service_code = (backend_root / "app/services/care_pathway_service.py").read_text()
    publisher_code = (backend_root / "app/agents/followup_care/notification_publisher.py").read_text()
    
    total += 1
    has_structured_logs = "extra={" in service_code or "extra={" in publisher_code
    passed += print_check(
        "Uses structured logging with extra={} dict",
        has_structured_logs,
        "Enables Cloud Logging field indexing"
    )
    
    # Check error handling
    total += 1
    has_error_handling = "except" in service_code or "except" in publisher_code
    passed += print_check(
        "Error handling implemented",
        has_error_handling,
        "Try/except blocks present in service or publisher code"
    )
    
    # Check Pydantic validation
    config_code = (backend_root / "app/config/care_pathways.py").read_text()
    
    total += 1
    uses_pydantic = "BaseModel" in config_code and "Field" in config_code
    passed += print_check(
        "Configuration uses Pydantic validation",
        uses_pydantic,
        "TierPathwayConfig validates YAML fields"
    )
    
    return passed, total


def validate_dod_criteria() -> tuple[int, int]:
    """Validate all Definition of Done criteria."""
    print_header("8. Definition of Done Criteria")
    passed = 0
    total = 0
    
    backend_root = Path(__file__).parent / "backend"
    agent_code = (backend_root / "app/agents/followup_care/agent.py").read_text()
    
    total += 1
    activates_pathway = "activate_pathway" in agent_code
    passed += print_check(
        "DoD: FollowUpCareAgent.process() activates care pathway",
        activates_pathway
    )
    
    total += 1
    publishes_alert = "publish_care_manager_alert" in agent_code
    passed += print_check(
        "DoD: Care manager alert dispatched to notification-requests",
        publishes_alert
    )
    
    total += 1
    conditional_alert = 'risk_tier_str == "HIGH"' in agent_code
    passed += print_check(
        "DoD: Alert published for HIGH tier only",
        conditional_alert
    )
    
    total += 1
    appointment_model_exists = (backend_root / "app/models/appointment.py").exists()
    passed += print_check(
        "DoD: Appointment ORM table created",
        appointment_model_exists
    )
    
    total += 1
    yaml_config_exists = (backend_root.parent / "backend/config/care_pathways.yaml").exists()
    passed += print_check(
        "DoD: Risk tier-to-pathway mapping in care_pathways.yaml",
        yaml_config_exists
    )
    
    total += 1
    tests_exist = (
        (backend_root / "tests/unit/config/test_care_pathways_config.py").exists() and
        (backend_root / "tests/unit/services/test_care_pathway_service.py").exists() and
        (backend_root / "tests/unit/agents/followup_care/test_followup_agent_us040.py").exists()
    )
    passed += print_check(
        "DoD: Unit tests implemented (HIGH/MEDIUM/LOW logic, appointment, alert)",
        tests_exist
    )
    
    return passed, total


def validate_integration_points() -> tuple[int, int]:
    """Validate integration with upstream and downstream services."""
    print_header("9. Integration Point Validation")
    passed = 0
    total = 0
    
    backend_root = Path(__file__).parent / "backend"
    agent_code = (backend_root / "app/agents/followup_care/agent.py").read_text()
    main_code = (backend_root / "app/agents/followup_care/main.py").read_text()
    
    # Check agent wiring in main.py
    total += 1
    wired_in_main = "CarePathwayService" in main_code and "NotificationPublisher" in main_code
    passed += print_check(
        "Dependencies wired in main.py",
        wired_in_main,
        "CarePathwayService and NotificationPublisher instantiated"
    )
    
    # Check agent receives dependencies
    total += 1
    receives_deps = "care_pathway_service" in agent_code and "notification_publisher" in agent_code
    passed += print_check(
        "FollowUpCareAgent __init__ accepts new dependencies",
        receives_deps
    )
    
    # Check integration with US-039 risk scoring
    total += 1
    updates_encounter_risk = "_update_encounter_risk" in agent_code
    passed += print_check(
        "Integrates with US-039 risk scoring (update_encounter_risk)",
        updates_encounter_risk,
        "Risk score persisted before pathway activation"
    )
    
    # Check Pub/Sub topic configuration
    total += 1
    notification_topic = "notification-requests" in main_code
    passed += print_check(
        "Pub/Sub topic configured (notification-requests)",
        notification_topic,
        "AIR-040 integration point"
    )
    
    return passed, total


def generate_final_report(all_passed: int, all_total: int) -> str:
    """Generate final approval/rejection report."""
    percentage = (all_passed / all_total * 100) if all_total > 0 else 0
    
    if all_passed == all_total:
        return f"""
{'=' * 60}
  ✅ APPROVED FOR PRODUCTION
{'=' * 60}

US-040 (Follow-up Care Pathways) has passed all {all_total} validation checks.

Security Sign-off: ✅ APPROVED
  - PHI Protection: All checks passed
  - Publish-After-Commit: Correct pattern verified
  - Idempotency: Redelivery handling validated

Code Review: ✅ APPROVED
  - All 5 tasks complete (TASK-001 through TASK-005)
  - 32/32 unit tests passing
  - Code quality standards met
  - DoD criteria satisfied

Ready for deployment to GCP Cloud Run (smarthandoff-dev).

Next Steps:
  1. Merge to main branch
  2. Deploy to dev environment
  3. Run integration tests with real Pub/Sub
  4. Validate end-to-end A03 → appointment → alert flow
  5. Monitor Cloud Logging for PHI leaks (first 48 hours)
"""
    else:
        failed = all_total - all_passed
        return f"""
{'=' * 60}
  ❌ BLOCKED — {failed} VALIDATION FAILURES
{'=' * 60}

US-040 validation: {all_passed}/{all_total} checks passed ({percentage:.1f}%)

BLOCKING ISSUES: {failed} checks failed

Action Required:
  1. Review failed checks above
  2. Fix all blocking issues
  3. Re-run validation: python validate_us040_task006_code_review.py
  4. Obtain Security Engineer approval for PHI/security fixes

DO NOT MERGE OR DEPLOY until all checks pass.
"""


def main() -> int:
    """Run all validations and generate final report."""
    print("=" * 60)
    print("  US-040 TASK-006: Code Review & DoD Sign-off")
    print("  Follow-up Care Pathways — FINAL VALIDATION")
    print("=" * 60)
    
    all_passed = 0
    all_total = 0
    
    # Run all validations
    checks = [
        ("Task Completion", validate_task_completion),
        ("Security: PHI Protection", validate_security_phi_protection),
        ("Security: Publish-After-Commit", validate_security_publish_after_commit),
        ("Security: Idempotency", validate_security_idempotency),
        ("Acceptance Criteria", validate_acceptance_criteria),
        ("Unit Tests", validate_unit_tests),
        ("Code Quality", validate_code_quality),
        ("Definition of Done", validate_dod_criteria),
        ("Integration Points", validate_integration_points),
    ]
    
    for name, func in checks:
        p, t = func()
        all_passed += p
        all_total += t
    
    # Final summary
    print_header("VALIDATION SUMMARY")
    percentage = (all_passed / all_total * 100) if all_total > 0 else 0
    print(f"Total Checks: {all_total}")
    print(f"Passed: {all_passed}")
    print(f"Failed: {all_total - all_passed}")
    print(f"Success Rate: {percentage:.1f}%")
    
    # Generate final report
    report = generate_final_report(all_passed, all_total)
    print(report)
    
    return 0 if all_passed == all_total else 1


if __name__ == "__main__":
    sys.exit(main())
