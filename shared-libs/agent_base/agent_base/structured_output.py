"""Structured output enforcement mixin for LangChain + Vertex AI agents.

Provides ``invoke_structured()`` which calls a LangChain chain and validates
the response against a Pydantic v2 schema. On validation failure, the raw
response is logged and a ``StructuredOutputError`` is raised.

Design refs:
    ADR-004  — structured output enforced via Pydantic schemas
    FR-020   — discharge summaries must match defined document schema
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """Raised when LLM response cannot be validated against the target schema."""


class StructuredOutputMixin:
    """Mixin that adds ``invoke_structured()`` to a LangChain agent class."""

    async def invoke_structured(
        self,
        chain: "Runnable",
        schema: type[T],
        inputs: dict,
    ) -> T:
        """Invoke ``chain`` and validate the output against ``schema``.

        Args:
            chain: LangChain runnable (prompt | llm | parser).
            schema: Pydantic v2 model class for output validation.
            inputs: Input dict passed to ``chain.ainvoke()``.

        Returns:
            Validated instance of ``schema``.

        Raises:
            StructuredOutputError: If the LLM response fails Pydantic validation.
        """
        raw = await chain.ainvoke(inputs)
        try:
            return schema.model_validate(raw if isinstance(raw, dict) else raw.dict())
        except (ValidationError, AttributeError) as exc:
            logger.error(
                "structured_output_validation_failed",
                extra={
                    "schema": schema.__name__,
                    "error": str(exc),
                },
            )
            raise StructuredOutputError(
                f"LLM output failed {schema.__name__} validation: {exc}"
            ) from exc
