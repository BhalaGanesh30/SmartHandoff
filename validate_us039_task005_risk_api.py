"""Validation script for US-039 TASK-005: Risk API Endpoint.

Validates:
    1. Schema files exist and structure is correct
    2. Router implementation exists with proper endpoint
    3. Main.py registers the router
    4. Agent.py updated to use JSON output_summary
    5. RBAC role enforcement
    6. Response model fields
    7. Error handling patterns
    8. Database query patterns

US-039 TASK-005 — GET /api/v1/encounters/{id}/risk
"""
from __future__ import annotations

import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent
SERVICES_ROOT = PROJECT_ROOT / "services" / "api-gateway"
BACKEND_ROOT = PROJECT_ROOT / "backend"

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


def validate_schema_files() -> bool:
    """Validate schema file structure."""
    print("\n1. SCHEMA FILES")
    print("=" * 60)
    
    try:
        # Check directory exists
        schemas_dir = SERVICES_ROOT / "app" / "schemas"
        check("Schema Files", "schemas/ directory exists", schemas_dir.exists())
        
        # Check risk.py exists
        risk_schema = schemas_dir / "risk.py"
        check("Schema Files", "risk.py exists", risk_schema.exists())
        
        if risk_schema.exists():
            schema_code = risk_schema.read_text()
            
            # Check RiskTier enum
            check("Schema Files", "RiskTier enum defined", "class RiskTier(str, Enum):" in schema_code)
            check("Schema Files", "RiskTier.LOW", 'LOW = "LOW"' in schema_code)
            check("Schema Files", "RiskTier.MEDIUM", 'MEDIUM = "MEDIUM"' in schema_code)
            check("Schema Files", "RiskTier.HIGH", 'HIGH = "HIGH"' in schema_code)
            check("Schema Files", "RiskTier.UNKNOWN", 'UNKNOWN = "UNKNOWN"' in schema_code)
            
            # Check ContributingFactor model
            check("Schema Files", "ContributingFactor model defined",
                  "class ContributingFactor(BaseModel):" in schema_code)
            check("Schema Files", "ContributingFactor.feature field",
                  "feature: str" in schema_code)
            check("Schema Files", "ContributingFactor.shap_value field",
                  "shap_value: float" in schema_code)
            check("Schema Files", "ContributingFactor.feature_value field",
                  "feature_value: float" in schema_code)
            check("Schema Files", "ContributingFactor.direction field",
                  "direction: str" in schema_code)
            
            # Check EncounterRiskResponse model
            check("Schema Files", "EncounterRiskResponse model defined",
                  "class EncounterRiskResponse(BaseModel):" in schema_code)
            check("Schema Files", "EncounterRiskResponse.encounter_id field",
                  "encounter_id: str" in schema_code)
            check("Schema Files", "EncounterRiskResponse.risk_score field",
                  "risk_score: float | None" in schema_code)
            check("Schema Files", "EncounterRiskResponse.risk_tier field",
                  "risk_tier: RiskTier" in schema_code)
            check("Schema Files", "EncounterRiskResponse.contributing_factors field",
                  "contributing_factors: list[ContributingFactor]" in schema_code)
            check("Schema Files", "EncounterRiskResponse.model_version field",
                  "model_version: str | None" in schema_code)
            check("Schema Files", "EncounterRiskResponse.assessed_at field",
                  "assessed_at: str | None" in schema_code)
        
        return True
    except Exception as e:
        check("Schema Files", "Schema validation failed", False, str(e))
        return False


