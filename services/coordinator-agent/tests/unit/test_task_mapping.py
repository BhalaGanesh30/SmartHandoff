"""Unit tests for coordinator task type mapping (SC-1, SC-2)."""
import pytest

from app.coordinator.task_mapping import AgentTaskType, get_task_types_for_event


class TestAdmitEventMapping:
    """SC-1: ADT^A01 must create exactly 5 task types."""

    def test_admit_creates_five_tasks(self):
        tasks = get_task_types_for_event("ADT^A01")
        assert len(tasks) == 5

    def test_admit_includes_all_required_task_types(self):
        tasks = get_task_types_for_event("ADT^A01")
        required = {
            AgentTaskType.DOCUMENTATION,
            AgentTaskType.MEDICATION_RECONCILIATION,
            AgentTaskType.BED_MANAGEMENT,
            AgentTaskType.FOLLOW_UP_CARE,
            AgentTaskType.PATIENT_COMMUNICATION,
        }
        assert set(tasks) == required


class TestTransferEventMapping:
    """SC-2: ADT^A02 must NOT include DISCHARGE_SUMMARY."""

    def test_transfer_excludes_discharge_summary(self):
        tasks = get_task_types_for_event("ADT^A02")
        assert AgentTaskType.DISCHARGE_SUMMARY not in tasks

    def test_transfer_includes_bed_management(self):
        tasks = get_task_types_for_event("ADT^A02")
        assert AgentTaskType.BED_MANAGEMENT in tasks

    def test_transfer_includes_transfer_note(self):
        tasks = get_task_types_for_event("ADT^A02")
        assert AgentTaskType.TRANSFER_NOTE in tasks


class TestUnknownEventMapping:
    """Unknown event types return empty list — no tasks, no exception."""

    def test_unknown_event_type_returns_empty(self):
        result = get_task_types_for_event("ADT^A99")
        assert result == []

    def test_empty_string_returns_empty(self):
        result = get_task_types_for_event("")
        assert result == []
