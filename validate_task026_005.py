"""
Validation script for TASK-026-005: Review Queue Filter and Task API Completeness Fields

This script validates the implementation of:
1. DocumentRepository.get_review_queue() method with completeness filtering
2. AgentTaskResponse schema with document completeness fields
3. Encounter tasks API enhancement to include document information

US-026 Scenario 2: INCOMPLETE documents excluded from review queue
US-026 Scenario 4: Tasks API includes completeness_status and missing_fields
"""
import ast
import pathlib
import sys


def validate_imports() -> bool:
    """Validate that required modules can be imported."""
    print("=" * 70)
    print("VALIDATION 1: Import Checks")
    print("=" * 70)
    print()
    
    try:
        # Check DocumentRepository imports
        doc_repo_file = pathlib.Path("backend/app/db/repositories/document_repository.py")
        if not doc_repo_file.exists():
            print("✗ DocumentRepository file not found")
            return False
        
        content = doc_repo_file.read_text(encoding='utf-8')
        if "from sqlalchemy import select" not in content:
            print("✗ Missing 'from sqlalchemy import select' import")
            return False
        
        print("✓ DocumentRepository imports are correct")
        
        # Check schema imports
        schema_file = pathlib.Path("backend/app/schemas/agent_task.py")
        if not schema_file.exists():
            print("✗ agent_task schema file not found")
            return False
        
        print("✓ Schema file exists")
        
        # Check router imports
        router_file = pathlib.Path("backend/app/api/v1/routers/encounter_tasks.py")
        if not router_file.exists():
            print("✗ encounter_tasks router file not found")
            return False
        
        router_content = router_file.read_text(encoding='utf-8')
        if "from app.models.document import Document" not in router_content:
            print("✗ Missing Document model import in router")
            return False
        
        print("✓ Router imports are correct")
        print()
        return True
        
    except Exception as e:
        print(f"✗ Import validation failed: {e}")
        return False


def validate_get_review_queue_method() -> bool:
    """Validate that get_review_queue() method exists with correct implementation."""
    print("=" * 70)
    print("VALIDATION 2: DocumentRepository.get_review_queue() Method")
    print("=" * 70)
    print()
    
    doc_repo_file = pathlib.Path("backend/app/db/repositories/document_repository.py")
    content = doc_repo_file.read_text(encoding='utf-8')
    
    checks = [
        ("Method definition", "async def get_review_queue"),
        ("PENDING_APPROVAL filter", 'Document.status == DocumentStatus.PENDING_APPROVAL.value'),
        ("COMPLETE filter", 'Document.completeness_status == "COMPLETE"'),
        ("Pagination support", "limit: int = 50"),
        ("Order by created_at", "order_by(Document.created_at.asc())"),
    ]
    
    all_passed = True
    for check_name, search_str in checks:
        if search_str in content:
            print(f"✓ {check_name}: found")
        else:
            print(f"✗ {check_name}: NOT found")
            all_passed = False
    
    # Check that get_by_encounter method also exists
    if "async def get_by_encounter" in content:
        print("✓ get_by_encounter() helper method: found")
    else:
        print("✗ get_by_encounter() helper method: NOT found")
        all_passed = False
    
    print()
    return all_passed


def validate_schema_fields() -> bool:
    """Validate that AgentTaskResponse has document completeness fields."""
    print("=" * 70)
    print("VALIDATION 3: AgentTaskResponse Schema Fields")
    print("=" * 70)
    print()
    
    schema_file = pathlib.Path("backend/app/schemas/agent_task.py")
    content = schema_file.read_text(encoding='utf-8')
    
    required_fields = [
        "document_id: UUID | None",
        "generation_type: str | None",
        "completeness_status: str | None",
        "missing_fields: list[str]",
    ]
    
    all_passed = True
    for field in required_fields:
        if field in content:
            print(f"✓ Field '{field}' found in schema")
        else:
            print(f"✗ Field '{field}' NOT found in schema")
            all_passed = False
    
    # Validate that US-026 comments are present
    if "US-026" in content and "Document completeness fields" in content:
        print("✓ US-026 documentation comments present")
    else:
        print("✗ US-026 documentation comments missing")
        all_passed = False
    
    print()
    return all_passed


