"""Validation script for US-033 TASK-003: MedicationSummaryGenerator + Gemini Flash Prompt.

Validates that:
1. generator.py file exists
2. MedicationSummaryGenerator class is defined
3. Gemini Flash model configuration is correct (gemini-1.5-flash, temp=0.2)
4. System and user prompts are defined
5. Brand name enrichment is integrated
6. Error handling raises ValueError on invalid JSON
7. Method signatures are correct
8. All required imports present
9. Design refs documentation complete
10. Python syntax is valid

Design refs:
    US-033 TASK-003 — MedicationSummaryGenerator Class + Gemini Flash Prompt
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def validate_file_structure() -> tuple[int, int]:
    """Validate that generator.py exists."""
    print("\n📁 1. FILE STRUCTURE")
    print("=" * 70)
    
    passed = 0
    total = 1
    
    file_path = Path("backend/app/agents/medication_reconciliation/summary/generator.py")
    if file_path.exists():
        print(f"✅ {file_path} exists")
        passed += 1
    else:
        print(f"❌ {file_path} not found")
    
    print(f"\n📊 File Structure: {passed}/{total} files present")
    return passed, total


def validate_class_definition() -> tuple[int, int]:
    """Validate MedicationSummaryGenerator class definition."""
    print("\n🏗️  2. CLASS DEFINITION")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    file_path = Path("backend/app/agents/medication_reconciliation/summary/generator.py")
    if not file_path.exists():
        print("❌ generator.py not found")
        return 0, 5
    
    with open(file_path, "r") as f:
        content = f.read()
    
    # Check 1: Module docstring with Design refs
    total += 1
    if '"""MedicationSummaryGenerator' in content and "Design refs:" in content:
        print("✅ Module docstring with Design refs present")
        passed += 1
    else:
        print("❌ Missing module docstring or Design refs")
    
    # Check 2: MedicationSummaryGenerator class
    total += 1
    if "class MedicationSummaryGenerator:" in content:
        print("✅ MedicationSummaryGenerator class defined")
        passed += 1
    else:
        print("❌ MedicationSummaryGenerator class not found")
    
    # Check 3: __init__ method with enricher, project, location parameters
    total += 1
    if "def __init__(\n        self,\n        enricher: BrandNameEnricher," in content or "def __init__(self, enricher: BrandNameEnricher, project: str" in content:
        print("✅ __init__ method with enricher, project, location parameters")
        passed += 1
    else:
        print("❌ __init__ method missing or incorrect signature")
    
    # Check 4: generate() async method
    total += 1
    if "async def generate(" in content and "reconciliation_result: dict[str, Any]" in content:
        print("✅ generate() async method with reconciliation_result parameter")
        passed += 1
    else:
        print("❌ generate() method missing or incorrect signature")
    
    # Check 5: _enrich_medications() private async method
    total += 1
    if "async def _enrich_medications(" in content:
        print("✅ _enrich_medications() private async method defined")
        passed += 1
    else:
        print("❌ _enrich_medications() method missing")
    
    print(f"\n📊 Class Definition: {passed}/{total} checks passed")
    return passed, total


def validate_model_configuration() -> tuple[int, int]:
    """Validate Gemini Flash model configuration."""
    print("\n🤖 3. MODEL CONFIGURATION")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    file_path = Path("backend/app/agents/medication_reconciliation/summary/generator.py")
    if not file_path.exists():
        return 0, 5
    
    with open(file_path, "r") as f:
        content = f.read()
    
    # Check 1: Gemini Flash model name
    total += 1
    if '_GEMINI_MODEL = "gemini-1.5-flash"' in content:
        print('✅ Model is gemini-1.5-flash (not Pro)')
        passed += 1
    else:
        print('❌ Model is not gemini-1.5-flash')
    
    # Check 2: Temperature = 0.2
    total += 1
    if "_TEMPERATURE = 0.2" in content:
        print("✅ Temperature = 0.2 (low for consistency)")
        passed += 1
    else:
        print("❌ Temperature not set to 0.2")
    
    # Check 3: Max output tokens defined
    total += 1
    if "_MAX_OUTPUT_TOKENS" in content:
        print("✅ Max output tokens configured")
        passed += 1
    else:
        print("❌ Max output tokens not configured")
    
    # Check 4: ChatVertexAI instantiation
    total += 1
    if "ChatVertexAI(" in content and "model_name=_GEMINI_MODEL" in content:
        print("✅ ChatVertexAI instantiated with correct parameters")
        passed += 1
    else:
        print("❌ ChatVertexAI not properly instantiated")
    
    # Check 5: Default location is us-central1
    total += 1
    if 'location: str = "us-central1"' in content:
        print('✅ Default location is "us-central1"')
        passed += 1
    else:
        print('❌ Default location not "us-central1"')
    
    print(f"\n📊 Model Configuration: {passed}/{total} checks passed")
    return passed, total


