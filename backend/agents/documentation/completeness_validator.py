"""
CompletenessValidator — stateless required-field checker for discharge documents.

Reads required fields from CompletenessConfig (TASK-026-001) and evaluates
whether a generated document contains all non-null, non-empty values for every
required field. Returns a CompletenessResult value object.

Design constraints:
- Pure function object: no I/O, no DB session, no LLM calls.
- Both None and empty string/list values are treated as missing (US-026 Technical Notes).
- The required_fields list is sourced from YAML config — adding a field requires no
  code change (US-026 Scenario 3).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from config.completeness_config import CompletenessConfig, get_completeness_config

logger = logging.getLogger(__name__)


class CompletenessStatus(str, Enum):
    """Document completeness verdict."""
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class CompletenessResult:
    """
    Immutable value object returned by CompletenessValidator.

    Attributes:
        status: COMPLETE if all required fields are present and non-empty;
                INCOMPLETE otherwise.
        missing_fields: Ordered list of field names that are null or empty.
                        Empty list when status is COMPLETE.
    """
    status: CompletenessStatus
    missing_fields: List[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """Convenience predicate — True when status is COMPLETE."""
        return self.status == CompletenessStatus.COMPLETE


def _is_absent(value: Any) -> bool:
    """
    Return True if the field value should be considered missing.

    Rules (US-026 Technical Notes):
    - None → missing
    - Empty string ("") → missing
    - Empty list ([]) → missing
    - Any other value (non-empty string, non-empty list, dict, int, bool) → present
    """
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


class CompletenessValidator:
    """
    Validates discharge document completeness against a configurable required-field list.

    Args:
        config: CompletenessConfig instance. Defaults to the module-level cached singleton.
        document_type: The document type key used to look up the required fields in config.
                       Defaults to 'discharge_summary'.
    """

    def __init__(
        self,
        config: CompletenessConfig | None = None,
        document_type: str = "discharge_summary",
    ) -> None:
        self._config = config or get_completeness_config()
        self._document_type = document_type
        self._required_fields: List[str] = self._config.get_required_fields(document_type)
        logger.debug(
            "CompletenessValidator initialised: document_type=%s required_fields=%s",
            document_type,
            self._required_fields,
        )

    def validate(self, document_data: Dict[str, Any]) -> CompletenessResult:
        """
        Evaluate whether the document contains all required fields.

        Args:
            document_data: Dict representation of the document. Typically obtained
                           via `summary.model_dump()` from a DischargeSummarySchema.

        Returns:
            CompletenessResult with COMPLETE status and empty missing_fields list,
            or INCOMPLETE status with the list of absent field names.
        """
        missing: List[str] = []

        for field_name in self._required_fields:
            value = document_data.get(field_name)
            if _is_absent(value):
                missing.append(field_name)
                logger.debug("CompletenessValidator: field '%s' is absent or empty", field_name)

        if missing:
            logger.info(
                "CompletenessValidator: document INCOMPLETE — missing_fields=%s",
                missing,
            )
            return CompletenessResult(
                status=CompletenessStatus.INCOMPLETE,
                missing_fields=missing,
            )

        logger.info("CompletenessValidator: document COMPLETE")
        return CompletenessResult(status=CompletenessStatus.COMPLETE, missing_fields=[])
