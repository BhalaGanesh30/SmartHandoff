"""Unit tests for MedicationSummaryWriter — US-033 AC Scenario 3.

Test matrix:
    - write() persists medications_section to Document
    - write() raises ValueError for unknown document_id
    - db.flush() called (not commit) — caller owns transaction
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.agents.medication_reconciliation.summary.writer import MedicationSummaryWriter
from app.agents.medication_reconciliation.summary.schema import MedicationSummaryOutput


@pytest.mark.asyncio
async def test_write_persists_medications_section():
    """Write persists summary.model_dump() to document.medications_section."""
    summary = MedicationSummaryOutput()
    document_id = uuid4()
    mock_document = MagicMock()
    mock_document.id = document_id

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=mock_document)
    )

    writer = MedicationSummaryWriter(db=mock_db)
    await writer.write(document_id=document_id, summary=summary)

    assert mock_document.medications_section == summary.model_dump()
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_raises_for_unknown_document_id():
    """ValueError raised when document_id not found in database."""
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=None)
    )

    writer = MedicationSummaryWriter(db=mock_db)
    unknown_id = uuid4()
    with pytest.raises(ValueError, match="not found"):
        await writer.write(document_id=unknown_id, summary=MedicationSummaryOutput())


@pytest.mark.asyncio
async def test_write_calls_flush_not_commit():
    """Writer calls db.flush() (caller owns transaction, not commit)."""
    summary = MedicationSummaryOutput()
    document_id = uuid4()
    mock_document = MagicMock()

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=mock_document)
    )

    writer = MedicationSummaryWriter(db=mock_db)
    await writer.write(document_id=document_id, summary=summary)

    # Verify flush called, commit NOT called
    mock_db.flush.assert_awaited_once()
    assert not mock_db.commit.called