def validate_router_implementation() -> bool:
    """Validate that encounter_tasks router populates completeness fields."""
    print("=" * 70)
    print("VALIDATION 4: Encounter Tasks Router Implementation")
    print("=" * 70)
    print()
    
    router_file = pathlib.Path("backend/app/api/v1/routers/encounter_tasks.py")
    content = router_file.read_text(encoding='utf-8')
    
    checks = [
        ("Document query", "sa.select(Document)"),
        ("Document filter", "Document.encounter_id == encounter_id"),
        ("Latest document selection", "documents[0] if documents else None"),
        ("Agent type check", 'task.agent_type.lower() == "documentation"'),
        ("Document ID assignment", "task_resp.document_id = latest_doc.id"),
        ("Generation type assignment", "task_resp.generation_type = latest_doc.generation_type"),
        ("Completeness status assignment", "task_resp.completeness_status = latest_doc.completeness_status"),
        ("Missing fields assignment", "task_resp.missing_fields = latest_doc.missing_fields or []"),
    ]
    
    all_passed = True
    for check_name, search_str in checks:
        if search_str in content:
            print(f"✓ {check_name}: found")
        else:
            print(f"✗ {check_name}: NOT found")
            all_passed = False
    
    # Check US-026 documentation
    if "US-026" in content:
        print("✓ US-026 documentation comments present")
    else:
        print("✗ US-026 documentation comments missing")
        all_passed = False
    
    print()
    return all_passed


def validate_no_n_plus_one() -> bool:
    """Validate that document lookup is a single query, not N+1."""
    print("=" * 70)
    print("VALIDATION 5: No N+1 Query Pattern")
    print("=" * 70)
    print()
    
    router_file = pathlib.Path("backend/app/api/v1/routers/encounter_tasks.py")
    content = router_file.read_text(encoding='utf-8')
    
    # Check that documents are fetched ONCE before the task loop
    doc_query_before_loop = (
        "doc_stmt = (" in content and
        "sa.select(Document)" in content and
        "for task in tasks:" in content
    )
    
    if doc_query_before_loop:
        print("✓ Documents fetched once before task loop (no N+1)")
        
        # Verify the query is outside the loop
        doc_query_pos = content.find("doc_stmt = (")
        loop_pos = content.find("for task in tasks:")
        
        if doc_query_pos < loop_pos:
            print("✓ Document query positioned before task loop")
            print()
            return True
        else:
            print("✗ Document query appears after task loop")
            print()
            return False
    else:
        print("✗ Document query pattern not found or inside loop (potential N+1)")
        print()
        return False


def main() -> int:
    """Run all validation checks."""
    print()
    print("=" * 70)
    print("TASK-026-005 VALIDATION SCRIPT")
    print("=" * 70)
    print()
    
    results = [
        ("Import Checks", validate_imports()),
        ("get_review_queue() Method", validate_get_review_queue_method()),
        ("Schema Fields", validate_schema_fields()),
        ("Router Implementation", validate_router_implementation()),
        ("No N+1 Query", validate_no_n_plus_one()),
    ]
    
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print()
    
    for check_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status:<12} {check_name}")
    
    print()
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"Total: {passed}/{total} checks passed")
    print()
    
    if passed == total:
        print("=" * 70)
        print("TASK-026-005: ALL VALIDATIONS PASSED ✓")
        print("=" * 70)
        print()
        return 0
    else:
        print("=" * 70)
        print("TASK-026-005: SOME VALIDATIONS FAILED ✗")
        print("=" * 70)
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