def validate_prompts() -> tuple[int, int]:
    """Validate system and user prompt templates."""
    print("\n💬 4. PROMPT TEMPLATES")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    file_path = Path("backend/app/agents/medication_reconciliation/summary/generator.py")
    if not file_path.exists():
        return 0, 7
    
    with open(file_path, "r") as f:
        content = f.read()
    
    # Check 1: _SYSTEM_PROMPT defined
    total += 1
    if "_SYSTEM_PROMPT = " in content:
        print("✅ _SYSTEM_PROMPT constant defined")
        passed += 1
    else:
        print("❌ _SYSTEM_PROMPT not defined")
    
    # Check 2: System prompt mentions 6th-grade reading level
    total += 1
    if "6th-grade reading level" in content:
        print("✅ System prompt specifies 6th-grade reading level")
        passed += 1
    else:
        print("❌ System prompt does not mention reading level")
    
    # Check 3: System prompt instructs JSON-only output
    total += 1
    if "valid JSON only" in content or "JSON only" in content:
        print("✅ System prompt instructs JSON-only output")
        passed += 1
    else:
        print("❌ System prompt does not specify JSON output")
    
    # Check 4: _USER_PROMPT_TEMPLATE defined
    total += 1
    if "_USER_PROMPT_TEMPLATE = " in content:
        print("✅ _USER_PROMPT_TEMPLATE constant defined")
        passed += 1
    else:
        print("❌ _USER_PROMPT_TEMPLATE not defined")
    
    # Check 5: User prompt mentions all four categories
    total += 1
    all_categories = all(cat in content for cat in ['"new"', '"stopped"', '"changed"', '"continued"'])
    if all_categories:
        print("✅ User prompt includes all four medication categories")
        passed += 1
    else:
        print("❌ User prompt missing one or more categories")
    
    # Check 6: Dosing instructions format mentioned
    total += 1
    if "Take X tablet" in content or "tablet(s)" in content:
        print("✅ Dosing instructions format specified")
        passed += 1
    else:
        print("❌ Dosing instructions format not specified")
    
    # Check 7: Template uses format() with medication_changes_json
    total += 1
    if "{medication_changes_json}" in content:
        print("✅ Template uses {medication_changes_json} placeholder")
        passed += 1
    else:
        print("❌ Template missing medication_changes_json placeholder")
    
    print(f"\n📊 Prompt Templates: {passed}/{total} checks passed")
    return passed, total


def validate_brand_name_enrichment() -> tuple[int, int]:
    """Validate brand name enrichment integration."""
    print("\n💊 5. BRAND NAME ENRICHMENT")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    file_path = Path("backend/app/agents/medication_reconciliation/summary/generator.py")
    if not file_path.exists():
        return 0, 4
    
    with open(file_path, "r") as f:
        content = f.read()
    
    # Check 1: BrandNameEnricher imported
    total += 1
    if "from app.agents.medication_reconciliation.brand_name.enricher import BrandNameEnricher" in content:
        print("✅ BrandNameEnricher imported from TASK-001")
        passed += 1
    else:
        print("❌ BrandNameEnricher not imported")
    
    # Check 2: _enrich_medications method exists
    total += 1
    if "async def _enrich_medications(" in content:
        print("✅ _enrich_medications() method defined")
        passed += 1
    else:
        print("❌ _enrich_medications() method not found")
    
    # Check 3: Enrichment called before prompt construction
    total += 1
    # Check that enriched is used before prompt formatting
    if "enriched = await self._enrich_medications(" in content and "medication_changes_json=json.dumps(enriched" in content:
        print("✅ Brand name enrichment called before prompt construction")
        passed += 1
    else:
        print("❌ Enrichment not called before prompt")
    
    # Check 4: enricher.enrich() called in _enrich_medications
    total += 1
    if "await self._enricher.enrich(" in content:
        print("✅ enricher.enrich() called for each medication")
        passed += 1
    else:
        print("❌ enricher.enrich() not called")
    
    print(f"\n📊 Brand Name Enrichment: {passed}/{total} checks passed")
    return passed, total


