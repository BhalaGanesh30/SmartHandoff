"""
Validation script for TASK-026-001: CompletenessConfig implementation.
Tests all Definition of Done criteria.
"""
import os
import sys
import tempfile
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

print()
print("=" * 80)
print("TASK-026-001: CompletenessConfig Validation")
print("=" * 80)
print()

# Test 1: YAML file contains five required fields for discharge_summary
print("Test 1: YAML file structure and required fields")
print("-" * 80)
try:
    import yaml
    yaml_path = Path(__file__).parent / "config" / "document_completeness.yaml"
    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    discharge_fields = config["document_types"]["discharge_summary"]["required_fields"]
    expected_fields = [
        "diagnosis_summary",
        "medications_at_discharge",
        "follow_up_instructions",
        "warning_signs",
        "activity_restrictions"
    ]
    
    assert len(discharge_fields) == 5, f"Expected 5 fields, got {len(discharge_fields)}"
    assert set(discharge_fields) == set(expected_fields), f"Field mismatch: {discharge_fields}"
    print(f"✓ YAML contains 5 required fields: {discharge_fields}")
except Exception as e:
    print(f"✗ YAML validation failed: {e}")
    sys.exit(1)

print()

# Test 2: CompletenessConfig._load() parses YAML without error
print("Test 2: CompletenessConfig._load() parses YAML successfully")
print("-" * 80)
try:
    from config.completeness_config import CompletenessConfig
    
    config = CompletenessConfig()
    assert hasattr(config, "_rules"), "Missing _rules attribute"
    assert isinstance(config._rules, dict), "_rules is not a dict"
    assert "discharge_summary" in config._rules, "discharge_summary not in _rules"
    print("✓ CompletenessConfig._load() parsed YAML and populated _rules dict")
except Exception as e:
    print(f"✗ Config loading failed: {e}")
    sys.exit(1)

print()

# Test 3: get_required_fields("discharge_summary") returns 5-item list
print("Test 3: get_required_fields() returns correct field list")
print("-" * 80)
try:
    fields = config.get_required_fields("discharge_summary")
    assert isinstance(fields, list), f"Expected list, got {type(fields)}"
    assert len(fields) == 5, f"Expected 5 fields, got {len(fields)}"
    assert set(fields) == set(expected_fields), f"Field mismatch: {fields}"
    print(f"✓ get_required_fields('discharge_summary') returns: {fields}")
except Exception as e:
    print(f"✗ get_required_fields failed: {e}")
    sys.exit(1)

print()

# Test 4: get_required_fields("unknown_type") returns [] without raising
print("Test 4: get_required_fields() handles unknown document types")
print("-" * 80)
try:
    unknown_fields = config.get_required_fields("unknown_type")
    assert unknown_fields == [], f"Expected [], got {unknown_fields}"
    print("✓ get_required_fields('unknown_type') returns [] without raising")
except Exception as e:
    print(f"✗ Unknown type handling failed: {e}")
    sys.exit(1)

print()

# Test 5: get_completeness_config() returns cached singleton
print("Test 5: get_completeness_config() singleton caching")
print("-" * 80)
try:
    from config.completeness_config import get_completeness_config
    
    # Clear cache to ensure fresh start
    get_completeness_config.cache_clear()
    
    instance1 = get_completeness_config()
    instance2 = get_completeness_config()
    
    assert instance1 is instance2, "Instances are not the same object"
    print("✓ get_completeness_config() returns the same cached instance")
except Exception as e:
    print(f"✗ Singleton caching failed: {e}")
    sys.exit(1)

print()

# Test 6: COMPLETENESS_CONFIG_PATH env-var override works
print("Test 6: COMPLETENESS_CONFIG_PATH environment variable override")
print("-" * 80)
try:
    # Create a temporary YAML file with different content
    temp_yaml_content = """
document_types:
  test_document:
    required_fields:
      - test_field_1
      - test_field_2
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as temp_file:
        temp_file.write(temp_yaml_content)
        temp_path = temp_file.name
    
    try:
        # Clear cache and set env var
        get_completeness_config.cache_clear()
        os.environ["COMPLETENESS_CONFIG_PATH"] = temp_path
        
        # Get new config with override
        test_config = get_completeness_config()
        test_fields = test_config.get_required_fields("test_document")
        
        assert len(test_fields) == 2, f"Expected 2 fields, got {len(test_fields)}"
        assert "test_field_1" in test_fields, "test_field_1 not found"
        assert "test_field_2" in test_fields, "test_field_2 not found"
        
        print(f"✓ COMPLETENESS_CONFIG_PATH override works: {test_fields}")
    finally:
        # Clean up
        del os.environ["COMPLETENESS_CONFIG_PATH"]
        Path(temp_path).unlink()
        get_completeness_config.cache_clear()
except Exception as e:
    print(f"✗ Environment variable override failed: {e}")
    # Clean up on error
    if "COMPLETENESS_CONFIG_PATH" in os.environ:
        del os.environ["COMPLETENESS_CONFIG_PATH"]
    if 'temp_path' in locals():
        Path(temp_path).unlink(missing_ok=True)
    sys.exit(1)

print()

# Test 7: configured_document_types property
print("Test 7: configured_document_types property")
print("-" * 80)
try:
    final_config = get_completeness_config()
    doc_types = final_config.configured_document_types
    
    assert isinstance(doc_types, list), f"Expected list, got {type(doc_types)}"
    assert "discharge_summary" in doc_types, "discharge_summary not in configured types"
    print(f"✓ configured_document_types returns: {doc_types}")
except Exception as e:
    print(f"✗ configured_document_types failed: {e}")
    sys.exit(1)

print()
print("=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)
print()

validation_items = [
    "✓ config/document_completeness.yaml contains 5 required fields",
    "✓ CompletenessConfig._load() parses YAML successfully",
    "✓ get_required_fields('discharge_summary') returns 5-item list",
    "✓ get_required_fields('unknown_type') returns []",
    "✓ get_completeness_config() returns cached singleton",
    "✓ COMPLETENESS_CONFIG_PATH env-var override works",
    "✓ configured_document_types property works",
]

for item in validation_items:
    print(item)

print()
print("=" * 80)
print("TASK-026-001: ALL VALIDATIONS PASSED ✓")
print("=" * 80)
print()

print("Files Created:")
print("  ✓ config/document_completeness.yaml")
print("  ✓ backend/config/completeness_config.py")
print("  ✓ backend/config/__init__.py")
print()

print("Next Steps:")
print("  1. Add pyyaml to backend/requirements.txt if not already present")
print("  2. Implement TASK-026-002: CompletenessValidator class")
print("  3. Create unit tests for edge cases")
print()
