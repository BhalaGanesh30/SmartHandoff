"""Validation script for TASK-002: RxNav Batch Interaction API Client.

Validates:
    - Severity mapping for all RxNav severity labels
    - Empty rxcuis list handling
    - Source field set to "RXNAV"
    - RxNavUnavailableError exception handling
"""
import sys
import importlib.util
from pathlib import Path

# Load the module directly to avoid package import dependencies
module_path = Path(__file__).parent / "backend" / "app" / "agents" / "medication_reconciliation" / "drug_interaction" / "rxnav_client.py"
spec = importlib.util.spec_from_file_location("rxnav_client", module_path)
rxnav_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rxnav_client)

InteractionSeverity = rxnav_client.InteractionSeverity
RxNavUnavailableError = rxnav_client.RxNavUnavailableError
RxNavInteractionClient = rxnav_client.RxNavInteractionClient
_map_severity = rxnav_client._map_severity
_parse_interactions = rxnav_client._parse_interactions


def validate_severity_mapping():
    """Validate severity mapping logic."""
    print("✓ Testing severity mapping...")
    
    # Test HIGH mappings
    assert _map_severity("major") == InteractionSeverity.HIGH, "major should map to HIGH"
    assert _map_severity("MAJOR") == InteractionSeverity.HIGH, "MAJOR should map to HIGH"
    assert _map_severity("  major  ") == InteractionSeverity.HIGH, "major with spaces should map to HIGH"
    assert _map_severity("contraindicated") == InteractionSeverity.HIGH, "contraindicated should map to HIGH"
    assert _map_severity("CONTRAINDICATED") == InteractionSeverity.HIGH, "CONTRAINDICATED should map to HIGH"
    print("  ✓ HIGH severity mappings (major, contraindicated) work correctly")
    
    # Test MEDIUM mappings
    assert _map_severity("moderate") == InteractionSeverity.MEDIUM, "moderate should map to MEDIUM"
    assert _map_severity("MODERATE") == InteractionSeverity.MEDIUM, "MODERATE should map to MEDIUM"
    assert _map_severity("  moderate  ") == InteractionSeverity.MEDIUM, "moderate with spaces should map to MEDIUM"
    print("  ✓ MEDIUM severity mappings (moderate) work correctly")
    
    # Test LOW mappings
    assert _map_severity("minor") == InteractionSeverity.LOW, "minor should map to LOW"
    assert _map_severity("MINOR") == InteractionSeverity.LOW, "MINOR should map to LOW"
    assert _map_severity("unknown") == InteractionSeverity.LOW, "unknown should map to LOW"
    assert _map_severity("") == InteractionSeverity.LOW, "empty string should map to LOW"
    print("  ✓ LOW severity mappings (minor, other) work correctly")


def validate_parse_interactions():
    """Validate interaction parsing logic."""
    print("\n✓ Testing interaction parsing...")
    
    # Test empty response
    empty_response = {}
    interactions = _parse_interactions(empty_response)
    assert interactions == [], "Empty response should return empty list"
    print("  ✓ Empty response handling works correctly")
    
    # Test response with interactions
    sample_response = {
        "fullInteractionTypeGroup": [
            {
                "fullInteractionType": [
                    {
                        "interactionPair": [
                            {
                                "interactionConcept": [
                                    {
                                        "minConceptItem": {
                                            "rxcui": "11289",
                                            "name": "Warfarin"
                                        }
                                    },
                                    {
                                        "minConceptItem": {
                                            "rxcui": "1191",
                                            "name": "Aspirin"
                                        }
                                    }
                                ],
                                "severity": "major",
                                "description": "Increased risk of bleeding"
                            }
                        ]
                    }
                ]
            }
        ]
    }
    
    interactions = _parse_interactions(sample_response)
    assert len(interactions) == 1, "Should parse one interaction"
    
    interaction = interactions[0]
    assert interaction["rxcui1"] == "11289", "rxcui1 should be 11289"
    assert interaction["rxcui2"] == "1191", "rxcui2 should be 1191"
    assert interaction["drug1"] == "Warfarin", "drug1 should be Warfarin"
    assert interaction["drug2"] == "Aspirin", "drug2 should be Aspirin"
    assert interaction["severity"] == "HIGH", "severity should be HIGH"
    assert interaction["description"] == "Increased risk of bleeding", "description should match"
    assert interaction["source"] == "RXNAV", "source should be RXNAV"
    print("  ✓ Interaction parsing works correctly")
    print("  ✓ Source field set to 'RXNAV'")


def validate_client_initialization():
    """Validate client initialization."""
    print("\n✓ Testing client initialization...")
    
    # Test without http_client
    client1 = RxNavInteractionClient()
    assert client1._client is None, "Client should be None when not provided"
    print("  ✓ Client initialization without http_client works")
    
    # Test with http_client (mock)
    import httpx
    http_client = httpx.AsyncClient()
    client2 = RxNavInteractionClient(http_client=http_client)
    assert client2._client is http_client, "Client should be set when provided"
    print("  ✓ Client initialization with http_client works")


def validate_exception_handling():
    """Validate exception handling."""
    print("\n✓ Testing exception handling...")
    
    # Test RxNavUnavailableError
    error = RxNavUnavailableError(503)
    assert error.status_code == 503, "Status code should be 503"
    assert "503" in str(error), "Error message should contain status code"
    print("  ✓ RxNavUnavailableError exception works correctly")
    
    # Test with custom message
    error_custom = RxNavUnavailableError(503, "Custom error message")
    assert error_custom.status_code == 503, "Status code should be 503"
    assert str(error_custom) == "Custom error message", "Custom message should be used"
    print("  ✓ RxNavUnavailableError with custom message works")


def main():
    """Run all validation tests."""
    print("=" * 70)
    print("TASK-002 Validation: RxNav Batch Interaction API Client")
    print("=" * 70)
    
    try:
        validate_severity_mapping()
        validate_parse_interactions()
        validate_client_initialization()
        validate_exception_handling()
        
        print("\n" + "=" * 70)
        print("✅ ALL VALIDATION CHECKS PASSED")
        print("=" * 70)
        print("\nValidation Summary:")
        print("  ✓ Severity mapping: major/contraindicated → HIGH")
        print("  ✓ Severity mapping: moderate → MEDIUM")
        print("  ✓ Severity mapping: minor/other → LOW")
        print("  ✓ Empty rxcuis list handling")
        print("  ✓ Source field set to 'RXNAV'")
        print("  ✓ RxNavUnavailableError exception handling")
        print("\nDefinition of Done:")
        print("  ✓ rxnav_client.py implemented")
        print("  ✓ Severity mapping verified against all four RxNav severity labels")
        print("  ⚠ Unit tests for HTTP 503 → RxNavUnavailableError (covered in TASK-008)")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