def validate_router_implementation() -> bool:
    """Validate router implementation."""
    print("\n2. ROUTER IMPLEMENTATION")
    print("=" * 60)
    
    try:
        # Check file exists
        router_file = SERVICES_ROOT / "app" / "routers" / "encounters_risk.py"
        check("Router", "encounters_risk.py exists", router_file.exists())
        
        if router_file.exists():
            router_code = router_file.read_text()
            
            # Check router setup
            check("Router", "APIRouter imported", "from fastapi import APIRouter" in router_code)
            check("Router", "router instance created", 'router = APIRouter(' in router_code)
            check("Router", "schemas imported",
                  "from app.schemas.risk import" in router_code)
            
            # Check endpoint definition
            check("Router", "GET endpoint decorator",
                  '@router.get(' in router_code)
            check("Router", "Endpoint path /encounters/{encounter_id}/risk",
                  '"/encounters/{encounter_id}/risk"' in router_code)
            check("Router", "Response model EncounterRiskResponse",
                  "response_model=EncounterRiskResponse" in router_code)
            
            # Check get_encounter_risk function
            check("Router", "get_encounter_risk function defined",
                  "async def get_encounter_risk(" in router_code)
            check("Router", "encounter_id parameter",
                  "encounter_id: str" in router_code)
            
            # Check database queries
            check("Router", "Encounter query",
                  "select(Encounter)" in router_code)
            check("Router", "Soft delete check (deleted_at)",
                  "deleted_at.is_(None)" in router_code or "Encounter.deleted_at.is_(None)" in router_code)
            check("Router", "AgentTask query",
                  "select(AgentTask)" in router_code)
            check("Router", "FOLLOWUP_CARE agent type filter",
                  'agent_type == "FOLLOWUP_CARE"' in router_code or 'agent_type="FOLLOWUP_CARE"' in router_code)
            check("Router", "COMPLETED status filter",
                  "COMPLETED" in router_code)
            
            # Check JSON parsing
            check("Router", "JSON parsing of output_summary",
                  "json.loads(" in router_code)
            check("Router", "contributing_factors extraction",
                  'get("contributing_factors"' in router_code or '"contributing_factors"' in router_code)
            check("Router", "model_version extraction",
                  'get("model_version"' in router_code or '"model_version"' in router_code)
            
            # Check error handling
            check("Router", "UUID validation",
                  "uuid.UUID(" in router_code)
            check("Router", "HTTP 400 for invalid UUID",
                  "HTTP_400_BAD_REQUEST" in router_code)
            check("Router", "HTTP 404 for not found",
                  "HTTP_404_NOT_FOUND" in router_code)
            check("Router", "HTTP 403 for forbidden",
                  "HTTP_403_FORBIDDEN" in router_code)
        
        return True
    except Exception as e:
        check("Router", "Router validation failed", False, str(e))
        return False


def validate_rbac_enforcement() -> bool:
    """Validate RBAC role enforcement."""
    print("\n3. RBAC ENFORCEMENT")
    print("=" * 60)
    
    try:
        router_file = SERVICES_ROOT / "app" / "routers" / "encounters_risk.py"
        if router_file.exists():
            router_code = router_file.read_text()
            
            # Check allowed roles
            check("RBAC", "_ALLOWED_ROLES defined",
                  "_ALLOWED_ROLES" in router_code)
            check("RBAC", "admin role allowed",
                  '"admin"' in router_code)
            check("RBAC", "physician role allowed",
                  '"physician"' in router_code)
            check("RBAC", "nurse role allowed",
                  '"nurse"' in router_code)
            
            # Check role enforcement
            check("RBAC", "Role check in endpoint",
                  "current_user.role" in router_code)
            check("RBAC", "Unit-scoped access check",
                  "encounter.unit" in router_code)
            check("RBAC", "403 for unauthorized access",
                  "403" in router_code or "HTTP_403_FORBIDDEN" in router_code)
        
        return True
    except Exception as e:
        check("RBAC", "RBAC validation failed", False, str(e))
        return False


def validate_main_registration() -> bool:
    """Validate router registration in main.py."""
    print("\n4. MAIN.PY ROUTER REGISTRATION")
    print("=" * 60)
    
    try:
        main_file = SERVICES_ROOT / "main.py"
        check("Main Registration", "main.py exists", main_file.exists())
        
        if main_file.exists():
            main_code = main_file.read_text()
            
            # Check import
            check("Main Registration", "encounters_risk router imported",
                  "from app.routers.encounters_risk import router as encounters_risk_router" in main_code)
            
            # Check registration
            check("Main Registration", "Router registered with app",
                  "app.include_router(encounters_risk_router" in main_code)
            check("Main Registration", "Prefix /api/v1",
                  'prefix="/api/v1"' in main_code)
        
        return True
    except Exception as e:
        check("Main Registration", "Main registration validation failed", False, str(e))
        return False


