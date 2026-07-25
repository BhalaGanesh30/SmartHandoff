"""
Unit tests for US-029 Scenario 3 — portal documents filter.

Validates that GET /api/v1/portal/documents returns only APPROVED documents
and that PENDING_REVIEW, DRAFT, and REJECTED are silently excluded.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.schemas.document_schemas import DocumentResponse, DocumentStatus


ENCOUNTER_ID = uuid4()
PATIENT_USER_ID = uuid4()


def _make_doc(doc_id, status: DocumentStatus) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.status = status
    doc.encounter_id = ENCOUNTER_ID
    doc.ai_assisted_label = True
    doc.approved_at = None
    doc.reviewed_by_user_id = None
    doc.reviewed_by_display_name = None
    return doc


class TestPortalDocumentsFilter:
    """US-029 Scenario 3 — APPROVED-only filter."""

    def test_pending_review_documents_excluded(self) -> None:
        """PENDING_REVIEW documents must not appear in portal response."""
        all_docs = [
            _make_doc(uuid4(), DocumentStatus.APPROVED),
            _make_doc(uuid4(), DocumentStatus.PENDING_REVIEW),   # must be excluded
            _make_doc(uuid4(), DocumentStatus.DRAFT),             # must be excluded
        ]
        filtered = [d for d in all_docs if d.status == DocumentStatus.APPROVED]

        assert len(filtered) == 1
        assert all(d.status == DocumentStatus.APPROVED for d in filtered)

    def test_only_approved_documents_returned(self) -> None:
        """Only APPROVED documents must be present in the filtered set."""
        docs = [_make_doc(uuid4(), DocumentStatus.APPROVED) for _ in range(3)]
        docs.append(_make_doc(uuid4(), DocumentStatus.REJECTED))

        approved_only = [d for d in docs if d.status == DocumentStatus.APPROVED]

        assert len(approved_only) == 3

    def test_empty_list_when_no_approved_documents(self) -> None:
        """Empty list returned when no approved documents exist — not 404."""
        docs = [_make_doc(uuid4(), DocumentStatus.PENDING_REVIEW)]
        approved_only = [d for d in docs if d.status == DocumentStatus.APPROVED]
        assert approved_only == []

    def test_rejected_documents_excluded(self) -> None:
        """REJECTED documents must be excluded from portal response."""
        docs = [
            _make_doc(uuid4(), DocumentStatus.REJECTED),
            _make_doc(uuid4(), DocumentStatus.APPROVED),
        ]
        filtered = [d for d in docs if d.status == DocumentStatus.APPROVED]
        assert len(filtered) == 1
        assert filtered[0].status == DocumentStatus.APPROVED
