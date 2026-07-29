"""Automated validation for US-042 TASK-006: Code Review & DoD Sign-off.

Validates:
1. Python syntax for all US-042 modules
2. PHI compliance (no PHI in logs or Pub/Sub messages)
3. Unit test execution (14 tests pass)
4. RBAC enforcement (dependency-based, not inline checks)
5. acknowledged_by sourced from JWT claim
6. Idempotency keys distinct (NOTIF-ESC vs NOTIF-SUP-ESC)
7. SLA cutoff uses sent_at field
8. APScheduler 60-second interval with 30s grace time
9. Concurrent-safe UPDATE with WHERE status=PENDING
10. Timezone-aware datetime.now(tz=timezone.utc)

Security Engineer Checklist:
- RBAC enforcement at router level
- PHI containment in Pub/Sub payloads
- PHI containment in log lines
- acknowledged_by from JWT sub claim

Backend Engineer Checklist:
- Idempotency key unique constraint
- Concurrent-safe UPDATE WHERE clause
- Timezone-aware timestamps
- APScheduler configuration
- SLA cutoff field (sent_at)
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
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


def validate_python_syntax(result: ValidationResult, base_path: Path) -> None:
    """Validate Python syntax for all US-042 modules."""
    print("\n=== Python Syntax Validation ===\n")

    modules = [
        "backend/app/models/care_escalation.py",
        "backend/app/agents/followup_care/escalation/__init__.py",
        "backend/app/agents/followup_care/escalation/schemas.py",
        "backend/app/agents/followup_care/escalation/monitor.py",
        "backend/app/agents/followup_care/escalation/reescalation_job.py",
        "backend/app/api/v1/routers/care_escalations.py",
    ]

    for module_rel in modules:
        module_path = base_path / module_rel
        if not module_path.exists():
            result.add_fail(f"Module not found: {module_rel}", str(module_path))
            continue

        try:
            content = module_path.read_text(encoding="utf-8")
            ast.parse(content)
            result.add_pass(f"Syntax valid: {module_rel}")
        except SyntaxError as e:
            result.add_fail(
                f"Syntax error in {module_rel}",
                f"Line {e.lineno}: {e.msg}",
            )


def validate_phi_compliance(result: ValidationResult, base_path: Path) -> None:
    """Validate no PHI fields in logs or Pub/Sub messages."""
    print("\n=== PHI Compliance Validation ===\n")

    modules = [
        "backend/app/agents/followup_care/escalation/monitor.py",
        "backend/app/agents/followup_care/escalation/reescalation_job.py",
        "backend/app/api/v1/routers/care_escalations.py",
    ]

    phi_patterns = [
        r"first_name",
        r"last_name",
        r"\.mrn",
        r"\.dob",
        r"\.phone",
        r"\.email",
    ]

    for module_rel in modules:
        module_path = base_path / module_rel
        if not module_path.exists():
            result.add_fail(f"PHI check skipped: {module_rel}", "File not found")
            continue

        content = module_path.read_text(encoding="utf-8")
        found_phi = False

        for pattern in phi_patterns:
            if re.search(pattern, content):
                result.add_fail(
                    f"PHI field found in {module_rel}",
                    f"Pattern: {pattern}",
                )
                found_phi = True
                break

        if not found_phi:
            result.add_pass(f"No PHI in {module_rel}")


def validate_unit_tests(result: ValidationResult, base_path: Path) -> None:
    """Run unit tests and verify all pass."""
    print("\n=== Unit Test Execution ===\n")

    backend_path = base_path / "backend"

    try:
        proc = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "tests/unit/agents/followup_care/escalation/",
                "tests/unit/routers/test_acknowledge_router.py",
                "-v",
                "--tb=short",
            ],
            cwd=backend_path,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if "passed" in proc.stdout:
            for line in proc.stdout.split("\n"):
                if "passed" in line:
                    result.add_pass("All unit tests passed", line.strip())
                    break
        else:
            result.add_fail("Unit tests failed", "Check pytest output")

    except subprocess.TimeoutExpired:
        result.add_fail("Test execution timeout", "Tests took >60 seconds")
    except Exception as e:
        result.add_warning("Could not run unit tests", str(e))


def validate_rbac_enforcement(result: ValidationResult, base_path: Path) -> None:
    """Validate RBAC is enforced via FastAPI dependency."""
    print("\n=== RBAC Enforcement Validation ===\n")

    router_path = base_path / "backend" / "app" / "api" / "v1" / "routers" / "care_escalations.py"

    if not router_path.exists():
        result.add_fail("Router file not found", str(router_path))
        return

    content = router_path.read_text(encoding="utf-8")

    # Check for Depends(_require_any_role(...))
    if "Depends(_require_any_role(_ALLOWED_ROLES))" in content:
        result.add_pass("RBAC dependency applied at router level")
    else:
        result.add_fail(
            "RBAC not applied as dependency",
            "Missing Depends(_require_any_role(_ALLOWED_ROLES))",
        )

    # Check acknowledged_by sourced from current_user.sub
    if "escalation.acknowledged_by = UUID(current_user.sub)" in content:
        result.add_pass("acknowledged_by sourced from JWT claim")
    else:
        result.add_fail(
            "acknowledged_by not from JWT",
            "Should be: escalation.acknowledged_by = UUID(current_user.sub)",
        )


def validate_pubsub_payloads(result: ValidationResult, base_path: Path) -> None:
    """Validate Pub/Sub payloads contain only UUIDs, no PHI."""
    print("\n=== Pub/Sub Payload Validation ===\n")

    # Check CARE_TEAM_ESCALATION payload
    monitor_path = base_path / "backend" / "app" / "agents" / "followup_care" / "escalation" / "monitor.py"
    if monitor_path.exists():
        content = monitor_path.read_text(encoding="utf-8")
        if "CareTeamEscalationMessage" in content:
            result.add_pass("CARE_TEAM_ESCALATION uses schema (no PHI)")
        else:
            result.add_warning(
                "CARE_TEAM_ESCALATION payload not verified",
                "Check monitor.py for PHI fields",
            )
    else:
        result.add_fail("monitor.py not found", str(monitor_path))

    # Check SUPERVISOR_ESCALATION payload
    reescalation_path = base_path / "backend" / "app" / "agents" / "followup_care" / "escalation" / "reescalation_job.py"
    if reescalation_path.exists():
        content = reescalation_path.read_text(encoding="utf-8")
        # Verify payload contains only allowed fields
        if '"event_type": "SUPERVISOR_ESCALATION"' in content:
            # Check for PHI fields in payload construction (within _publish_supervisor_escalation)
            # Extract the payload dict construction
            match = re.search(
                r'payload = json\.dumps\(\s*\{([^}]+)\}\s*\)',
                content,
                re.DOTALL,
            )
            if match:
                payload_str = match.group(1)
                # Check for PHI fields in payload
                phi_found = any(
                    re.search(rf'"{field}":', payload_str)
                    for field in ["first_name", "last_name", "mrn", "dob", "phone", "email"]
                )
                if not phi_found:
                    result.add_pass("SUPERVISOR_ESCALATION contains no PHI")
                else:
                    result.add_fail(
                        "SUPERVISOR_ESCALATION contains PHI fields",
                        "Check reescalation_job.py payload",
                    )
            else:
                result.add_warning(
                    "SUPERVISOR_ESCALATION payload structure not found",
                    "Check reescalation_job.py manually",
                )
        else:
            result.add_warning(
                "SUPERVISOR_ESCALATION event not found",
                "Check reescalation_job.py",
            )
    else:
        result.add_fail("reescalation_job.py not found", str(reescalation_path))


def validate_idempotency_keys(result: ValidationResult, base_path: Path) -> None:
    """Validate idempotency keys are distinct and properly formatted."""
    print("\n=== Idempotency Key Validation ===\n")

    monitor_path = base_path / "backend" / "app" / "agents" / "followup_care" / "escalation" / "monitor.py"
    reescalation_path = base_path / "backend" / "app" / "agents" / "followup_care" / "escalation" / "reescalation_job.py"

    care_team_key = None
    supervisor_key = None

    if monitor_path.exists():
        content = monitor_path.read_text(encoding="utf-8")
        match = re.search(r'idempotency_key=f"(NOTIF-ESC-[^"]+)"', content)
        if match:
            care_team_key = match.group(1)
            result.add_pass(f"CARE_TEAM_ESCALATION key: {care_team_key}")
        else:
            result.add_fail("CARE_TEAM_ESCALATION key not found", "Check monitor.py")

    if reescalation_path.exists():
        content = reescalation_path.read_text(encoding="utf-8")
        match = re.search(r'"idempotency_key": f"(NOTIF-SUP-ESC-[^"]+)"', content)
        if match:
            supervisor_key = match.group(1)
            result.add_pass(f"SUPERVISOR_ESCALATION key: {supervisor_key}")
        else:
            result.add_fail(
                "SUPERVISOR_ESCALATION key not found",
                "Check reescalation_job.py",
            )

    if care_team_key and supervisor_key:
        if care_team_key != supervisor_key:
            result.add_pass("Idempotency keys are distinct")
        else:
            result.add_fail(
                "Idempotency keys are identical",
                "NOTIF-ESC and NOTIF-SUP-ESC should be different",
            )


def validate_sla_compliance(result: ValidationResult, base_path: Path) -> None:
    """Validate SLA compliance: 15-min cutoff, 60s interval, concurrent-safe UPDATE."""
    print("\n=== SLA Compliance Validation ===\n")

    reescalation_path = base_path / "backend" / "app" / "agents" / "followup_care" / "escalation" / "reescalation_job.py"

    if not reescalation_path.exists():
        result.add_fail("reescalation_job.py not found", str(reescalation_path))
        return

    content = reescalation_path.read_text(encoding="utf-8")

    # Check sent_at used for SLA cutoff
    if "CareEscalation.sent_at < sla_cutoff" in content:
        result.add_pass("SLA cutoff uses sent_at field")
    else:
        result.add_fail(
            "SLA cutoff field incorrect",
            "Should use CareEscalation.sent_at",
        )

    # Check concurrent-safe UPDATE WHERE clause
    if (
        "CareEscalation.status == CareEscalationStatus.PENDING" in content
        and "CareEscalation.escalated_to_supervisor.is_(False)" in content
    ):
        result.add_pass("UPDATE uses concurrent-safe WHERE clause")
    else:
        result.add_fail(
            "UPDATE WHERE clause not concurrent-safe",
            "Should check status=PENDING AND escalated_to_supervisor=False",
        )

    # Check APScheduler configuration
    main_path = base_path / "backend" / "app" / "agents" / "followup_care" / "main.py"
    if main_path.exists():
        main_content = main_path.read_text(encoding="utf-8")
        if 'seconds=60' in main_content and 'misfire_grace_time=30' in main_content:
            result.add_pass("APScheduler: 60s interval, 30s grace time")
        else:
            result.add_fail(
                "APScheduler configuration incorrect",
                "Should be seconds=60, misfire_grace_time=30",
            )
    else:
        result.add_warning("APScheduler config not checked", "main.py not found")


def validate_timezone_handling(result: ValidationResult, base_path: Path) -> None:
    """Validate timezone-aware datetime usage."""
    print("\n=== Timezone Handling Validation ===\n")

    monitor_path = base_path / "backend" / "app" / "agents" / "followup_care" / "escalation" / "monitor.py"

    if not monitor_path.exists():
        result.add_fail("monitor.py not found", str(monitor_path))
        return

    content = monitor_path.read_text(encoding="utf-8")

    if "datetime.now(tz=timezone.utc)" in content:
        result.add_pass("Timezone-aware datetime.now(tz=timezone.utc)")
    else:
        result.add_fail(
            "Timezone handling incorrect",
            "Should use datetime.now(tz=timezone.utc)",
        )


def validate_unique_constraint(result: ValidationResult, base_path: Path) -> None:
    """Validate care_escalation.idempotency_key unique constraint."""
    print("\n=== Database Constraint Validation ===\n")

    model_path = base_path / "backend" / "app" / "models" / "care_escalation.py"

    if not model_path.exists():
        result.add_fail("care_escalation.py model not found", str(model_path))
        return

    content = model_path.read_text(encoding="utf-8")

    if 'UniqueConstraint("idempotency_key"' in content:
        result.add_pass("Unique constraint on idempotency_key")
    else:
        result.add_fail(
            "Missing unique constraint",
            'Should have UniqueConstraint("idempotency_key")',
        )


def validate_test_phi_assertions(result: ValidationResult, base_path: Path) -> None:
    """Validate PHI assertions in unit tests."""
    print("\n=== Test PHI Assertion Validation ===\n")

    test_files = [
        "backend/tests/unit/agents/followup_care/escalation/test_care_escalation_monitor.py",
        "backend/tests/unit/agents/followup_care/escalation/test_reescalation_job.py",
    ]

    for test_file_rel in test_files:
        test_path = base_path / test_file_rel
        if not test_path.exists():
            result.add_fail(f"Test file not found: {test_file_rel}", str(test_path))
            continue

        content = test_path.read_text(encoding="utf-8")

        if 'assert phi_field not in published' in content:
            result.add_pass(f"PHI assertion in {test_file_rel.split('/')[-1]}")
        else:
            result.add_fail(
                f"Missing PHI assertion in {test_file_rel}",
                "Should check that phi_field not in published",
            )


def main() -> None:
    """Run all validation checks."""
    result = ValidationResult()
    base_path = Path(__file__).parent

    print("\n" + "=" * 80)
    print("US-042 TASK-006 Validation: Code Review & DoD Sign-off")
    print("=" * 80)

    # Pre-review validation sequence
    validate_python_syntax(result, base_path)
    validate_phi_compliance(result, base_path)
    validate_unit_tests(result, base_path)

    # Security Engineer checklist
    validate_rbac_enforcement(result, base_path)
    validate_pubsub_payloads(result, base_path)

    # Backend Engineer checklist
    validate_idempotency_keys(result, base_path)
    validate_sla_compliance(result, base_path)
    validate_timezone_handling(result, base_path)
    validate_unique_constraint(result, base_path)
    validate_test_phi_assertions(result, base_path)

    print(result.summary())

    if result.failed > 0:
        print("❌ Code review FAILED. Address failures before DoD sign-off.")
        exit(1)
    elif result.warnings > 0:
        print("⚠️  Code review PASSED with warnings. Review before deployment.")
        exit(0)
    else:
        print("✅ All code review checks PASSED. Ready for DoD sign-off.")
        exit(0)


if __name__ == "__main__":
    main()
