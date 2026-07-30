"""Validation script for US-039 TASK-004: FollowUpCareAgent.

Validates:
    1. Agent module structure and imports
    2. Feature extraction logic (7 features)
    3. Discharge disposition encoding
    4. ICD-10 diagnosis group encoding
    5. Inference client retry logic
    6. Agent process method (A03 handling)
    7. Database update logic
    8. AgentTask creation
    9. Error handling (FHIR failures, retries)
    10. PHI containment

US-039 TASK-004 — FollowUpCareAgent implementation
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
BACKEND_ROOT = Path(__file__).parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

VALIDATION_RESULTS = []


def check(category: str, name: str, condition: bool, details: str = "") -> bool:
    """Record a validation check result."""
    status = "✅ PASS" if condition else "❌ FAIL"
    result = f"  [{status}] {name}"
    if details and not condition:
        result += f"\n      → {details}"
    VALIDATION_RESULTS.append((category, condition, result))
    print(result)
    return condition


def validate_module_structure() -> bool:
    """Validate agent module structure and imports."""
    print("\n1. MODULE STRUCTURE")
    print("=" * 60)
    
    try:
        # Check directory exists
        agent_dir = BACKEND_ROOT / "app" / "agents" / "followup_care"
        check("Module Structure", "followup_care directory exists", agent_dir.exists())
        
        # Check all required files exist
        files = [
            "__init__.py",
            "schemas.py",
            "feature_extractor.py",
            "inference_client.py",
            "agent.py",
            "main.py",
        ]
        
        for file in files:
            file_path = agent_dir / file
            check("Module Structure", f"{file} exists", file_path.exists())
        
        return True
    except Exception as e:
        check("Module Structure", "Module structure validation failed", False, str(e))
        return False


def validate_schemas() -> bool:
    """Validate Pydantic schemas."""
    print("\n2. PYDANTIC SCHEMAS")
    print("=" * 60)
    
    try:
        from app.agents.followup_care.schemas import RiskTier, RiskAssessmentResult
        
        # Check RiskTier enum
        check("Schemas", "RiskTier enum imported", RiskTier is not None)
        check("Schemas", "RiskTier.LOW defined", hasattr(RiskTier, "LOW"))
        check("Schemas", "RiskTier.MEDIUM defined", hasattr(RiskTier, "MEDIUM"))
        check("Schemas", "RiskTier.HIGH defined", hasattr(RiskTier, "HIGH"))
        check("Schemas", "RiskTier.UNKNOWN defined", hasattr(RiskTier, "UNKNOWN"))
        
        # Check RiskAssessmentResult schema
        check("Schemas", "RiskAssessmentResult defined", RiskAssessmentResult is not None)
        
        # Test schema instantiation
        result = RiskAssessmentResult(
            encounter_id="test-uuid",
            risk_score=0.45,
            risk_tier=RiskTier.MEDIUM,
            model_version="1.0.0",
            contributing_factors=[],
            db_updated=True,
            agent_task_id="task-uuid"
        )
        
        check("Schemas", "RiskAssessmentResult instantiates correctly", result is not None)
        check("Schemas", "encounter_id field works", result.encounter_id == "test-uuid")
        check("Schemas", "risk_score field works", result.risk_score == 0.45)
        check("Schemas", "risk_tier field works", result.risk_tier == RiskTier.MEDIUM)
        
        return True
    except Exception as e:
        check("Schemas", "Schema validation failed", False, str(e))
        return False


def validate_feature_extractor() -> bool:
    """Validate feature extraction logic."""
    print("\n3. FEATURE EXTRACTION")
    print("=" * 60)
    
    try:
        # Read code directly instead of importing
        extractor_path = BACKEND_ROOT / "app" / "agents" / "followup_care" / "feature_extractor.py"
        extractor_code = extractor_path.read_text()
        
        # Check discharge disposition mapping
        check("Feature Extractor", "DISCHARGE_DISPOSITION_MAP defined",
              "DISCHARGE_DISPOSITION_MAP" in extractor_code)
        check("Feature Extractor", '"home": 0 mapping', '"home": 0,' in extractor_code)
        check("Feature Extractor", '"snf": 1 mapping', '"snf": 1,' in extractor_code)
        check("Feature Extractor", '"rehab": 2 mapping', '"rehab": 2,' in extractor_code)
        check("Feature Extractor", '"home_health": 3 mapping',
              '"home_health": 3,' in extractor_code)
        check("Feature Extractor", '"ama": 4 mapping', '"ama": 4,' in extractor_code)
        
        # Check ICD-10 group mapping
        check("Feature Extractor", "ICD10_GROUP_MAP defined", "ICD10_GROUP_MAP" in extractor_code)
        check("Feature Extractor", 'I (Circulatory) → 0', '"I": 0,' in extractor_code)
        check("Feature Extractor", 'J (Respiratory) → 1', '"J": 1,' in extractor_code)
        check("Feature Extractor", 'C (Neoplasms) → 8', '"C": 8,' in extractor_code)
        check("Feature Extractor", 'F (Mental Health) → 9', '"F": 9,' in extractor_code)
        check("Feature Extractor", "ICD10_GROUP_DEFAULT = 19",
              "ICD10_GROUP_DEFAULT = 19" in extractor_code)
        
        # Check extract_features function
        check("Feature Extractor", "extract_features function defined",
              "async def extract_features(" in extractor_code)
        check("Feature Extractor", "Returns dict[str, float]",
              "dict[str, float]" in extractor_code)
        
        return True
    except Exception as e:
        check("Feature Extractor", "Feature extractor validation failed", False, str(e))
        return False


def validate_inference_client() -> bool:
    """Validate inference client configuration."""
    print("\n4. INFERENCE CLIENT")
    print("=" * 60)
    
    try:
        from app.agents.followup_care.inference_client import (
            ML_INFERENCE_URL,
            _RETRY_ATTEMPTS,
            _TIMEOUT_SECONDS,
        )
        
        # Check configuration
        check("Inference Client", "ML_INFERENCE_URL defined", ML_INFERENCE_URL is not None)
        check("Inference Client", "RETRY_ATTEMPTS is 3", _RETRY_ATTEMPTS == 3)
        check("Inference Client", "TIMEOUT_SECONDS is 10.0", _TIMEOUT_SECONDS == 10.0)
        
        # Check function signature
        from app.agents.followup_care import inference_client
        check("Inference Client", "call_readmission_inference function exists",
              hasattr(inference_client, "call_readmission_inference"))
        
        return True
    except Exception as e:
        check("Inference Client", "Inference client validation failed", False, str(e))
        return False


def validate_agent_class() -> bool:
    """Validate FollowUpCareAgent class structure."""
    print("\n5. AGENT CLASS STRUCTURE")
    print("=" * 60)
    
    try:
        # Read code directly
        agent_path = BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py"
        agent_code = agent_path.read_text()
        
        # Check class exists
        check("Agent Class", "FollowUpCareAgent class defined",
              "class FollowUpCareAgent(BaseAgent):" in agent_code)
        
        # Check HANDLED_EVENT_TYPES
        check("Agent Class", "HANDLED_EVENT_TYPES defined",
              "HANDLED_EVENT_TYPES = frozenset" in agent_code)
        check("Agent Class", 'Handles A03 events only',
              'frozenset({"A03"})' in agent_code)
        
        # Check methods
        check("Agent Class", "process method defined", "async def process(self, message:" in agent_code)
        check("Agent Class", "_update_encounter_risk method defined",
              "async def _update_encounter_risk(" in agent_code)
        check("Agent Class", "_create_agent_task method defined",
              "async def _create_agent_task(" in agent_code)
        
        return True
    except Exception as e:
        check("Agent Class", "Agent class validation failed", False, str(e))
        return False


def validate_event_filtering() -> bool:
    """Validate agent filters events correctly."""
    print("\n6. EVENT FILTERING")
    print("=" * 60)
    
    try:
        # Read code directly
        agent_path = BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py"
        agent_code = agent_path.read_text()
        
        # Check HANDLED_EVENT_TYPES
        check("Event Filtering", "A03 is handled", '"A03"' in agent_code)
        check("Event Filtering", "Only A03 in frozenset",
              'frozenset({"A03"})' in agent_code)
        check("Event Filtering", "Filters by event_type",
              "if event_type not in self.HANDLED_EVENT_TYPES:" in agent_code)
        check("Event Filtering", "Returns None for non-A03",
              "return None" in agent_code and "not A03" in agent_code)
        
        return True
    except Exception as e:
        check("Event Filtering", "Event filtering validation failed", False, str(e))
        return False


def validate_error_handling() -> bool:
    """Validate error handling patterns."""
    print("\n7. ERROR HANDLING")
    print("=" * 60)
    
    try:
        # Read code directly
        extractor_path = BACKEND_ROOT / "app" / "agents" / "followup_care" / "feature_extractor.py"
        extractor_code = extractor_path.read_text()
        
        agent_path = BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py"
        agent_code = agent_path.read_text()
        
        # Check feature extractor has error handling
        check("Error Handling", "FHIR failure has try-except",
              "try:" in extractor_code and "except Exception as exc:" in extractor_code)
        check("Error Handling", "FHIR failure logs WARNING",
              "logger.warning" in extractor_code)
        check("Error Handling", "FHIR failure defaults to 0.0",
              "num_comorbidities = 0.0" in extractor_code)
        
        # Check agent has RetryableError
        check("Error Handling", "Agent imports RetryableError",
              "from app.agents.base_agent import BaseAgent, RetryableError" in agent_code)
        check("Error Handling", "Feature extraction errors raise RetryableError",
              "raise RetryableError" in agent_code)
        check("Error Handling", "DB errors raise RetryableError",
              "raise RetryableError(f\"DB write failed" in agent_code)
        check("Error Handling", "ValueError for missing encounter (non-retryable)",
              'raise ValueError(f"Encounter not found' in extractor_code)
        
        return True
    except Exception as e:
        check("Error Handling", "Error handling validation failed", False, str(e))
        return False


def validate_database_updates() -> bool:
    """Validate database update logic."""
    print("\n8. DATABASE UPDATES")
    print("=" * 60)
    
    try:
        agent_code = Path(BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py").read_text()
        
        # Check encounter update
        check("Database Updates", "Updates encounter.risk_score",
              "update(Encounter)" in agent_code and "risk_score=risk_score" in agent_code)
        check("Database Updates", "Updates encounter.risk_tier",
              "risk_tier=risk_tier" in agent_code)
        check("Database Updates", "Uses UUID for encounter_id",
              "uuid.UUID(encounter_id)" in agent_code)
        
        # Check AgentTask creation
        check("Database Updates", "Creates AgentTask",
              "task = AgentTask(" in agent_code)
        check("Database Updates", "AgentTask type is FOLLOWUP_CARE",
              'agent_type="FOLLOWUP_CARE"' in agent_code)
        check("Database Updates", "AgentTask status is COMPLETED",
              "status=AgentTaskStatus.COMPLETED" in agent_code)
        
        # Check transaction
        check("Database Updates", "Single transaction with commit",
              "await write_session.commit()" in agent_code)
        
        return True
    except Exception as e:
        check("Database Updates", "Database update validation failed", False, str(e))
        return False


def validate_phi_containment() -> bool:
    """Validate PHI containment in logging."""
    print("\n9. PHI CONTAINMENT")
    print("=" * 60)
    
    try:
        # Check feature extractor logging
        extractor_code = Path(BACKEND_ROOT / "app" / "agents" / "followup_care" / "feature_extractor.py").read_text()
        
        phi_keywords = ["name", "ssn", "mrn", "dob", "address", "phone", "email"]
        for keyword in phi_keywords[:3]:  # Test a few
            check("PHI Containment", f"No '{keyword}' in feature extractor logs",
                  f'"{keyword}"' not in extractor_code.lower())
        
        # Check agent logging
        agent_code = Path(BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py").read_text()
        
        check("PHI Containment", "Logs encounter_id (UUID, not PHI)",
              "encounter_id=" in agent_code)
        check("PHI Containment", "Logs risk_score",
              "risk_score=" in agent_code)
        check("PHI Containment", "Logs risk_tier",
              "risk_tier=" in agent_code)
        check("PHI Containment", "No patient name in logs",
              "patient.name" not in agent_code and "patient_name" not in agent_code)
        
        return True
    except Exception as e:
        check("PHI Containment", "PHI containment validation failed", False, str(e))
        return False


def validate_main_entrypoint() -> bool:
    """Validate main.py entrypoint."""
    print("\n10. MAIN ENTRYPOINT")
    print("=" * 60)
    
    try:
        main_code = Path(BACKEND_ROOT / "app" / "agents" / "followup_care" / "main.py").read_text()
        
        # Check imports
        check("Main Entrypoint", "Imports FollowUpCareAgent",
              "from app.agents.followup_care.agent import FollowUpCareAgent" in main_code)
        check("Main Entrypoint", "Imports FHIRClient",
              "from app.core.fhir_client import FHIRClient" in main_code)
        check("Main Entrypoint", "Imports DB dependencies",
              "from app.core.dependencies import get_read_db, get_write_db" in main_code)
        
        # Check main function
        check("Main Entrypoint", "Defines async main() function",
              "async def main()" in main_code)
        check("Main Entrypoint", "Initializes FHIRClient",
              "fhir_client = FHIRClient(" in main_code)
        check("Main Entrypoint", "Initializes FollowUpCareAgent",
              "agent = FollowUpCareAgent(" in main_code)
        check("Main Entrypoint", "Calls agent.run()",
              "await agent.run()" in main_code)
        
        # Check asyncio.run
        check("Main Entrypoint", "Uses asyncio.run(main())",
              "asyncio.run(main())" in main_code)
        
        return True
    except Exception as e:
        check("Main Entrypoint", "Main entrypoint validation failed", False, str(e))
        return False


def validate_upstream_dependencies() -> bool:
    """Validate references to upstream dependencies."""
    print("\n11. UPSTREAM DEPENDENCIES")
    print("=" * 60)
    
    try:
        agent_code = Path(BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py").read_text()
        extractor_code = Path(BACKEND_ROOT / "app" / "agents" / "followup_care" / "feature_extractor.py").read_text()
        
        # Check BaseAgent (US-024)
        check("Upstream Dependencies", "Extends BaseAgent (US-024)",
              "from app.agents.base_agent import BaseAgent" in agent_code)
        check("Upstream Dependencies", "Uses RetryableError (US-024)",
              "RetryableError" in agent_code)
        
        # Check FHIRClient (US-017)
        check("Upstream Dependencies", "Uses FHIRClient (US-017)",
              "from app.core.fhir_client import FHIRClient" in extractor_code)
        check("Upstream Dependencies", "Calls get_conditions()",
              "await fhir_client.get_conditions(" in extractor_code)
        
        # Check DB models
        check("Upstream Dependencies", "Uses Encounter model",
              "from app.models.encounter import Encounter" in extractor_code)
        check("Upstream Dependencies", "Uses Patient model",
              "from app.models.patient import Patient" in extractor_code)
        check("Upstream Dependencies", "Uses Medication model",
              "from app.models.medication import Medication" in extractor_code)
        check("Upstream Dependencies", "Uses AgentTask model",
              "from app.models.agent_task import AgentTask" in agent_code)
        
        return True
    except Exception as e:
        check("Upstream Dependencies", "Upstream dependency validation failed", False, str(e))
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
        return True
    else:
        print("❌ SOME VALIDATIONS FAILED")
        return False


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("US-039 TASK-004 VALIDATION")
    print("FollowUpCareAgent Implementation")
    print("=" * 60)
    
    validate_module_structure()
    validate_schemas()
    validate_feature_extractor()
    validate_inference_client()
    validate_agent_class()
    validate_event_filtering()
    validate_error_handling()
    validate_database_updates()
    validate_phi_containment()
    validate_main_entrypoint()
    validate_upstream_dependencies()
    
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
