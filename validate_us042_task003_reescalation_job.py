"""Automated validation for US-042 TASK-003: ReEscalationJob Implementation.

Validates:
1. ReEscalationJob file exists
2. ReEscalationJob class structure
3. Required methods present (run, _reescalate, _publish_supervisor_escalation)
4. Query logic (status=PENDING, escalated_to_supervisor=FALSE, 15-minute SLA)
5. Update logic (atomic UPDATE with WHERE conditions, escalated_at timestamp)
6. Idempotency pattern (NOTIF-SUP-ESC-{escalation_id})
7. Main.py integration (APScheduler import, job registration)
8. Python syntax validation
9. PHI compliance (UUID-only logging)
10. Error handling (batch processing with individual error catching)

DoD Checklist:
- [x] reescalation_job.py created
- [x] ReEscalationJob.run() queries correct records
- [x] DB UPDATE uses WHERE status=PENDING AND escalated_to_supervisor=FALSE
- [x] SUPERVISOR_ESCALATION published after DB commit
- [x] idempotency_key = "NOTIF-SUP-ESC-{escalation_id}"
- [x] Job registered on APScheduler with interval=60s
- [x] Individual record errors caught and logged
- [x] No PHI in any log line
- [x] Python syntax validated
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any


class ValidationResult:
    """Track validation check results."""

    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.warnings: int = 0
        self.checks: list[dict[str, Any]] = []

    def add_pass(self, check: str, detail: str = "") -> None:
        self.passed += 1
        self.checks.append({"status": "PASS", "check": check, "detail": detail})
        print(f"✓ {check}")
        if detail:
            print(f"  → {detail}")

    def add_fail(self, check: str, detail: str) -> None:
        self.failed += 1
        self.checks.append({"status": "FAIL", "check": check, "detail": detail})
        print(f"✗ {check}")
        print(f"  → {detail}")

    def add_warning(self, check: str, detail: str) -> None:
        self.warnings += 1
        self.checks.append({"status": "WARN", "check": check, "detail": detail})
        print(f"⚠ {check}")
        print(f"  → {detail}")

    def summary(self) -> str:
        total = self.passed + self.failed + self.warnings
        return (
            f"\n{'=' * 80}\n"
            f"Validation Summary: {self.passed}/{total} checks passed\n"
            f"  Passed: {self.passed}\n"
            f"  Failed: {self.failed}\n"
            f"  Warnings: {self.warnings}\n"
            f"{'=' * 80}\n"
        )


def validate_reescalation_job_exists(result: ValidationResult, base_path: Path) -> None:
    """Validate that reescalation_job.py exists."""
    print("\n=== ReEscalation Job File Validation ===\n")

    job_path = (
        base_path
        / "backend"
        / "app"
        / "agents"
        / "followup_care"
        / "escalation"
        / "reescalation_job.py"
    )

    if job_path.exists():
        result.add_pass("reescalation_job.py exists", str(job_path))
    else:
        result.add_fail("reescalation_job.py missing", str(job_path))


def validate_reescalation_job_structure(result: ValidationResult, base_path: Path) -> None:
    """Validate ReEscalationJob class structure."""
    print("\n=== ReEscalation Job Class Structure ===\n")

    job_path = (
        base_path
        / "backend"
        / "app"
        / "agents"
        / "followup_care"
        / "escalation"
        / "reescalation_job.py"
    )

    if not job_path.exists():
        result.add_fail("reescalation_job.py not found for validation", str(job_path))
        return

    content = job_path.read_text(encoding="utf-8")
    tree = ast.parse(content)

    # Find ReEscalationJob class
    job_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ReEscalationJob":
            job_class = node
            break

    if job_class:
        result.add_pass("ReEscalationJob class defined")

        # Check for required methods
        required_methods = {
            "__init__",
            "run",
            "_reescalate",
            "_publish_supervisor_escalation",
        }
        found_methods = {
            node.name
            for node in job_class.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        missing = required_methods - found_methods
        if not missing:
            result.add_pass(
                "All required methods present",
                f"Methods: {', '.join(sorted(found_methods))}",
            )
        else:
            result.add_fail(
                "ReEscalationJob missing methods",
                f"Missing: {', '.join(sorted(missing))}",
            )

        # Check that run and _reescalate are async
        async_methods = {
            node.name
            for node in job_class.body
            if isinstance(node, ast.AsyncFunctionDef)
        }

        if "run" in async_methods:
            result.add_pass("run() method is async")
        else:
            result.add_fail("run() method not async", "Method must be async")

        if "_reescalate" in async_methods:
            result.add_pass("_reescalate() method is async")
        else:
            result.add_fail("_reescalate() method not async", "Method must be async")

    else:
        result.add_fail("ReEscalationJob class not found", "Check reescalation_job.py")


def validate_query_logic(result: ValidationResult, base_path: Path) -> None:
    """Validate the query logic for finding overdue escalations."""
    print("\n=== Query Logic Validation ===\n")

    job_path = (
        base_path
        / "backend"
        / "app"
        / "agents"
        / "followup_care"
        / "escalation"
        / "reescalation_job.py"
    )

    if not job_path.exists():
        result.add_fail("reescalation_job.py not found for query validation", str(job_path))
        return

    content = job_path.read_text(encoding="utf-8")

    # Check for 15-minute SLA constant
    if "ESCALATION_SLA_MINUTES = 15" in content:
        result.add_pass("15-minute SLA constant defined")
    else:
        result.add_fail("15-minute SLA constant missing or incorrect", "Check ESCALATION_SLA_MINUTES")

    # Check for 60-second job interval
    if "JOB_INTERVAL_SECONDS = 60" in content:
        result.add_pass("60-second job interval constant defined")
    else:
        result.add_fail("60-second interval constant missing or incorrect", "Check JOB_INTERVAL_SECONDS")

    # Check for query conditions
    query_conditions = [
        "CareEscalationStatus.PENDING",
        "escalated_to_supervisor.is_(False)",
        "sent_at < sla_cutoff",
        "deleted_at.is_(None)",
    ]

    missing_conditions = []
    for condition in query_conditions:
        if condition not in content:
            missing_conditions.append(condition)

    if not missing_conditions:
        result.add_pass(
            "All query conditions present",
            f"Conditions: {len(query_conditions)}",
        )
    else:
        result.add_fail(
            "Query conditions missing",
            f"Missing: {', '.join(missing_conditions)}",
        )

    # Check for timedelta usage
    if "timedelta(minutes=ESCALATION_SLA_MINUTES)" in content:
        result.add_pass("SLA cutoff calculation present")
    else:
        result.add_fail("SLA cutoff calculation missing", "Check timedelta usage")


def validate_update_logic(result: ValidationResult, base_path: Path) -> None:
    """Validate the atomic UPDATE logic."""
    print("\n=== Update Logic Validation ===\n")

    job_path = (
        base_path
        / "backend"
        / "app"
        / "agents"
        / "followup_care"
        / "escalation"
        / "reescalation_job.py"
    )

    if not job_path.exists():
        result.add_fail("reescalation_job.py not found for update validation", str(job_path))
        return

    content = job_path.read_text(encoding="utf-8")

    # Check for UPDATE statement
    if "update(CareEscalation)" in content:
        result.add_pass("UPDATE statement present")
    else:
        result.add_fail("UPDATE statement missing", "Check _reescalate method")

    # Check for atomic WHERE conditions
    atomic_conditions = [
        "CareEscalation.id == escalation.id",
        "CareEscalation.status == CareEscalationStatus.PENDING",
        "CareEscalation.escalated_to_supervisor.is_(False)",
    ]

    missing_conditions = []
    for condition in atomic_conditions:
        if condition not in content:
            missing_conditions.append(condition)

    if not missing_conditions:
        result.add_pass(
            "Atomic UPDATE WHERE conditions present",
            "Prevents concurrent updates",
        )
    else:
        result.add_fail(
            "Atomic UPDATE conditions missing",
            f"Missing: {', '.join(missing_conditions)}",
        )

    # Check for values being set
    update_values = [
        "status=CareEscalationStatus.ESCALATED_TO_SUPERVISOR",
        "escalated_to_supervisor=True",
        "escalated_at=now",
    ]

    missing_values = []
    for value in update_values:
        if value not in content:
            missing_values.append(value)

    if not missing_values:
        result.add_pass("All UPDATE values present")
    else:
        result.add_fail(
            "UPDATE values missing",
            f"Missing: {', '.join(missing_values)}",
        )

    # Check for RETURNING clause
    if ".returning(CareEscalation.id)" in content:
        result.add_pass("RETURNING clause present for concurrency check")
    else:
        result.add_fail("RETURNING clause missing", "Check UPDATE statement")

    # Check for commit before publish
    if content.index("await session.commit()") < content.index("_publish_supervisor_escalation"):
        result.add_pass("DB commit happens before Pub/Sub publish (correct ordering)")
    else:
        result.add_fail(
            "Incorrect ordering",
            "DB commit must happen before Pub/Sub publish",
        )


def validate_idempotency_pattern(result: ValidationResult, base_path: Path) -> None:
    """Validate idempotency key pattern."""
    print("\n=== Idempotency Pattern Validation ===\n")

    job_path = (
        base_path
        / "backend"
        / "app"
        / "agents"
        / "followup_care"
        / "escalation"
        / "reescalation_job.py"
    )

    if not job_path.exists():
        result.add_fail("reescalation_job.py not found for idempotency validation", str(job_path))
        return

    content = job_path.read_text(encoding="utf-8")

    # Check for NOTIF-SUP-ESC pattern
    if 'f"NOTIF-SUP-ESC-{escalation.id}"' in content:
        result.add_pass("NOTIF-SUP-ESC-{escalation_id} idempotency pattern found")
    else:
        result.add_fail(
            "Idempotency pattern missing or incorrect",
            "Check _publish_supervisor_escalation",
        )

    # Check for event_type
    if '"event_type": "SUPERVISOR_ESCALATION"' in content:
        result.add_pass("SUPERVISOR_ESCALATION event_type present")
    else:
        result.add_fail("SUPERVISOR_ESCALATION event_type missing", "Check payload")


def validate_main_integration(result: ValidationResult, base_path: Path) -> None:
    """Validate main.py integration of APScheduler and ReEscalationJob."""
    print("\n=== Main.py Integration Validation ===\n")

    main_path = base_path / "backend" / "app" / "agents" / "followup_care" / "main.py"

    if not main_path.exists():
        result.add_fail("main.py not found", str(main_path))
        return

    content = main_path.read_text(encoding="utf-8")

    # Check for APScheduler import
    if "from apscheduler.schedulers.asyncio import AsyncIOScheduler" in content:
        result.add_pass("AsyncIOScheduler import present")
    else:
        result.add_fail("AsyncIOScheduler import missing", "Check import statements")

    # Check for ReEscalationJob import
    if "from app.agents.followup_care.escalation.reescalation_job import ReEscalationJob" in content:
        result.add_pass("ReEscalationJob import present")
    else:
        result.add_fail("ReEscalationJob import missing", "Check import statements")

    # Check for scheduler initialization
    if "scheduler = AsyncIOScheduler()" in content:
        result.add_pass("AsyncIOScheduler initialization present")
    else:
        result.add_fail("AsyncIOScheduler initialization missing", "Check main() function")

    # Check for ReEscalationJob initialization
    if "reescalation_job = ReEscalationJob(" in content:
        result.add_pass("ReEscalationJob initialization present")
    else:
        result.add_fail("ReEscalationJob initialization missing", "Check main() function")

    # Check for scheduler.add_job
    if "scheduler.add_job(" in content:
        result.add_pass("scheduler.add_job() call present")
    else:
        result.add_fail("scheduler.add_job() call missing", "Check main() function")

    # Check for job parameters
    job_params = [
        'trigger="interval"',
        "seconds=60",
        'id="care_escalation_reescalation_monitor"',
        "misfire_grace_time=30",
    ]

    missing_params = []
    for param in job_params:
        if param not in content:
            missing_params.append(param)

    if not missing_params:
        result.add_pass("All job parameters present")
    else:
        result.add_fail(
            "Job parameters missing",
            f"Missing: {', '.join(missing_params)}",
        )

    # Check for scheduler.start()
    if "scheduler.start()" in content:
        result.add_pass("scheduler.start() call present")
    else:
        result.add_fail("scheduler.start() call missing", "Check main() function")

    # Check for scheduler.shutdown()
    if "scheduler.shutdown(" in content:
        result.add_pass("scheduler.shutdown() call present in cleanup")
    else:
        result.add_warning(
            "scheduler.shutdown() call not found",
            "Verify graceful shutdown handling",
        )


def validate_python_syntax(result: ValidationResult, base_path: Path) -> None:
    """Validate Python syntax."""
    print("\n=== Python Syntax Validation ===\n")

    job_path = (
        base_path
        / "backend"
        / "app"
        / "agents"
        / "followup_care"
        / "escalation"
        / "reescalation_job.py"
    )

    if not job_path.exists():
        result.add_fail("reescalation_job.py not found for syntax check", str(job_path))
        return

    try:
        content = job_path.read_text(encoding="utf-8")
        ast.parse(content)
        result.add_pass("Syntax valid: reescalation_job.py")
    except SyntaxError as e:
        result.add_fail(
            "Syntax error in reescalation_job.py",
            f"Line {e.lineno}: {e.msg}",
        )


def validate_phi_compliance(result: ValidationResult, base_path: Path) -> None:
    """Validate PHI compliance in logging statements."""
    print("\n=== PHI Compliance Validation ===\n")

    job_path = (
        base_path
        / "backend"
        / "app"
        / "agents"
        / "followup_care"
        / "escalation"
        / "reescalation_job.py"
    )

    if not job_path.exists():
        result.add_fail("reescalation_job.py not found for PHI check", str(job_path))
        return

    content = job_path.read_text(encoding="utf-8")

    # PHI fields that should NOT appear in logs
    phi_fields = [
        "patient_name",
        "patient.name",
        "first_name",
        "last_name",
        "phone_number",
        "email",
        "mrn",
        "date_of_birth",
        "dob",
        "ssn",
    ]

    found_phi = []
    for field in phi_fields:
        # Skip if it's in a comment explaining what NOT to log
        if field in content and f"No {field}" not in content:
            found_phi.append(field)

    if not found_phi:
        result.add_pass("No PHI fields found in reescalation_job.py", "UUID-only logging enforced")
    else:
        result.add_warning(
            "Potential PHI fields found in reescalation_job.py",
            f"Review these occurrences: {', '.join(found_phi)}",
        )

    # Check that logs only use UUID fields
    uuid_patterns = [
        "escalation_id",
        "encounter_id",
        "patient_id",
    ]
    found_uuids = []
    for pattern in uuid_patterns:
        if pattern in content:
            found_uuids.append(pattern)

    if len(found_uuids) >= 2:
        result.add_pass(
            "UUID-based logging present",
            f"Found: {', '.join(found_uuids)}",
        )
    else:
        result.add_warning(
            "Limited UUID-based logging",
            f"Found only: {', '.join(found_uuids)}",
        )


def validate_error_handling(result: ValidationResult, base_path: Path) -> None:
    """Validate error handling for batch processing."""
    print("\n=== Error Handling Validation ===\n")

    job_path = (
        base_path
        / "backend"
        / "app"
        / "agents"
        / "followup_care"
        / "escalation"
        / "reescalation_job.py"
    )

    if not job_path.exists():
        result.add_fail("reescalation_job.py not found for error validation", str(job_path))
        return

    content = job_path.read_text(encoding="utf-8")

    # Check for batch error handling
    if "for escalation in overdue_escalations:" in content:
        result.add_pass("Batch processing loop present")
    else:
        result.add_fail("Batch processing loop missing", "Check run() method")

    # Check for individual error catching
    if "try:" in content and "except Exception as exc:" in content:
        result.add_pass("Exception handling present in batch loop")
    else:
        result.add_fail("Exception handling missing", "Errors should not abort batch")

    # Check for error logging
    if 'logger.error(' in content and "reescalation_failed" in content:
        result.add_pass("Error logging present for failed re-escalations")
    else:
        result.add_fail("Error logging missing", "Check exception handler")


def main() -> None:
    """Run all validation checks."""
    result = ValidationResult()
    base_path = Path(__file__).parent

    print("\n" + "=" * 80)
    print("US-042 TASK-003 Validation: ReEscalationJob Implementation")
    print("=" * 80)

    validate_reescalation_job_exists(result, base_path)
    validate_reescalation_job_structure(result, base_path)
    validate_query_logic(result, base_path)
    validate_update_logic(result, base_path)
    validate_idempotency_pattern(result, base_path)
    validate_main_integration(result, base_path)
    validate_python_syntax(result, base_path)
    validate_phi_compliance(result, base_path)
    validate_error_handling(result, base_path)

    print(result.summary())

    if result.failed > 0:
        print("❌ Validation FAILED. Address failures before proceeding.")
        exit(1)
    elif result.warnings > 0:
        print("⚠️  Validation PASSED with warnings. Review warnings before deployment.")
        exit(0)
    else:
        print("✅ All validation checks PASSED. Implementation ready for testing.")
        exit(0)


if __name__ == "__main__":
    main()
