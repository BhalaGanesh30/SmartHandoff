"""
Field-level JSON diff engine for document change tracking.

Compares the stored document content against the incoming edited payload and
produces a list of ChangeLogEntry records — one per changed top-level field.

Design decisions:
- Top-level key comparison only: discharge summary sections are atomic strings
  or small objects; deep-diff is deferred to Phase 2.
- Strict equality (==): avoids false negatives from whitespace normalisation;
  callers must normalise before passing if needed.
- No external diff library dependency: keeps the agent container lightweight.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.schemas.document_schemas import ChangeLogEntry

logger = logging.getLogger(__name__)


def compute_field_diff(
    stored_content: dict[str, Any],
    updated_content: dict[str, Any],
    author_id: UUID,
) -> list[ChangeLogEntry]:
    """
    Compare `stored_content` against `updated_content` at the top-level field level.

    Args:
        stored_content: The current `Document.content` value (decrypted dict).
        updated_content: The incoming edited content from the PATCH request body.
        author_id: UUID of the authenticated user performing the edit.

    Returns:
        List of `ChangeLogEntry` — one entry per field where
        `updated_content[field] != stored_content.get(field)`.
        Returns an empty list when no fields changed.

    Raises:
        ValueError: If either argument is not a dict.
    """
    if not isinstance(stored_content, dict):
        raise ValueError(f"stored_content must be a dict, got {type(stored_content).__name__}")
    if not isinstance(updated_content, dict):
        raise ValueError(f"updated_content must be a dict, got {type(updated_content).__name__}")

    timestamp = datetime.now(timezone.utc)
    entries: list[ChangeLogEntry] = []

    all_keys = set(stored_content.keys()) | set(updated_content.keys())

    for field in sorted(all_keys):  # Deterministic order for auditability
        old_val = stored_content.get(field)
        new_val = updated_content.get(field)

        if old_val != new_val:
            entries.append(
                ChangeLogEntry(
                    field=field,
                    old_value=old_val,
                    new_value=new_val,
                    author_id=author_id,
                    timestamp=timestamp,
                )
            )
            logger.debug(
                "Change detected in field '%s' by author %s", field, author_id
            )

    return entries


def apply_diff_to_change_log(
    existing_log: list[dict],
    new_entries: list[ChangeLogEntry],
) -> list[dict]:
    """
    Append `new_entries` to the existing `change_log` list.

    Converts `ChangeLogEntry` objects to plain dicts for JSONB storage.
    Preserves existing entries (append-only semantics).

    Args:
        existing_log: Current `Document.change_log` list (may be empty).
        new_entries: New `ChangeLogEntry` objects to append.

    Returns:
        Updated list of dicts ready for JSONB persistence.
    """
    serialised = [
        entry.model_dump(mode="json") for entry in new_entries
    ]
    return existing_log + serialised
