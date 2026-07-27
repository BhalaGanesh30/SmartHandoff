"""
Unit tests for the document_diff service module.

Validates field-level diff detection, append-only log behaviour, and edge cases.
"""
import pytest
from uuid import UUID, uuid4
from datetime import timezone

from app.schemas.document_schemas import ChangeLogEntry
from app.services.document_diff import compute_field_diff, apply_diff_to_change_log

AUTHOR_ID: UUID = uuid4()


class TestComputeFieldDiff:
    """Tests for compute_field_diff()."""

    def test_no_changes_returns_empty_list(self) -> None:
        stored = {"medications": "Aspirin 100mg", "diet": "Low sodium"}
        updated = {"medications": "Aspirin 100mg", "diet": "Low sodium"}
        result = compute_field_diff(stored, updated, AUTHOR_ID)
        assert result == []

    def test_single_field_change_produces_one_entry(self) -> None:
        stored = {"medications": "Aspirin 100mg"}
        updated = {"medications": "Aspirin 75mg"}
        entries = compute_field_diff(stored, updated, AUTHOR_ID)
        assert len(entries) == 1
        assert entries[0].field == "medications"
        assert entries[0].old_value == "Aspirin 100mg"
        assert entries[0].new_value == "Aspirin 75mg"
        assert entries[0].author_id == AUTHOR_ID

    def test_multiple_fields_changed_produces_multiple_entries(self) -> None:
        stored = {"medications": "Aspirin", "diet": "Normal", "activity": "Rest"}
        updated = {"medications": "Warfarin", "diet": "Low sodium", "activity": "Rest"}
        entries = compute_field_diff(stored, updated, AUTHOR_ID)
        changed_fields = {e.field for e in entries}
        assert changed_fields == {"medications", "diet"}
        assert len(entries) == 2

    def test_new_field_added_produces_entry_with_none_old_value(self) -> None:
        stored: dict = {}
        updated = {"medications": "New med"}
        entries = compute_field_diff(stored, updated, AUTHOR_ID)
        assert len(entries) == 1
        assert entries[0].old_value is None
        assert entries[0].new_value == "New med"

    def test_field_removed_produces_entry_with_none_new_value(self) -> None:
        stored = {"medications": "Aspirin"}
        updated: dict = {}
        entries = compute_field_diff(stored, updated, AUTHOR_ID)
        assert len(entries) == 1
        assert entries[0].old_value == "Aspirin"
        assert entries[0].new_value is None

    def test_timestamp_is_timezone_aware_utc(self) -> None:
        stored = {"medications": "Old"}
        updated = {"medications": "New"}
        entries = compute_field_diff(stored, updated, AUTHOR_ID)
        assert entries[0].timestamp.tzinfo is not None
        assert entries[0].timestamp.tzinfo == timezone.utc

    def test_raises_value_error_for_non_dict_stored(self) -> None:
        with pytest.raises(ValueError, match="stored_content must be a dict"):
            compute_field_diff("not a dict", {}, AUTHOR_ID)  # type: ignore

    def test_raises_value_error_for_non_dict_updated(self) -> None:
        with pytest.raises(ValueError, match="updated_content must be a dict"):
            compute_field_diff({}, 42, AUTHOR_ID)  # type: ignore

    def test_entries_ordered_by_field_name(self) -> None:
        """Entries must be sorted by field key for deterministic audit trails."""
        stored = {"z_field": "old", "a_field": "old"}
        updated = {"z_field": "new", "a_field": "new"}
        entries = compute_field_diff(stored, updated, AUTHOR_ID)
        assert entries[0].field == "a_field"
        assert entries[1].field == "z_field"


class TestApplyDiffToChangeLog:
    """Tests for apply_diff_to_change_log()."""

    def _make_entry(self) -> ChangeLogEntry:
        return ChangeLogEntry(
            field="medications",
            old_value="Aspirin",
            new_value="Warfarin",
            author_id=AUTHOR_ID,
        )

    def test_appends_to_empty_log(self) -> None:
        entry = self._make_entry()
        result = apply_diff_to_change_log([], [entry])
        assert len(result) == 1
        assert result[0]["field"] == "medications"

    def test_appends_to_existing_log(self) -> None:
        existing = [{"field": "diet", "old_value": "a", "new_value": "b",
                     "author_id": str(AUTHOR_ID), "timestamp": "2026-07-16T00:00:00Z"}]
        entry = self._make_entry()
        result = apply_diff_to_change_log(existing, [entry])
        assert len(result) == 2
        assert result[0]["field"] == "diet"
        assert result[1]["field"] == "medications"

    def test_does_not_mutate_existing_log(self) -> None:
        existing: list[dict] = []
        entry = self._make_entry()
        apply_diff_to_change_log(existing, [entry])
        assert existing == []  # Original list unchanged

    def test_empty_new_entries_returns_copy_of_existing(self) -> None:
        existing = [{"field": "diet"}]
        result = apply_diff_to_change_log(existing, [])
        assert result == existing
        assert result is not existing  # New list object
