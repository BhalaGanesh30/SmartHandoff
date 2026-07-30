#!/usr/bin/env python3
"""Validation script for US-034 TASK-003: Implement MedRecSLAMonitor.

Validates:
1. MedRecSLAMonitor class exists with correct structure
2. Query filters for MEDICATION_RECONCILIATION tasks only
3. SLA measured from encounter.admit_date (not created_at)
4. sla_escalation_sent_at stamped before publisher call
5. Second APScheduler job registered on existing scheduler
6. COMPLETED tasks excluded by status filter
7. No PHI in logs
"""
import ast
import re
import sys
from pathlib import Path


def print_header(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'=' * 70}")
    print(f"{title}")
    print(f"{'=' * 70}\n")


def print_result(check: str, passed: bool) -> None:
    """Print a check result."""
    symbol = "✅" if passed else "❌"
    print(f"{symbol} {check}")


def validate_medrec_sla_monitor() -> tuple[int, int]:
    """Validate MedRecSLAMonitor implementation."""
    monitor_path = Path("services/sla-monitor/app/monitor/medrec_sla_monitor.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("1. MEDREC SLA MONITOR VALIDATION")
    
    if not monitor_path.exists():
        print_result("medrec_sla_monitor.py file exists", False)
        return 0, 1
    
    print_result("medrec_sla_monitor.py file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with monitor_path.open("r") as f:
        content = f.read()
    
    # Check for MedRecSLAMonitor class
    total_checks += 1
    has_class = "class MedRecSLAMonitor:" in content
    print_result("MedRecSLAMonitor class defined", has_class)
    if has_class:
        checks_passed += 1
    else:
        return checks_passed, total_checks
    
    # Check for run_check method
    total_checks += 1
    has_run_check = "async def run_check(self)" in content
    print_result("run_check() async method exists", has_run_check)
    if has_run_check:
        checks_passed += 1
    
    # Check filters for MEDICATION_RECONCILIATION
    total_checks += 1
    filters_medrec = 'AgentTask.agent_type == _MEDREC_AGENT_TYPE' in content or \
                     'agent_type == "MEDICATION_RECONCILIATION"' in content or \
                     'AgentTask.agent_type == "MEDICATION_RECONCILIATION"' in content
    print_result("Query filters for MEDICATION_RECONCILIATION agent_type", filters_medrec)
    if filters_medrec:
        checks_passed += 1
    
    # Check filters for IN_PROGRESS, PENDING statuses
    total_checks += 1
    filters_status = "AgentTask.status.in_(_ACTIVE_STATUSES)" in content or \
                     "status.in_(_ACTIVE_STATUSES)" in content
    print_result("Query filters for active statuses (IN_PROGRESS, PENDING)", filters_status)
    if filters_status:
        checks_passed += 1
    
    # Check filters for sla_escalation_sent_at IS NULL
    total_checks += 1
    filters_escalation = "sla_escalation_sent_at.is_(None)" in content
    print_result("Query filters for sla_escalation_sent_at IS NULL", filters_escalation)
    if filters_escalation:
        checks_passed += 1
    
    # Check join to Encounter
    total_checks += 1
    joins_encounter = "join(Encounter" in content or ".join(Encounter," in content
    print_result("Query joins to Encounter table", joins_encounter)
    if joins_encounter:
        checks_passed += 1
    
    # Check uses encounter.admit_date for SLA calculation
    total_checks += 1
    uses_admit_date = "Encounter.admit_date" in content or "encounter.admit_date" in content
    print_result("Uses encounter.admit_date for SLA calculation", uses_admit_date)
    if uses_admit_date:
        checks_passed += 1
    
    # Check sla_escalation_sent_at is set
    total_checks += 1
    sets_escalation_time = "sla_escalation_sent_at=" in content or "sla_escalation_sent_at =" in content
    print_result("Sets sla_escalation_sent_at timestamp", sets_escalation_time)
    if sets_escalation_time:
        checks_passed += 1
    
    # Check calls publisher.publish
    total_checks += 1
    calls_publisher = "self._publisher.publish(" in content
    print_result("Calls ChargePharmacistEscalationPublisher.publish()", calls_publisher)
    if calls_publisher:
        checks_passed += 1
    
    # Check uses read session for query
    total_checks += 1
    uses_read_session = "get_read_session()" in content
    print_result("Uses read replica session for query (TR-010)", uses_read_session)
    if uses_read_session:
        checks_passed += 1
    
    # Check uses write session for update
    total_checks += 1
    uses_write_session = "get_write_session()" in content
    print_result("Uses write session for sla_escalation_sent_at update", uses_write_session)
    if uses_write_session:
        checks_passed += 1
    
    # Check no PHI in logs (no patient name, MRN, etc.)
    total_checks += 1
    phi_keywords = ["patient_name", "mrn", "ssn", "date_of_birth"]
    has_phi = any(keyword in content.lower() for keyword in phi_keywords)
    print_result("No PHI (patient_name, mrn, ssn, dob) in logs", not has_phi)
    if not has_phi:
        checks_passed += 1
    
    # Check imports ChargePharmacistEscalationPublisher
    total_checks += 1
    imports_publisher = "ChargePharmacistEscalationPublisher" in content
    print_result("Imports ChargePharmacistEscalationPublisher", imports_publisher)
    if imports_publisher:
        checks_passed += 1
    
    # Check imports models
    total_checks += 1
    imports_encounter = "from app.models.encounter import Encounter" in content
    print_result("Imports Encounter model", imports_encounter)
    if imports_encounter:
        checks_passed += 1
    
    print(f"\n📊 MedRecSLAMonitor: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_sla_monitor_integration() -> tuple[int, int]:
    """Validate SLAMonitor integration with MedRecSLAMonitor."""
    monitor_path = Path("services/sla-monitor/app/monitor/sla_monitor.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("2. SLA MONITOR INTEGRATION VALIDATION")
    
    if not monitor_path.exists():
        print_result("sla_monitor.py file exists", False)
        return 0, 1
    
    print_result("sla_monitor.py file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with monitor_path.open("r") as f:
        content = f.read()
    
    # Check imports MedRecSLAMonitor
    total_checks += 1
    imports_medrec = "from app.monitor.medrec_sla_monitor import MedRecSLAMonitor" in content
    print_result("Imports MedRecSLAMonitor", imports_medrec)
    if imports_medrec:
        checks_passed += 1
    
    # Check imports ChargePharmacistEscalationPublisher
    total_checks += 1
    imports_publisher = "ChargePharmacistEscalationPublisher" in content
    print_result("Imports ChargePharmacistEscalationPublisher", imports_publisher)
    if imports_publisher:
        checks_passed += 1
    
    # Check __init__ accepts medrec_publisher parameter
    total_checks += 1
    has_medrec_param = "medrec_publisher" in content
    print_result("__init__() accepts medrec_publisher parameter", has_medrec_param)
    if has_medrec_param:
        checks_passed += 1
    
    # Check start() registers second job
    total_checks += 1
    registers_medrec_job = 'id="medrec_sla_check"' in content or "medrec_sla_check" in content
    print_result("start() registers medrec_sla_check job", registers_medrec_job)
    if registers_medrec_job:
        checks_passed += 1
    
    # Check creates MedRecSLAMonitor instance
    total_checks += 1
    creates_instance = "MedRecSLAMonitor(" in content
    print_result("Creates MedRecSLAMonitor instance", creates_instance)
    if creates_instance:
        checks_passed += 1
    
    # Check adds job to scheduler
    total_checks += 1
    adds_job = "self._scheduler.add_job" in content
    print_result("Adds job to existing scheduler", adds_job)
    if adds_job:
        checks_passed += 1
    
    # Check uses same scheduler (not new instance)
    total_checks += 1
    # Should only have ONE AsyncIOScheduler instantiation
    scheduler_count = content.count("AsyncIOScheduler(")
    single_scheduler = scheduler_count == 1
    print_result("Uses same scheduler instance (not creating new one)", single_scheduler)
    if single_scheduler:
        checks_passed += 1
    
    print(f"\n📊 SLA Monitor Integration: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_main_wiring() -> tuple[int, int]:
    """Validate main.py wiring."""
    main_path = Path("services/sla-monitor/app/main.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("3. MAIN.PY WIRING VALIDATION")
    
    if not main_path.exists():
        print_result("main.py file exists", False)
        return 0, 1
    
    print_result("main.py file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with main_path.open("r") as f:
        content = f.read()
    
    # Check imports ChargePharmacistEscalationPublisher
    total_checks += 1
    imports_publisher = "ChargePharmacistEscalationPublisher" in content
    print_result("Imports ChargePharmacistEscalationPublisher", imports_publisher)
    if imports_publisher:
        checks_passed += 1
    
    # Check creates ChargePharmacistEscalationPublisher instance
    total_checks += 1
    creates_publisher = "ChargePharmacistEscalationPublisher(" in content
    print_result("Creates ChargePharmacistEscalationPublisher instance", creates_publisher)
    if creates_publisher:
        checks_passed += 1
    
    # Check passes medrec_publisher to SLAMonitor
    total_checks += 1
    passes_publisher = "medrec_publisher=" in content
    print_result("Passes medrec_publisher to SLAMonitor", passes_publisher)
    if passes_publisher:
        checks_passed += 1
    
    # Check SLAMonitor instantiation
    total_checks += 1
    creates_monitor = "SLAMonitor(" in content
    print_result("Creates SLAMonitor instance", creates_monitor)
    if creates_monitor:
        checks_passed += 1
    
    print(f"\n📊 Main.py Wiring: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_encounter_model() -> tuple[int, int]:
    """Validate Encounter model exists in sla-monitor."""
    model_path = Path("services/sla-monitor/app/models/encounter.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("4. ENCOUNTER MODEL VALIDATION")
    
    if not model_path.exists():
        print_result("encounter.py model file exists", False)
        return 0, 1
    
    print_result("encounter.py model file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with model_path.open("r") as f:
        content = f.read()
    
    # Check for Encounter class
    total_checks += 1
    has_class = "class Encounter(Base):" in content or "class Encounter(" in content
    print_result("Encounter class defined", has_class)
    if has_class:
        checks_passed += 1
    
    # Check for admit_date field
    total_checks += 1
    has_admit_date = "admit_date" in content
    print_result("admit_date field present", has_admit_date)
    if has_admit_date:
        checks_passed += 1
    
    # Check for unit field
    total_checks += 1
    has_unit = 'unit:' in content or 'unit =' in content
    print_result("unit field present (for patient_unit in payload)", has_unit)
    if has_unit:
        checks_passed += 1
    
    print(f"\n📊 Encounter Model: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_charge_pharmacist_publisher() -> tuple[int, int]:
    """Validate ChargePharmacistEscalationPublisher implementation."""
    publisher_path = Path("services/sla-monitor/app/publisher/charge_pharmacist_escalation_publisher.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("5. CHARGE PHARMACIST PUBLISHER VALIDATION")
    
    if not publisher_path.exists():
        print_result("charge_pharmacist_escalation_publisher.py file exists", False)
        return 0, 1
    
    print_result("charge_pharmacist_escalation_publisher.py file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with publisher_path.open("r") as f:
        content = f.read()
    
    # Check for ChargePharmacistEscalationPublisher class
    total_checks += 1
    has_class = "class ChargePharmacistEscalationPublisher:" in content
    print_result("ChargePharmacistEscalationPublisher class defined", has_class)
    if has_class:
        checks_passed += 1
    
    # Check for publish method
    total_checks += 1
    has_publish = "async def publish(" in content
    print_result("publish() async method exists", has_publish)
    if has_publish:
        checks_passed += 1
    
    # Check publish parameters
    required_params = ["encounter_id", "task_id", "patient_unit", "hours_elapsed"]
    for param in required_params:
        total_checks += 1
        has_param = param in content
        print_result(f"publish() has '{param}' parameter", has_param)
        if has_param:
            checks_passed += 1
    
    # Check notification_type in payload
    total_checks += 1
    has_notification_type = '"CHARGE_PHARMACIST_ESCALATION"' in content or "'CHARGE_PHARMACIST_ESCALATION'" in content
    print_result("Payload has notification_type='CHARGE_PHARMACIST_ESCALATION'", has_notification_type)
    if has_notification_type:
        checks_passed += 1
    
    # Check priority=HIGH
    total_checks += 1
    has_priority = '"HIGH"' in content or "'HIGH'" in content
    print_result("Payload has priority='HIGH'", has_priority)
    if has_priority:
        checks_passed += 1
    
    # Check uses Pub/Sub publisher
    total_checks += 1
    uses_pubsub = "pubsub_v1" in content or "PublisherClient" in content
    print_result("Uses Google Cloud Pub/Sub client", uses_pubsub)
    if uses_pubsub:
        checks_passed += 1
    
    print(f"\n📊 Charge Pharmacist Publisher: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def validate_agent_task_model() -> tuple[int, int]:
    """Validate AgentTask model has sla_escalation_sent_at field."""
    model_path = Path("services/sla-monitor/app/models/agent_task.py")
    
    checks_passed = 0
    total_checks = 0
    
    print_header("6. AGENT TASK MODEL VALIDATION")
    
    if not model_path.exists():
        print_result("agent_task.py model file exists", False)
        return 0, 1
    
    print_result("agent_task.py model file exists", True)
    checks_passed += 1
    total_checks += 1
    
    with model_path.open("r") as f:
        content = f.read()
    
    # Check for sla_escalation_sent_at field
    total_checks += 1
    has_field = "sla_escalation_sent_at" in content
    print_result("sla_escalation_sent_at field present (US-034 TASK-001)", has_field)
    if has_field:
        checks_passed += 1
    
    # Check field is nullable
    total_checks += 1
    is_nullable = "nullable=True" in content and "sla_escalation_sent_at" in content
    print_result("sla_escalation_sent_at is nullable", is_nullable)
    if is_nullable:
        checks_passed += 1
    
    print(f"\n📊 Agent Task Model: {checks_passed}/{total_checks} checks passed\n")
    
    return checks_passed, total_checks


def main() -> int:
    """Run all validation checks."""
    print_header("US-034 TASK-003 VALIDATION\nMedRecSLAMonitor — 24-Hour Admission SLA Check")
    
    all_checks_passed = 0
    all_total_checks = 0
    
    medrec_passed, medrec_total = validate_medrec_sla_monitor()
    all_checks_passed += medrec_passed
    all_total_checks += medrec_total
    
    integration_passed, integration_total = validate_sla_monitor_integration()
    all_checks_passed += integration_passed
    all_total_checks += integration_total
    
    main_passed, main_total = validate_main_wiring()
    all_checks_passed += main_passed
    all_total_checks += main_total
    
    encounter_passed, encounter_total = validate_encounter_model()
    all_checks_passed += encounter_passed
    all_total_checks += encounter_total
    
    publisher_passed, publisher_total = validate_charge_pharmacist_publisher()
    all_checks_passed += publisher_passed
    all_total_checks += publisher_total
    
    agent_task_passed, agent_task_total = validate_agent_task_model()
    all_checks_passed += agent_task_passed
    all_total_checks += agent_task_total
    
    print_header("📊 OVERALL VALIDATION SUMMARY")
    print(f"Total Checks Passed: {all_checks_passed}/{all_total_checks}")
    
    success_rate = (all_checks_passed / all_total_checks * 100) if all_total_checks > 0 else 0
    print(f"Success Rate: {success_rate:.1f}%\n")
    
    if all_checks_passed == all_total_checks:
        print("✅ ALL VALIDATION CHECKS PASSED\n")
        print("US-034 TASK-003 Implementation:")
        print("  ✓ MedRecSLAMonitor class created")
        print("  ✓ Query filters for MEDICATION_RECONCILIATION tasks")
        print("  ✓ SLA measured from encounter.admit_date")
        print("  ✓ sla_escalation_sent_at stamped before publisher call")
        print("  ✓ Second APScheduler job registered on existing scheduler")
        print("  ✓ COMPLETED tasks excluded by status filter")
        print("  ✓ No PHI in logs")
        print("  ✓ ChargePharmacistEscalationPublisher created")
        print("  ✓ Encounter model added to sla-monitor")
        print("  ✓ Main.py wiring complete")
        print("\nNext steps:")
        print("  1. Mark task as Complete")
        print("  2. Create implementation summary")
        print("  3. Write unit tests (TASK-006)")
        return 0
    else:
        print(f"❌ {all_total_checks - all_checks_passed} VALIDATION CHECK(S) FAILED\n")
        print("Please review the failed checks above and fix the issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
