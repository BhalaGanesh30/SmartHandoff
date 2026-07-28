"""Unit tests for bed status state machine (status_machine.py).

Coverage:
  A01: any status → OCCUPIED (no restriction on current status)
  A03: OCCUPIED → DIRTY; invalid current status raises BedStatusTransitionError
  A02: resolve_target_status returns OCCUPIED for new bed
  Unknown event: raises ValueError

Design refs:
    US-035 TASK-006 — Unit test coverage for status_machine.py
    US-035 TASK-001 — BedStatusTransitionError exception
"""
from __future__ import annotations

import pytest

from app.agents.bed_management.schemas import BedStatus
from app.agents.bed_management.status_machine import resolve_target_status
from app.exceptions import BedStatusTransitionError


def test_a01_from_vacant_returns_occupied():
    """A01 (admit) from VACANT → OCCUPIED."""
    assert resolve_target_status("A01", BedStatus.VACANT) == BedStatus.OCCUPIED


def test_a01_from_occupied_returns_occupied():
    """A01 does not require VACANT — admit into already-occupied bed (override)."""
    assert resolve_target_status("A01", BedStatus.OCCUPIED) == BedStatus.OCCUPIED


def test_a01_from_dirty_returns_occupied():
    """A01 (admit) from DIRTY → OCCUPIED."""
    assert resolve_target_status("A01", BedStatus.DIRTY) == BedStatus.OCCUPIED


def test_a01_from_maintenance_returns_occupied():
    """A01 (admit) from MAINTENANCE → OCCUPIED."""
    assert resolve_target_status("A01", BedStatus.MAINTENANCE) == BedStatus.OCCUPIED


def test_a01_from_reserved_returns_occupied():
    """A01 (admit) from RESERVED → OCCUPIED."""
    assert resolve_target_status("A01", BedStatus.RESERVED) == BedStatus.OCCUPIED


def test_a03_from_occupied_returns_dirty():
    """A03 (discharge) from OCCUPIED → DIRTY."""
    assert resolve_target_status("A03", BedStatus.OCCUPIED) == BedStatus.DIRTY


def test_a03_from_vacant_raises_transition_error():
    """A03 (discharge) from VACANT is invalid — cannot discharge unoccupied bed."""
    with pytest.raises(BedStatusTransitionError):
        resolve_target_status("A03", BedStatus.VACANT)


def test_a03_from_dirty_raises_transition_error():
    """A03 (discharge) from DIRTY is invalid."""
    with pytest.raises(BedStatusTransitionError):
        resolve_target_status("A03", BedStatus.DIRTY)


def test_a03_from_maintenance_raises_transition_error():
    """A03 (discharge) from MAINTENANCE is invalid."""
    with pytest.raises(BedStatusTransitionError):
        resolve_target_status("A03", BedStatus.MAINTENANCE)


def test_a03_from_reserved_raises_transition_error():
    """A03 (discharge) from RESERVED is invalid."""
    with pytest.raises(BedStatusTransitionError):
        resolve_target_status("A03", BedStatus.RESERVED)


def test_a02_returns_occupied_for_new_bed():
    """A02 (transfer): new bed target status is OCCUPIED regardless of current."""
    assert resolve_target_status("A02", BedStatus.VACANT) == BedStatus.OCCUPIED
    assert resolve_target_status("A02", BedStatus.DIRTY) == BedStatus.OCCUPIED
    assert resolve_target_status("A02", BedStatus.MAINTENANCE) == BedStatus.OCCUPIED


def test_unknown_event_raises_value_error():
    """Unhandled event type (e.g., A08) raises ValueError."""
    with pytest.raises(ValueError, match="does not handle event type"):
        resolve_target_status("A08", BedStatus.VACANT)
