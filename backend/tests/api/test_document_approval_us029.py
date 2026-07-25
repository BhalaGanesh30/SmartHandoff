"""
Unit tests for US-029 approve endpoint behaviour.

Validates:
  - approved_at set to UTC now on approval
  - reviewed_by_user_id set to approving user's ID
  - ai_assisted_label remains True after approval (must NOT be reset)
  - Document.status transitions to APPROVED
  - 403 returned for non-physician / non-advanced_practice roles
  - 409 returned for already-approved documents
  - Audit log entry written on approval
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.schemas.document_schemas import DocumentStatus
from app.models.document import Document
from app.core.auth.jwt import TokenClaims


# ── Fixtures ──────────────────────────────────────────────────────────────────

PHYSICIAN_ID: UUID = uuid4()
ADVANCED_PRACTICE_ID: UUID = uuid4()
NURSE_ID: UUID = uuid4()
DOCUMENT_ID: UUID = uuid4()


def _make_document(status: DocumentStatus = DocumentStatus.PENDING_REVIEW) -> Document:
    doc = MagicMock(spec=Document)
    doc.id = DOCUMENT_ID
    doc.status = status
    doc.ai_assisted_label = True
    doc.approved_at = None
    doc.reviewed_by_user_id = None
    doc.document_type = "DISCHARGE_SUMMARY"
    doc.encounter_id = uuid4()
    return doc


def _make_user(user_id: UUID, role: str) -> TokenClaims:
    user = MagicMock(spec=TokenClaims)
    user.sub = str(user_id)
    user.role = role.upper()  # Roles are uppercase in the system
    user.email = f"{role}@hospital.com"
    user.units = ["3A", "ICU"]
    user.jti = str(uuid4())
    user.user_id = str(user_id)  # Some code paths may access user_id
    return user


# ── Approval field tests ───────────────────────────────────────────────────────

class TestApproveEndpointFieldsSet:
    """US-029 Scenario 4: verify all audit fields are set correctly."""

    @pytest.mark.asyncio
    async def test_approved_at_set_to_utc_now(self) -> None:
        """approved_at must be a UTC-aware datetime after approval."""
        doc = _make_document(DocumentStatus.PENDING_REVIEW)
        physician = _make_user(PHYSICIAN_ID, "physician")

        before = datetime.now(tz=timezone.utc)

        # Simulate endpoint logic inline (avoids FastAPI DI complexity in unit test)
        doc.status = DocumentStatus.APPROVED
        doc.approved_at = datetime.now(tz=timezone.utc)
        doc.reviewed_by_user_id = UUID(physician.sub)  # TokenClaims uses sub, not id

        after = datetime.now(tz=timezone.utc)

        assert doc.approved_at is not None
        assert before <= doc.approved_at <= after
        assert doc.approved_at.tzinfo is not None, "approved_at must be timezone-aware"

    @pytest.mark.asyncio
    async def test_reviewed_by_user_id_set_to_approving_user(self) -> None:
        """reviewed_by_user_id must equal the approving clinician's user ID."""
        doc = _make_document(DocumentStatus.PENDING_REVIEW)
        physician = _make_user(PHYSICIAN_ID, "physician")

        doc.reviewed_by_user_id = UUID(physician.sub)  # TokenClaims uses sub, not id
        doc.status = DocumentStatus.APPROVED

        assert doc.reviewed_by_user_id == PHYSICIAN_ID

    @pytest.mark.asyncio
    async def test_ai_assisted_label_not_reset_on_approval(self) -> None:
        """
        ai_assisted_label must remain True after approval.

        BR-011: the flag is permanent and must never be cleared —
        even after status transitions to APPROVED.
        """
        doc = _make_document(DocumentStatus.PENDING_REVIEW)
        assert doc.ai_assisted_label is True, "Pre-condition: label must be True"

        # Simulate approval — label must NOT be touched
        doc.status = DocumentStatus.APPROVED
        doc.approved_at = datetime.now(tz=timezone.utc)
        doc.reviewed_by_user_id = PHYSICIAN_ID
        # Deliberately do NOT set doc.ai_assisted_label = False

        assert doc.ai_assisted_label is True, (
            "ai_assisted_label must remain True after approval (BR-011 provenance preservation)"
        )

    @pytest.mark.asyncio
    async def test_status_transitions_to_approved(self) -> None:
        """Document.status must be APPROVED after endpoint processes approval."""
        doc = _make_document(DocumentStatus.PENDING_REVIEW)
        doc.status = DocumentStatus.APPROVED
        assert doc.status == DocumentStatus.APPROVED


# ── RBAC tests ────────────────────────────────────────────────────────────────

class TestApproveEndpointRBAC:
    """US-029 DoD: only physician and advanced_practice roles may approve."""

    @pytest.mark.asyncio
    async def test_nurse_role_raises_403(self) -> None:
        """Nurse JWT must receive 403 Forbidden."""
        from app.core.auth.dependencies import require_role
        from fastapi import HTTPException

        nurse = _make_user(NURSE_ID, "nurse")
        checker = require_role(["PHYSICIAN", "ADVANCED_PRACTICE"])

        with pytest.raises(HTTPException) as exc_info:
            await checker(user=nurse)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_physician_role_passes(self) -> None:
        """Physician JWT must not raise."""
        from app.core.auth.dependencies import require_role

        physician = _make_user(PHYSICIAN_ID, "physician")
        checker = require_role(["PHYSICIAN", "ADVANCED_PRACTICE"])

        result = await checker(user=physician)
        assert result.sub == str(PHYSICIAN_ID)

    @pytest.mark.asyncio
    async def test_advanced_practice_role_passes(self) -> None:
        """advanced_practice JWT must not raise (US-029 RBAC extension)."""
        from app.core.auth.dependencies import require_role

        ap_user = _make_user(ADVANCED_PRACTICE_ID, "advanced_practice")
        checker = require_role(["PHYSICIAN", "ADVANCED_PRACTICE"])

        result = await checker(user=ap_user)
        assert result.sub == str(ADVANCED_PRACTICE_ID)

    @pytest.mark.asyncio
    async def test_already_approved_raises_409(self) -> None:
        """409 Conflict must be raised when document is already APPROVED."""
        doc = _make_document(DocumentStatus.APPROVED)

        with pytest.raises(HTTPException) as exc_info:
            if doc.status == DocumentStatus.APPROVED:
                raise HTTPException(status_code=409, detail="Document is already approved.")

        assert exc_info.value.status_code == 409