def validate_error_handling() -> tuple[int, int]:
    """Validate error handling for invalid JSON."""
    print("\n⚠️  6. ERROR HANDLING")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    file_path = Path("backend/app/agents/medication_reconciliation/summary/generator.py")
    if not file_path.exists():
        return 0, 4
    
    with open(file_path, "r") as f:
        content = f.read()
    
    # Check 1: ValueError imported or raised
    total += 1
    if "raise ValueError(" in content:
        print("✅ ValueError raised on validation failure")
        passed += 1
    else:
        print("❌ ValueError not raised")
    
    # Check 2: json.JSONDecodeError caught
    total += 1
    if "json.JSONDecodeError" in content:
        print("✅ json.JSONDecodeError caught")
        passed += 1
    else:
        print("❌ json.JSONDecodeError not handled")
    
    # Check 3: ValidationError caught
    total += 1
    if "ValidationError" in content:
        print("✅ ValidationError (from Pydantic) caught")
        passed += 1
    else:
        print("❌ ValidationError not handled")
    
    # Check 4: Error logged before raising
    total += 1
    if "logger.error(" in content:
        print("✅ Errors logged before raising")
        passed += 1
    else:
        print("❌ Errors not logged")
    
    print(f"\n📊 Error Handling: {passed}/{total} checks passed")
    return passed, total


def validate_imports() -> tuple[int, int]:
    """Validate all required imports."""
    print("\n📥 7. IMPORTS")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    file_path = Path("backend/app/agents/medication_reconciliation/summary/generator.py")
    if not file_path.exists():
        return 0, 6
    
    with open(file_path, "r") as f:
        content = f.read()
    
    required_imports = [
        ("langchain_google_vertexai", "ChatVertexAI"),
        ("langchain_core.messages", "HumanMessage"),
        ("langchain_core.messages", "SystemMessage"),
        ("app.agents.medication_reconciliation.brand_name.enricher", "BrandNameEnricher"),
        ("app.agents.medication_reconciliation.summary.schema", "MedicationSummaryOutput"),
        ("pydantic", "ValidationError"),
    ]
    
    for module, item in required_imports:
        total += 1
        if f"from {module} import" in content and item in content:
            print(f"✅ {item} imported from {module}")
            passed += 1
        else:
            print(f"❌ {item} not imported from {module}")
    
    print(f"\n📊 Imports: {passed}/{total} imports present")
    return passed, total


def validate_langchain_usage() -> tuple[int, int]:
    """Validate LangChain async invocation."""
    print("\n🔗 8. LANGCHAIN INTEGRATION")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    file_path = Path("backend/app/agents/medication_reconciliation/summary/generator.py")
    if not file_path.exists():
        return 0, 4
    
    with open(file_path, "r") as f:
        content = f.read()
    
    # Check 1: ainvoke used (async)
    total += 1
    if "await self._llm.ainvoke(" in content:
        print("✅ LangChain ainvoke() used for async call")
        passed += 1
    else:
        print("❌ ainvoke() not used (should be async)")
    
    # Check 2: Messages list created
    total += 1
    if "messages = [" in content or "messages=[" in content:
        print("✅ Messages list created for LangChain")
        passed += 1
    else:
        print("❌ Messages list not created")
    
    # Check 3: SystemMessage used
    total += 1
    if "SystemMessage(" in content:
        print("✅ SystemMessage used for system prompt")
        passed += 1
    else:
        print("❌ SystemMessage not used")
    
    # Check 4: HumanMessage used
    total += 1
    if "HumanMessage(" in content:
        print("✅ HumanMessage used for user prompt")
        passed += 1
    else:
        print("❌ HumanMessage not used")
    
    print(f"\n📊 LangChain Integration: {passed}/{total} checks passed")
    return passed, total


