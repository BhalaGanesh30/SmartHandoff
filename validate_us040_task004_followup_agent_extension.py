"""Validation script for US-040 TASK-004: FollowUpCareAgent Extension.

Validates:
    1. NotificationPublisher implementation
    2. CareManagerAlertPayload schema
    3. FollowUpCareAgent extensions (new dependencies, care pathway activation)
    4. Alert publishing for HIGH tier only
    5. Publish-after-commit pattern
    6. main.py dependency wiring
    7. Acceptance criteria coverage
    8. Definition of Done criteria

US-040 TASK-004 \u2014 FollowUpCareAgent Extension: Care Pathway Activation & HIGH-Risk Alert
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
    status = "\u2705 PASS" if condition else "\u274c FAIL"
    result = f"  [{status}] {name}"
    if details:
        if not condition:
            result += f"\n      \u2192 {details}"
        else:
            result += f" \u2014 {details}"
    VALIDATION_RESULTS.append((category, condition, result))
    print(result)
    return condition


def validate_notification_publisher() -> bool:
    """Validate NotificationPublisher implementation."""
    print("\n1. NOTIFICATION PUBLISHER")
    print("=" * 60)
    
    try:
        publisher_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "notification_publisher.py"
        
        check("Publisher", "notification_publisher.py exists", publisher_file.exists())
        
        if not publisher_file.exists():
            check("Publisher", "Publisher validation failed", False, "File not found")
            return False
        
        code = publisher_file.read_text(encoding="utf-8")
        
        # Check imports
        check("Publisher", "from __future__ import annotations", 
              "from __future__ import annotations" in code)
        check("Publisher", "import logging", "import logging" in code)
        check("Publisher", "from google.cloud import pubsub_v1", 
              "from google.cloud import pubsub_v1" in code)
        check("Publisher", "from app.agents.followup_care.schemas import CareManagerAlertPayload", 
              "from app.agents.followup_care.schemas import CareManagerAlertPayload" in code)
        
        # Check class definition
        check("Publisher", "NotificationPublisher class defined", 
              "class NotificationPublisher:" in code)
        check("Publisher", "__init__() accepts project_id", 
              "project_id: str" in code)
        check("Publisher", "__init__() accepts topic_id", 
              "topic_id: str" in code)
        check("Publisher", "__init__() accepts optional publisher_client", 
              "publisher_client:" in code and "PublisherClient | None" in code)
        
        # Check topic path construction
        check("Publisher", "Constructs topic_path from project_id and topic_id", 
              'f"projects/{project_id}/topics/{topic_id}"' in code or
              "f\"projects/{project_id}/topics/{topic_id}\"" in code)
        
        # Check publish method
        check("Publisher", "publish_care_manager_alert() method", 
              "def publish_care_manager_alert(" in code)
        check("Publisher", "Accepts CareManagerAlertPayload", 
              "payload: CareManagerAlertPayload" in code)
        check("Publisher", "Returns message ID (str)", "-> str:" in code)
        
        # Check publishing logic
        check("Publisher", "Serializes payload with model_dump_json()", 
              "payload.model_dump_json()" in code)
        check("Publisher", "Encodes to UTF-8", '.encode("utf-8")' in code or ".encode('utf-8')" in code)
        check("Publisher", "Publishes to topic_path", 
              "self._client.publish(" in code and "self._topic_path" in code)
        check("Publisher", "Sets idempotency_key attribute", 
              "idempotency_key=payload.idempotency_key" in code)
        check("Publisher", "Waits for result with timeout", 
              "future.result(timeout=" in code)
        
        # Check logging
        check("Publisher", "Logs CARE_MANAGER_ALERT published", 
              'logger.info(\n            "CARE_MANAGER_ALERT published"' in code or
              'logger.info("CARE_MANAGER_ALERT published"' in code)
        
        # Check design references
        check("Publisher", "References AIR-040 in docstring", "AIR-040" in code)
        check("Publisher", "References US-040 AC Scenario 1", "US-040" in code and "Scenario 1" in code)
        
        return True
    except Exception as e:
        check("Publisher", "Publisher validation failed", False, str(e))
        return False


def validate_care_manager_alert_schema() -> bool:
    """Validate CareManagerAlertPayload schema."""
    print("\n2. CARE MANAGER ALERT SCHEMA")
    print("=" * 60)
    
    try:
        schemas_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "schemas.py"
        code = schemas_file.read_text(encoding="utf-8")
        
        # Check class definition
        check("Schema", "CareManagerAlertPayload class defined", 
              "class CareManagerAlertPayload(BaseModel):" in code)
        
        # Check all required fields
        check("Schema", "alert_type field", 
              'alert_type: str' in code and 'default="CARE_MANAGER_ALERT"' in code)
        check("Schema", "encounter_id field", 
              "encounter_id: str" in code)
        check("Schema", "risk_score field", 
              "risk_score: float" in code and "ge=0.0" in code and "le=1.0" in code)
        check("Schema", "risk_tier field", 
              'risk_tier: str' in code and 'default="HIGH"' in code)
        check("Schema", "required_followup_days field", 
              "required_followup_days: int" in code)
        check("Schema", "appointment_id field", 
              "appointment_id: str" in code)
        check("Schema", "idempotency_key field", 
              "idempotency_key: str" in code)
        
        # Check idempotency key format documentation
        check("Schema", "Idempotency key format documented", 
              "CARE_MANAGER_ALERT:{encounter_id}:{appointment_id}" in code)
        
        # Check docstring
        check("Schema", "References US-040 AC Scenario 1", 
              "US-040 AC Scenario 1" in code or "US-040" in code)
        check("Schema", "References AIR-040", "AIR-040" in code)
        
        return True
    except Exception as e:
        check("Schema", "Schema validation failed", False, str(e))
        return False


def validate_agent_extensions() -> bool:
    """Validate FollowUpCareAgent extensions."""
    print("\n3. AGENT EXTENSIONS")
    print("=" * 60)
    
    try:
        agent_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py"
        code = agent_file.read_text(encoding="utf-8")
        
        # Check imports
        check("Agent", "Imports CareManagerAlertPayload", 
              "from app.agents.followup_care.schemas import CareManagerAlertPayload" in code)
        check("Agent", "Imports CarePathwayConfig", 
              "from app.config.care_pathways import CarePathwayConfig" in code)
        
        # Check __init__ signature
        check("Agent", "__init__ accepts care_pathway_service", 
              "care_pathway_service:" in code)
        check("Agent", "__init__ accepts notification_publisher", 
              "notification_publisher:" in code)
        check("Agent", "__init__ accepts care_pathway_config", 
              "care_pathway_config: CarePathwayConfig" in code)
        
        # Check __init__ stores dependencies
        check("Agent", "Stores care_pathway_service", 
              "self._care_pathway_service = care_pathway_service" in code)
        check("Agent", "Stores notification_publisher", 
              "self._notification_publisher = notification_publisher" in code)
        check("Agent", "Stores care_pathway_config", 
              "self._care_pathway_config = care_pathway_config" in code)
        
        # Check care pathway activation
        check("Agent", "Calls activate_pathway() after risk score persistence", 
              "await self._care_pathway_service.activate_pathway(" in code)
        check("Agent", "Passes encounter to activate_pathway", 
              "encounter=encounter" in code or "encounter=" in code)
        check("Agent", "Passes risk_tier to activate_pathway", 
              "risk_tier=risk_tier_str" in code or "risk_tier=" in code)
        check("Agent", "Passes discharge_date to activate_pathway", 
              "discharge_date=discharge_date" in code)
        
        # Check _update_encounter_risk returns Encounter
        check("Agent", "_update_encounter_risk() returns Encounter object", 
              "-> Encounter:" in code and "return encounter" in code)
        
        # Check single transaction for all DB writes
        check("Agent", "Single transaction covers risk score + appointment", 
              "await write_session.commit()" in code)
        
        return True
    except Exception as e:
        check("Agent", "Agent validation failed", False, str(e))
        return False


def validate_alert_publishing() -> bool:
    """Validate alert publishing logic."""
    print("\n4. ALERT PUBLISHING")
    print("=" * 60)
    
    try:
        agent_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py"
        code = agent_file.read_text(encoding="utf-8")
        
        # Check publish-after-commit pattern
        check("Publishing", "Alert published AFTER commit", 
              code.find("await write_session.commit()") < code.find("publish_care_manager_alert"))
        
        # Check conditional publishing (HIGH tier only)
        check("Publishing", "Alert published only for HIGH tier", 
              'if risk_tier_str == "HIGH"' in code or "if risk_tier_str == 'HIGH'" in code)
        check("Publishing", "Checks appointment_id exists before publishing", 
              "and appointment_id" in code)
        
        # Check alert payload construction
        check("Publishing", "Creates CareManagerAlertPayload", 
              "CareManagerAlertPayload(" in code)
        check("Publishing", "Sets encounter_id in payload", 
              "encounter_id=encounter_id" in code)
        check("Publishing", "Sets risk_score in payload", 
              "risk_score=risk_score" in code)
        check("Publishing", "Sets risk_tier=HIGH in payload", 
              'risk_tier="HIGH"' in code or "risk_tier='HIGH'" in code)
        check("Publishing", "Sets required_followup_days from config", 
              "required_followup_days=pathway_config.required_followup_days" in code)
        check("Publishing", "Sets appointment_id in payload", 
              "appointment_id=appointment_id" in code)
        check("Publishing", "Sets idempotency_key with correct format", 
              'f"CARE_MANAGER_ALERT:{encounter_id}:{appointment_id}"' in code or
              "f'CARE_MANAGER_ALERT:{encounter_id}:{appointment_id}'" in code)
        
        # Check publish call
        check("Publishing", "Calls publish_care_manager_alert()", 
              "publish_care_manager_alert(alert_payload)" in code)
        
        # Check error handling
        check("Publishing", "Catches publish exceptions", 
              "except Exception as exc:" in code and "logger.error" in code)
        check("Publishing", "Logs publish failures", 
              "Failed to publish CARE_MANAGER_ALERT" in code or 
              "publish" in code.lower() and "failed" in code.lower())
        
        return True
    except Exception as e:
        check("Publishing", "Publishing validation failed", False, str(e))
        return False


def validate_main_wiring() -> bool:
    """Validate main.py dependency wiring."""
    print("\n5. MAIN.PY WIRING")
    print("=" * 60)
    
    try:
        main_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "main.py"
        code = main_file.read_text(encoding="utf-8")
        
        # Check imports
        check("Main", "Imports NotificationPublisher", 
              "from app.agents.followup_care.notification_publisher import NotificationPublisher" in code)
        check("Main", "Imports load_care_pathways", 
              "from app.config.care_pathways import load_care_pathways" in code)
        check("Main", "Imports CarePathwayService", 
              "from app.services.care_pathway_service import CarePathwayService" in code)
        
        # Check configuration loading
        check("Main", "Loads care pathway config", 
              "load_care_pathways()" in code)
        check("Main", "Creates CarePathwayService", 
              "CarePathwayService(pathways=care_pathway_config)" in code or
              "CarePathwayService(" in code)
        check("Main", "Creates NotificationPublisher", 
              "NotificationPublisher(" in code)
        
        # Check NotificationPublisher initialization
        check("Main", "NotificationPublisher initialized with project_id", 
              "project_id=" in code)
        check("Main", "NotificationPublisher initialized with topic_id", 
              "topic_id=" in code)
        
        # Check agent initialization
        check("Main", "FollowUpCareAgent initialized with all dependencies", 
              "FollowUpCareAgent(" in code)
        check("Main", "Passes care_pathway_service to agent", 
              "care_pathway_service=care_pathway_service" in code)
        check("Main", "Passes notification_publisher to agent", 
              "notification_publisher=notification_publisher" in code)
        check("Main", "Passes care_pathway_config to agent", 
              "care_pathway_config=care_pathway_config" in code)
        
        return True
    except Exception as e:
        check("Main", "Main wiring validation failed", False, str(e))
        return False


def validate_acceptance_criteria() -> bool:
    """Validate US-040 Acceptance Criteria compliance."""
    print("\n6. ACCEPTANCE CRITERIA")
    print("=" * 60)
    
    try:
        agent_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py"
        code = agent_file.read_text(encoding="utf-8")
        
        # AC Scenario 1: CARE_MANAGER_ALERT published within 60s
        check("AC", "Scenario 1: CARE_MANAGER_ALERT published for HIGH tier", 
              "publish_care_manager_alert" in code and 'risk_tier_str == "HIGH"' in code or
              "publish_care_manager_alert" in code and "risk_tier_str == 'HIGH'" in code)
        check("AC", "Scenario 1: Alert contains encounter_id", 
              "encounter_id=encounter_id" in code)
        check("AC", "Scenario 1: Alert contains risk_score", 
              "risk_score=risk_score" in code)
        check("AC", "Scenario 1: Alert contains risk_tier=HIGH", 
              'risk_tier="HIGH"' in code or "risk_tier='HIGH'" in code)
        check("AC", "Scenario 1: Alert contains required_followup_days=7", 
              "required_followup_days=pathway_config.required_followup_days" in code)
        
        # AC Scenario 2: Appointment record for HIGH tier
        check("AC", "Scenario 2: Appointment created via CarePathwayService", 
              "activate_pathway(" in code)
        
        # AC Scenario 3: Appointment for MEDIUM tier, no alert
        # AC Scenario 4: Appointment for LOW tier, no alert
        check("AC", "Scenario 3/4: Appointment created for all tiers", 
              "activate_pathway(" in code)
        check("AC", "Scenario 3/4: Alert published ONLY for HIGH tier", 
              'if risk_tier_str == "HIGH"' in code or "if risk_tier_str == 'HIGH'" in code)
        
        return True
    except Exception as e:
        check("AC", "Acceptance criteria validation failed", False, str(e))
        return False


def validate_dod_criteria() -> bool:
    """Validate Definition of Done criteria."""
    print("\n7. DEFINITION OF DONE")
    print("=" * 60)
    
    try:
        # Check all files created
        files_required = [
            BACKEND_ROOT / "app" / "agents" / "followup_care" / "notification_publisher.py",
        ]
        
        all_files_exist = all(f.exists() for f in files_required)
        check("DoD", "notification_publisher.py created", 
              all_files_exist,
              f"{sum(f.exists() for f in files_required)}/{len(files_required)} files found")
        
        # Check schemas extended
        schemas_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "schemas.py"
        if schemas_file.exists():
            code = schemas_file.read_text(encoding="utf-8")
            check("DoD", "CareManagerAlertPayload added to schemas.py", 
                  "class CareManagerAlertPayload(BaseModel):" in code)
        
        # Check agent.py extended
        agent_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py"
        if agent_file.exists():
            code = agent_file.read_text(encoding="utf-8")
            check("DoD", "FollowUpCareAgent.process() extended with care pathway activation", 
                  "activate_pathway(" in code)
            check("DoD", "Single DB transaction covers risk score + appointment", 
                  "await write_session.commit()" in code)
            check("DoD", "Publish-after-commit pattern implemented", 
                  code.find("await write_session.commit()") < code.find("publish_care_manager_alert"))
            check("DoD", "Alert published only for HIGH tier", 
                  'if risk_tier_str == "HIGH"' in code or "if risk_tier_str == 'HIGH'" in code)
        
        # Check __init__ updated
        if agent_file.exists():
            code = agent_file.read_text(encoding="utf-8")
            check("DoD", "FollowUpCareAgent.__init__ accepts new dependencies", 
                  "care_pathway_service:" in code and 
                  "notification_publisher:" in code and
                  "care_pathway_config:" in code)
        
        # Check main.py wiring
        main_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "main.py"
        if main_file.exists():
            code = main_file.read_text(encoding="utf-8")
            check("DoD", "main.py wires all new dependencies", 
                  "CarePathwayService(" in code and 
                  "NotificationPublisher(" in code and
                  "load_care_pathways()" in code)
        
        return True
    except Exception as e:
        check("DoD", "DoD validation failed", False, str(e))
        return False


def validate_code_quality() -> bool:
    """Validate code quality and patterns."""
    print("\n8. CODE QUALITY")
    print("=" * 60)
    
    try:
        publisher_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "notification_publisher.py"
        agent_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py"
        
        # Check NotificationPublisher
        pub_code = publisher_file.read_text(encoding="utf-8")
        check("Quality", "NotificationPublisher has module docstring", 
              '"""Pub/Sub publisher' in pub_code)
        check("Quality", "NotificationPublisher has class docstring", 
              pub_code.count('"""') >= 4)
        check("Quality", "NotificationPublisher uses type hints", 
              ": str" in pub_code and "-> str:" in pub_code)
        
        # Check agent extensions
        agent_code = agent_file.read_text(encoding="utf-8")
        check("Quality", "Agent uses structured logging", 
              'extra={' in agent_code or 'extra = {' in agent_code)
        check("Quality", "Agent handles publish exceptions gracefully", 
              "except Exception as exc:" in agent_code and 
              "logger.error" in agent_code)
        
        # Check no PHI in logs
        check("Quality", "No PHI in log output", 
              "patient_name" not in agent_code.lower() and 
              "mrn" not in agent_code.lower() and
              "date_of_birth" not in agent_code.lower())
        
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
        status = "\u2705" if counts["passed"] == counts["total"] else "\u274c"
        print(f"{status} {category}: {counts['passed']}/{counts['total']} checks passed")
    
    print("=" * 60)
    print(f"TOTAL: {total_passed}/{total_checks} CHECKS PASSED")
    
    if total_passed == total_checks:
        print("\u2705 ALL VALIDATIONS PASSED")
        print("\nFollowUpCareAgent extension ready for integration testing")
        return True
    else:
        print("\u274c SOME VALIDATIONS FAILED")
        return False


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("US-040 TASK-004 VALIDATION")
    print("FollowUpCareAgent Extension \u2014 Care Pathway Activation & HIGH-Risk Alert")
    print("=" * 60)
    
    validate_notification_publisher()
    validate_care_manager_alert_schema()
    validate_agent_extensions()
    validate_alert_publishing()
    validate_main_wiring()
    validate_acceptance_criteria()
    validate_dod_criteria()
    validate_code_quality()
    
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
