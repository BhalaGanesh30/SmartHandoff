"""
Validation script for TASK-006: DocumentRepository.create_discharge_document()

Validates implementation completeness and test coverage.
"""
import pathlib
import sys


def validate_task_006():
    """Run validation checks for TASK-006 implementation."""
    
    print()
    print("=" * 80)
    print("TASK-006: DocumentRepository.create_discharge_document() — VALIDATION")
    print("=" * 80)
    print()
    
    all_passed = True
    
    # Check 1: Repository implementation exists
    print("1. Repository Implementation:")
    repo_file = pathlib.Path("backend/app/db/repositories/document_repository.py")
    if repo_file.exists():
        size = repo_file.stat().st_size
        print(f"   ✓ document_repository.py exists ({size} bytes)")
        
        # Check for key methods
        content = repo_file.read_text()
        if "create_discharge_document" in content:
            print("   ✓ create_discharge_document method implemented")
        else:
            print("   ✗ create_discharge_document method not found")
            all_passed = False
            
        if "SignalRHub" in content:
            print("   ✓ SignalR integration present")
        else:
            print("   ✗ SignalR integration missing")
            all_passed = False
    else:
        print("   ✗ document_repository.py not found")
        all_passed = False
    
    print()
    
    # Check 2: Test file exists
    print("2. Unit Tests:")
    test_file = pathlib.Path("backend/tests/unit/db/repositories/test_document_repository.py")
    if test_file.exists():
        size = test_file.stat().st_size
        print(f"   ✓ test_document_repository.py exists ({size} bytes)")
        
        # Count test functions
        content = test_file.read_text()
        test_count = content.count("async def test_")
        print(f"   ✓ {test_count} test functions defined")
        
        # Check for key tests
        key_tests = [
            "test_create_discharge_document_sets_pending_approval",
            "test_create_discharge_document_sets_generation_type_ai",
            "test_create_discharge_document_template_sets_generation_type_template",
            "test_signalr_push_sent_after_commit",
        ]
        
        for test_name in key_tests:
            if test_name in content:
                print(f"   ✓ {test_name}")
            else:
                print(f"   ✗ {test_name} missing")
                all_passed = False
    else:
        print("   ✗ test_document_repository.py not found")
        all_passed = False
    
    print()
    
    # Check 3: Required imports and dependencies
    print("3. Dependencies:")
    
    # Check Document model
    doc_model = pathlib.Path("backend/app/models/document.py")
    if doc_model.exists():
        content = doc_model.read_text()
        if "generation_type" in content:
            print("   ✓ Document model has generation_type field")
        else:
            print("   ✗ Document model missing generation_type field")
            all_passed = False
            
        if "DocumentStatus" in content:
            print("   ✓ DocumentStatus enum exists")
        else:
            print("   ✗ DocumentStatus enum missing")
            all_passed = False
    else:
        print("   ✗ Document model not found")
        all_passed = False
    
    # Check schemas
    schemas_file = pathlib.Path("backend/agents/documentation/schemas.py")
    if schemas_file.exists():
        content = schemas_file.read_text()
        if "DischargeSummarySchema" in content:
            print("   ✓ DischargeSummarySchema exists")
        else:
            print("   ✗ DischargeSummarySchema missing")
            all_passed = False
            
        if "GenerationType" in content:
            print("   ✓ GenerationType enum exists")
        else:
            print("   ✗ GenerationType enum missing")
            all_passed = False
    else:
        print("   ✗ schemas.py not found")
        all_passed = False
    
    # Check SignalR
    signalr_file = pathlib.Path("backend/app/signalr/__init__.py")
    if signalr_file.exists():
        content = signalr_file.read_text()
        if "SignalRHub" in content:
            print("   ✓ SignalRHub class exists")
        else:
            print("   ✗ SignalRHub class missing")
            all_passed = False
    else:
        print("   ✗ SignalR module not found")
        all_passed = False
    
    print()
    
    # Check 4: Implementation summary
    print("4. Documentation:")
    summary_file = pathlib.Path("US-025-TASK-006-IMPLEMENTATION-SUMMARY.md")
    if summary_file.exists():
        size = summary_file.stat().st_size
        print(f"   ✓ Implementation summary exists ({size} bytes)")
    else:
        print("   ✗ Implementation summary not found")
        all_passed = False
    
    print()
    print("=" * 80)
    
    if all_passed:
        print("✓ ALL VALIDATION CHECKS PASSED")
        print("=" * 80)
        print()
        print("Next Steps:")
        print("  1. Run unit tests:")
        print("     cd backend")
        print("     python -m pytest tests/unit/db/repositories/test_document_repository.py -v")
        print()
        print("  2. Integrate with DocumentationAgent:")
        print("     - Update DocumentationAgent.process() to call repository")
        print("     - Add integration tests")
        print()
        print("  3. End-to-end testing:")
        print("     - Test with real FHIR data")
        print("     - Verify SignalR notifications received")
        print("     - Validate encryption at database level")
        print()
        return 0
    else:
        print("✗ VALIDATION FAILED")
        print("=" * 80)
        print()
        print("Please fix the issues above and re-run validation.")
        print()
        return 1


if __name__ == "__main__":
    exit_code = validate_task_006()
    sys.exit(exit_code)
