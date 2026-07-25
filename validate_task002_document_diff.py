"""
Validation script for TASK-002: Document Diff Engine

Verifies that the implementation meets all acceptance criteria:
1. compute_field_diff returns [] when content unchanged
2. compute_field_diff produces one entry per changed field
3. ChangeLogEntry.timestamp is timezone-aware UTC
4. apply_diff_to_change_log never mutates existing_log in-place
5. compute_field_diff raises ValueError for non-dict inputs
6. Field ordering is deterministic (sorted keys)
7. No external diff library imported
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Add backend to path for imports
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.schemas.document_schemas import ChangeLogEntry
from app.services.document_diff import apply_diff_to_change_log, compute_field_diff


def validate_no_changes_returns_empty():
    """Verify compute_field_diff returns [] when stored_content == updated_content"""
    stored = {"section_a": "content 1", "section_b": "content 2"}
    updated = {"section_a": "content 1", "section_b": "content 2"}
    author_id = uuid4()
    
    result = compute_field_diff(stored, updated, author_id)
    
    assert result == [], f"Expected empty list, got {result}"
    print("✓ compute_field_diff returns [] when content unchanged")


def validate_one_entry_per_changed_field():
    """Verify compute_field_diff produces one entry per changed field"""
    stored = {"section_a": "old value", "section_b": "unchanged", "section_c": "another old"}
    updated = {"section_a": "new value", "section_b": "unchanged", "section_c": "another new"}
    author_id = uuid4()
    
    result = compute_field_diff(stored, updated, author_id)
    
    assert len(result) == 2, f"Expected 2 entries, got {len(result)}"
    
    # Verify correct fields changed
    changed_fields = {entry.field for entry in result}
    assert changed_fields == {"section_a", "section_c"}, f"Unexpected fields: {changed_fields}"
    
    print("✓ compute_field_diff produces one entry per changed field")


def validate_timestamp_is_utc():
    """Verify ChangeLogEntry.timestamp is timezone-aware UTC"""
    stored = {"section_a": "old"}
    updated = {"section_a": "new"}
    author_id = uuid4()
    
    result = compute_field_diff(stored, updated, author_id)
    
    assert len(result) == 1
    entry = result[0]
    
    assert entry.timestamp.tzinfo is not None, "Timestamp must be timezone-aware"
    assert entry.timestamp.tzinfo == timezone.utc, f"Expected UTC, got {entry.timestamp.tzinfo}"
    
    print("✓ ChangeLogEntry.timestamp is timezone-aware UTC")


def validate_no_inplace_mutation():
    """Verify apply_diff_to_change_log never mutates existing_log in-place"""
    existing_log = [
        {"field": "old_field", "old_value": "a", "new_value": "b", 
         "author_id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat()}
    ]
    existing_log_copy = existing_log.copy()
    
    new_entries = [
        ChangeLogEntry(
            field="new_field",
            old_value="x",
            new_value="y",
            author_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
        )
    ]
    
    result = apply_diff_to_change_log(existing_log, new_entries)
    
    # Verify original list unchanged
    assert existing_log == existing_log_copy, "Original list was mutated"
    
    # Verify result contains both old and new entries
    assert len(result) == 2, f"Expected 2 entries, got {len(result)}"
    assert result[0] == existing_log[0], "First entry should be from existing log"
    
    print("✓ apply_diff_to_change_log never mutates existing_log in-place")


def validate_value_error_on_non_dict():
    """Verify compute_field_diff raises ValueError for non-dict inputs"""
    author_id = uuid4()
    
    # Test with non-dict stored_content
    try:
        compute_field_diff("not a dict", {}, author_id)
        assert False, "Should have raised ValueError for non-dict stored_content"
    except ValueError as e:
        assert "stored_content must be a dict" in str(e)
    
    # Test with non-dict updated_content
    try:
        compute_field_diff({}, "not a dict", author_id)
        assert False, "Should have raised ValueError for non-dict updated_content"
    except ValueError as e:
        assert "updated_content must be a dict" in str(e)
    
    print("✓ compute_field_diff raises ValueError for non-dict inputs")


def validate_deterministic_ordering():
    """Verify field ordering is deterministic (sorted keys)"""
    stored = {"z_field": "1", "a_field": "2", "m_field": "3"}
    updated = {"z_field": "changed", "a_field": "changed", "m_field": "changed"}
    author_id = uuid4()
    
    # Run multiple times to ensure consistency
    result1 = compute_field_diff(stored, updated, author_id)
    result2 = compute_field_diff(stored, updated, author_id)
    
    fields1 = [entry.field for entry in result1]
    fields2 = [entry.field for entry in result2]
    
    assert fields1 == fields2, "Field order not deterministic"
    assert fields1 == sorted(fields1), f"Fields not sorted: {fields1}"
    
    print("✓ Field ordering is deterministic (sorted keys)")


def validate_no_external_diff_library():
    """Verify no external diff library imported"""
    import ast
    
    diff_file = Path(__file__).parent / "backend" / "app" / "services" / "document_diff.py"
    source = diff_file.read_text()
    tree = ast.parse(source)
    
    # Check all imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not any(lib in alias.name for lib in ["difflib", "deepdiff", "jsondiff"]), \
                    f"Unexpected diff library import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert not any(lib in node.module for lib in ["difflib", "deepdiff", "jsondiff"]), \
                    f"Unexpected diff library import: {node.module}"
    
    print("✓ No external diff library imported (pure stdlib + project schemas)")


def main():
    """Run all validation checks"""
    print()
    print("=" * 80)
    print("TASK-002: Document Diff Engine — Validation")
    print("=" * 80)
    print()
    
    try:
        validate_no_changes_returns_empty()
        validate_one_entry_per_changed_field()
        validate_timestamp_is_utc()
        validate_no_inplace_mutation()
        validate_value_error_on_non_dict()
        validate_deterministic_ordering()
        validate_no_external_diff_library()
        
        print()
        print("=" * 80)
        print("All validation checks PASSED ✓")
        print("=" * 80)
        print()
        
        print("Implementation Summary:")
        print("  ✓ compute_field_diff function implemented")
        print("  ✓ apply_diff_to_change_log function implemented")
        print("  ✓ ChangeLogEntry schema created")
        print("  ✓ All 7 validation criteria met")
        print()
        print("Files Created:")
        print("  • backend/app/schemas/document_schemas.py")
        print("  • backend/app/services/document_diff.py")
        print()
        print("Ready for integration with:")
        print("  → TASK-003: PATCH /api/v1/documents/{id} handler")
        print("  → TASK-004: Approve/reject endpoints")
        print()
        
        return 0
        
    except AssertionError as e:
        print()
        print("=" * 80)
        print(f"VALIDATION FAILED: {e}")
        print("=" * 80)
        return 1
    except Exception as e:
        print()
        print("=" * 80)
        print(f"ERROR: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
