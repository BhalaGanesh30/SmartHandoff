"""Validation script for US-040 TASK-002: Care Pathways Configuration.

Validates:
    1. care_pathways.yaml structure and content
    2. TierPathwayConfig Pydantic model validation
    3. All required risk tiers present (HIGH, MEDIUM, LOW)
    4. Correct followup_days, appointment_type, alert_care_manager per tier
    5. load_care_pathways() function correctness

US-040 TASK-002 — config/care_pathways.yaml & Pydantic Config Model
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


def validate_yaml_file() -> bool:
    """Validate care_pathways.yaml file structure."""
    print("\n1. YAML FILE STRUCTURE")
    print("=" * 60)
    
    try:
        yaml_file = BACKEND_ROOT / "config" / "care_pathways.yaml"
        
        check("YAML", "care_pathways.yaml exists", yaml_file.exists())
        
        if not yaml_file.exists():
            check("YAML", "YAML file validation failed", False, "File not found")
            return False
        
        # Read YAML manually to validate structure before Pydantic
        import yaml
        with yaml_file.open() as f:
            raw = yaml.safe_load(f)
        
        check("YAML", "YAML parses successfully", isinstance(raw, dict))
        check("YAML", "care_pathways key exists", "care_pathways" in raw)
        
        if "care_pathways" in raw:
            pathways = raw["care_pathways"]
            
            # Check all required tiers
            check("YAML", "HIGH tier defined", "HIGH" in pathways)
            check("YAML", "MEDIUM tier defined", "MEDIUM" in pathways)
            check("YAML", "LOW tier defined", "LOW" in pathways)
            
            # Validate HIGH tier
            if "HIGH" in pathways:
                high = pathways["HIGH"]
                check("YAML", "HIGH.followup_days = 7", high.get("followup_days") == 7)
                check("YAML", "HIGH.appointment_type = HIGH_RISK_FOLLOW_UP", 
                      high.get("appointment_type") == "HIGH_RISK_FOLLOW_UP")
                check("YAML", "HIGH.alert_care_manager = true", high.get("alert_care_manager") is True)
                check("YAML", "HIGH.required_followup_days = 7", high.get("required_followup_days") == 7)
            
            # Validate MEDIUM tier
            if "MEDIUM" in pathways:
                medium = pathways["MEDIUM"]
                check("YAML", "MEDIUM.followup_days = 14", medium.get("followup_days") == 14)
                check("YAML", "MEDIUM.appointment_type = STANDARD_FOLLOW_UP", 
                      medium.get("appointment_type") == "STANDARD_FOLLOW_UP")
                check("YAML", "MEDIUM.alert_care_manager = false", medium.get("alert_care_manager") is False)
                check("YAML", "MEDIUM.required_followup_days = null", medium.get("required_followup_days") is None)
            
            # Validate LOW tier
            if "LOW" in pathways:
                low = pathways["LOW"]
                check("YAML", "LOW.followup_days = 30", low.get("followup_days") == 30)
                check("YAML", "LOW.appointment_type = ROUTINE_FOLLOW_UP", 
                      low.get("appointment_type") == "ROUTINE_FOLLOW_UP")
                check("YAML", "LOW.alert_care_manager = false", low.get("alert_care_manager") is False)
                check("YAML", "LOW.required_followup_days = null", low.get("required_followup_days") is None)
        
        return True
    except Exception as e:
        check("YAML", "YAML validation failed", False, str(e))
        return False


def validate_pydantic_model() -> bool:
    """Validate Pydantic model structure."""
    print("\n2. PYDANTIC MODEL")
    print("=" * 60)
    
    try:
        config_file = BACKEND_ROOT / "app" / "config" / "care_pathways.py"
        
        check("Model", "care_pathways.py exists", config_file.exists())
        
        if not config_file.exists():
            check("Model", "Model validation failed", False, "File not found")
            return False
        
        code = config_file.read_text(encoding="utf-8")
        
        # Check imports
        check("Model", "from __future__ import annotations", "from __future__ import annotations" in code)
        check("Model", "Imports yaml", "import yaml" in code)
        check("Model", "Imports Pydantic", "from pydantic import" in code)
        check("Model", "Imports BaseModel", "BaseModel" in code)
        
        # Check class definitions
        check("Model", "TierPathwayConfig class defined", "class TierPathwayConfig(BaseModel):" in code)
        check("Model", "CarePathwayConfig type alias", "CarePathwayConfig = dict[str, TierPathwayConfig]" in code)
        
        # Check TierPathwayConfig fields
        check("Model", "followup_days field", "followup_days: int" in code)
        check("Model", "appointment_type field", "appointment_type: str" in code)
        check("Model", "alert_care_manager field", "alert_care_manager: bool" in code)
        check("Model", "required_followup_days field", "required_followup_days: int | None" in code)
        
        # Check validation constraints
        check("Model", "followup_days > 0 constraint", "gt=0" in code)
        
        # Check load function
        check("Model", "load_care_pathways() function", "def load_care_pathways(" in code)
        check("Model", "@lru_cache decorator", "@lru_cache" in code)
        
        return True
    except Exception as e:
        check("Model", "Model validation failed", False, str(e))
        return False


def validate_config_loading() -> bool:
    """Validate configuration loading functionality."""
    print("\n3. CONFIGURATION LOADING")
    print("=" * 60)
    
    try:
        # Import the config loader
        from app.config.care_pathways import load_care_pathways, TierPathwayConfig
        
        check("Loading", "load_care_pathways imported successfully", True)
        check("Loading", "TierPathwayConfig imported successfully", True)
        
        # Load the configuration
        pathways = load_care_pathways()
        
        check("Loading", "load_care_pathways() returns dict", isinstance(pathways, dict))
        check("Loading", "Contains HIGH tier", "HIGH" in pathways)
        check("Loading", "Contains MEDIUM tier", "MEDIUM" in pathways)
        check("Loading", "Contains LOW tier", "LOW" in pathways)
        
        # Validate HIGH tier
        if "HIGH" in pathways:
            high = pathways["HIGH"]
            check("Loading", "HIGH is TierPathwayConfig", isinstance(high, TierPathwayConfig))
            check("Loading", "HIGH.followup_days == 7", high.followup_days == 7)
            check("Loading", "HIGH.appointment_type == 'HIGH_RISK_FOLLOW_UP'", 
                  high.appointment_type == "HIGH_RISK_FOLLOW_UP")
            check("Loading", "HIGH.alert_care_manager == True", high.alert_care_manager is True)
            check("Loading", "HIGH.required_followup_days == 7", high.required_followup_days == 7)
        
        # Validate MEDIUM tier
        if "MEDIUM" in pathways:
            medium = pathways["MEDIUM"]
            check("Loading", "MEDIUM is TierPathwayConfig", isinstance(medium, TierPathwayConfig))
            check("Loading", "MEDIUM.followup_days == 14", medium.followup_days == 14)
            check("Loading", "MEDIUM.appointment_type == 'STANDARD_FOLLOW_UP'", 
                  medium.appointment_type == "STANDARD_FOLLOW_UP")
            check("Loading", "MEDIUM.alert_care_manager == False", medium.alert_care_manager is False)
            check("Loading", "MEDIUM.required_followup_days is None", medium.required_followup_days is None)
        
        # Validate LOW tier
        if "LOW" in pathways:
            low = pathways["LOW"]
            check("Loading", "LOW is TierPathwayConfig", isinstance(low, TierPathwayConfig))
            check("Loading", "LOW.followup_days == 30", low.followup_days == 30)
            check("Loading", "LOW.appointment_type == 'ROUTINE_FOLLOW_UP'", 
                  low.appointment_type == "ROUTINE_FOLLOW_UP")
            check("Loading", "LOW.alert_care_manager == False", low.alert_care_manager is False)
            check("Loading", "LOW.required_followup_days is None", low.required_followup_days is None)
        
        return True
    except Exception as e:
        check("Loading", "Configuration loading failed", False, str(e))
        return False


def validate_acceptance_criteria() -> bool:
    """Validate US-040 Acceptance Criteria compliance."""
    print("\n4. ACCEPTANCE CRITERIA")
    print("=" * 60)
    
    try:
        from app.config.care_pathways import load_care_pathways
        
        pathways = load_care_pathways()
        
        # AC Scenario 2: HIGH tier
        check("AC", "Scenario 2: HIGH.followup_days = 7", pathways["HIGH"].followup_days == 7)
        check("AC", "Scenario 2: HIGH.appointment_type = HIGH_RISK_FOLLOW_UP", 
              pathways["HIGH"].appointment_type == "HIGH_RISK_FOLLOW_UP")
        check("AC", "Scenario 2: HIGH.alert_care_manager = true", pathways["HIGH"].alert_care_manager is True)
        check("AC", "Scenario 2: HIGH.required_followup_days = 7", pathways["HIGH"].required_followup_days == 7)
        
        # AC Scenario 3: MEDIUM tier
        check("AC", "Scenario 3: MEDIUM.followup_days = 14", pathways["MEDIUM"].followup_days == 14)
        check("AC", "Scenario 3: MEDIUM.appointment_type = STANDARD_FOLLOW_UP", 
              pathways["MEDIUM"].appointment_type == "STANDARD_FOLLOW_UP")
        check("AC", "Scenario 3: MEDIUM.alert_care_manager = false", pathways["MEDIUM"].alert_care_manager is False)
        
        # AC Scenario 4: LOW tier
        check("AC", "Scenario 4: LOW.followup_days = 30", pathways["LOW"].followup_days == 30)
        check("AC", "Scenario 4: LOW.appointment_type = ROUTINE_FOLLOW_UP", 
              pathways["LOW"].appointment_type == "ROUTINE_FOLLOW_UP")
        check("AC", "Scenario 4: LOW.alert_care_manager = false", pathways["LOW"].alert_care_manager is False)
        
        return True
    except Exception as e:
        check("AC", "Acceptance criteria validation failed", False, str(e))
        return False


def validate_dod_criteria() -> bool:
    """Validate Definition of Done criteria."""
    print("\n5. DEFINITION OF DONE")
    print("=" * 60)
    
    try:
        # Check all files created
        files_required = [
            BACKEND_ROOT / "config" / "care_pathways.yaml",
            BACKEND_ROOT / "app" / "config" / "care_pathways.py",
        ]
        
        all_files_exist = all(f.exists() for f in files_required)
        check("DoD", "All required files created", all_files_exist,
              f"{sum(f.exists() for f in files_required)}/{len(files_required)} files found")
        
        # Check YAML has all 3 tiers
        yaml_file = BACKEND_ROOT / "config" / "care_pathways.yaml"
        if yaml_file.exists():
            import yaml
            with yaml_file.open() as f:
                raw = yaml.safe_load(f)
            check("DoD", "YAML has all 3 risk tiers", 
                  all(tier in raw.get("care_pathways", {}) for tier in ["HIGH", "MEDIUM", "LOW"]))
        
        # Check Pydantic model components
        config_file = BACKEND_ROOT / "app" / "config" / "care_pathways.py"
        if config_file.exists():
            code = config_file.read_text(encoding="utf-8")
            check("DoD", "TierPathwayConfig class defined", "class TierPathwayConfig(BaseModel):" in code)
            check("DoD", "CarePathwayConfig type alias defined", "CarePathwayConfig" in code)
            check("DoD", "load_care_pathways() function defined", "def load_care_pathways(" in code)
        
        # Check co-location with application config
        check("DoD", "Config file co-located in backend/config", 
              (BACKEND_ROOT / "config" / "care_pathways.yaml").exists())
        check("DoD", "Pydantic model co-located in app/config", 
              (BACKEND_ROOT / "app" / "config" / "care_pathways.py").exists())
        
        return True
    except Exception as e:
        check("DoD", "DoD validation failed", False, str(e))
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
        print("\nConfiguration is ready for use by FollowUpCareAgent")
        return True
    else:
        print("❌ SOME VALIDATIONS FAILED")
        return False


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("US-040 TASK-002 VALIDATION")
    print("Care Pathways Configuration & Pydantic Config Model")
    print("=" * 60)
    
    validate_yaml_file()
    validate_pydantic_model()
    validate_config_loading()
    validate_acceptance_criteria()
    validate_dod_criteria()
    
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