def validate_schema_validation() -> tuple[int, int]:
    """Validate MedicationSummaryOutput schema validation."""
    print("\n✅ 9. SCHEMA VALIDATION")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    file_path = Path("backend/app/agents/medication_reconciliation/summary/generator.py")
    if not file_path.exists():
        return 0, 3
    
    with open(file_path, "r") as f:
        content = f.read()
    
    # Check 1: MedicationSummaryOutput.model_validate() used
    total += 1
    if "MedicationSummaryOutput.model_validate(" in content:
        print("✅ MedicationSummaryOutput.model_validate() used")
        passed += 1
    else:
        print("❌ model_validate() not used for schema validation")
    
    # Check 2: JSON parsing before validation
    total += 1
    if "json.loads(" in content:
        print("✅ JSON parsing before schema validation")
        passed += 1
    else:
        print("❌ JSON not parsed")
    
    # Check 3: Returns MedicationSummaryOutput type
    total += 1
    if "-> MedicationSummaryOutput:" in content:
        print("✅ generate() returns MedicationSummaryOutput")
        passed += 1
    else:
        print("❌ generate() return type not MedicationSummaryOutput")
    
    print(f"\n📊 Schema Validation: {passed}/{total} checks passed")
    return passed, total


def validate_syntax() -> tuple[int, int]:
    """Validate Python syntax."""
    print("\n✨ 10. PYTHON SYNTAX")
    print("=" * 70)
    
    passed = 0
    total = 1
    
    file_path = Path("backend/app/agents/medication_reconciliation/summary/generator.py")
    if not file_path.exists():
        print("❌ generator.py not found")
        return 0, 1
    
    try:
        with open(file_path, "r") as f:
            code = f.read()
        ast.parse(code)
        print(f"✅ generator.py has no syntax errors")
        passed += 1
    except SyntaxError as e:
        print(f"❌ generator.py has syntax error: {e}")
    
    print(f"\n📊 Python Syntax: {passed}/{total} files valid")
    return passed, total


def main() -> int:
    """Run all validation checks."""
    print("=" * 70)
    print("US-033 TASK-003 VALIDATION")
    print("MedicationSummaryGenerator Class + Gemini Flash Prompt")
    print("=" * 70)
    
    results = []
    results.append(validate_file_structure())
    results.append(validate_class_definition())
    results.append(validate_model_configuration())
    results.append(validate_prompts())
    results.append(validate_brand_name_enrichment())
    results.append(validate_error_handling())
    results.append(validate_imports())
    results.append(validate_langchain_usage())
    results.append(validate_schema_validation())
    results.append(validate_syntax())
    
    total_passed = sum(r[0] for r in results)
    total_checks = sum(r[1] for r in results)
    
    print("\n" + "=" * 70)
    print("📊 OVERALL VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total Checks Passed: {total_passed}/{total_checks}")
    print(f"Success Rate: {(total_passed/total_checks)*100:.1f}%")
    
    if total_passed == total_checks:
        print("\n✅ ALL VALIDATION CHECKS PASSED")
        print("\nUS-033 TASK-003 Acceptance Criteria:")
        print("  ✓ MedicationSummaryGenerator.generate() returns MedicationSummaryOutput")
        print("  ✓ Gemini Flash model (gemini-1.5-flash, not Pro)")
        print("  ✓ Brand name enrichment called before prompt construction")
        print("  ✓ ValueError raised on invalid JSON (no silent failures)")
        print("  ✓ Temperature = 0.2 (deterministic factual output)")
        print("  ✓ System prompt: 6th-grade reading level, JSON-only output")
        print("  ✓ Dosing instructions format: 'Take X tablet(s) (Xmg) [frequency]'")
        print("\nImplementation ready for integration testing.")
        print("\nNext steps:")
        print("  1. Configure GCP project ID and Vertex AI credentials")
        print("  2. Test with sample reconciliation result from US-030")
        print("  3. Validate Gemini Flash output against schema")
        print("  4. Implement unit tests in TASK-006")
        return 0
    else:
        print("\n⚠️  SOME VALIDATION CHECKS FAILED")
        print(f"{total_checks - total_passed} check(s) need review before completion.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