def validate_agent_json_update() -> bool:
    """Validate agent.py uses JSON for output_summary."""
    print("\n5. AGENT.PY JSON OUTPUT")
    print("=" * 60)
    
    try:
        agent_file = BACKEND_ROOT / "app" / "agents" / "followup_care" / "agent.py"
        check("Agent JSON", "agent.py exists", agent_file.exists())
        
        if agent_file.exists():
            agent_code = agent_file.read_text()
            
            # Check JSON import
            check("Agent JSON", "json module imported",
                  "import json" in agent_code)
            
            # Check _create_agent_task signature updated
            check("Agent JSON", "_create_agent_task has contributing_factors param",
                  "contributing_factors" in agent_code)
            
            # Check JSON serialization
            check("Agent JSON", "json.dumps() used for output_summary",
                  "json.dumps(" in agent_code)
            check("Agent JSON", "risk_tier in JSON",
                  '"risk_tier"' in agent_code)
            check("Agent JSON", "model_version in JSON",
                  '"model_version"' in agent_code)
            check("Agent JSON", "contributing_factors in JSON",
                  '"contributing_factors": contributing_factors' in agent_code)
            
            # Check method call updated
            check("Agent JSON", "_create_agent_task call includes contributing_factors",
                  "contributing_factors=contributing_factors" in agent_code)
        
        return True
    except Exception as e:
        check("Agent JSON", "Agent JSON validation failed", False, str(e))
        return False


def validate_response_structure() -> bool:
    """Validate response structure matches spec."""
    print("\n6. RESPONSE STRUCTURE")
    print("=" * 60)
    
    try:
        schema_file = SERVICES_ROOT / "app" / "schemas" / "risk.py"
        if schema_file.exists():
            schema_code = schema_file.read_text()
            
            # Check field types
            check("Response Structure", "encounter_id is str",
                  "encounter_id: str" in schema_code)
            check("Response Structure", "risk_score is Optional[float]",
                  "risk_score: float | None" in schema_code or "Optional[float]" in schema_code)
            check("Response Structure", "risk_tier defaults to UNKNOWN",
                  "RiskTier.UNKNOWN" in schema_code)
            check("Response Structure", "contributing_factors is list",
                  "list[ContributingFactor]" in schema_code)
            check("Response Structure", "model_version is Optional[str]",
                  "model_version: str | None" in schema_code or "Optional[str]" in schema_code)
            check("Response Structure", "assessed_at is Optional[str]",
                  "assessed_at: str | None" in schema_code or "Optional[str]" in schema_code)
        
        return True
    except Exception as e:
        check("Response Structure", "Response structure validation failed", False, str(e))
        return False


def validate_error_handling() -> bool:
    """Validate comprehensive error handling."""
    print("\n7. ERROR HANDLING")
    print("=" * 60)
    
    try:
        router_file = SERVICES_ROOT / "app" / "routers" / "encounters_risk.py"
        if router_file.exists():
            router_code = router_file.read_text()
            
            # Check error scenarios
            check("Error Handling", "Invalid UUID error (400)",
                  "Invalid encounter ID format" in router_code)
            check("Error Handling", "Encounter not found error (404)",
                  "Encounter not found" in router_code)
            check("Error Handling", "Access denied error (403)",
                  "Access denied" in router_code)
            check("Error Handling", "Try-except for JSON parsing",
                  "try:" in router_code and "json.loads" in router_code)
            check("Error Handling", "Logging on JSON parse failure",
                  "logger.warning" in router_code)
            check("Error Handling", "Graceful fallback for missing AgentTask",
                  "contributing_factors: list[ContributingFactor] = []" in router_code or "contributing_factors = []" in router_code)
        
        return True
    except Exception as e:
        check("Error Handling", "Error handling validation failed", False, str(e))
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
    print("US-039 TASK-005 VALIDATION")
    print("GET /api/v1/encounters/{id}/risk Endpoint")
    print("=" * 60)
    
    validate_schema_files()
    validate_router_implementation()
    validate_rbac_enforcement()
    validate_main_registration()
    validate_agent_json_update()
    validate_response_structure()
    validate_error_handling()
    
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
