"""StructuredOutputHelper — LangChain + Vertex AI structured output wrapper.

Provides a single ``invoke_structured()`` method that wraps the LangChain
``ChatVertexAI.with_structured_output(PydanticModel)`` pattern used by all
specialist agents to generate validated Pydantic instances from Gemini.

Timeout behaviour (TR-004):
    Default ``timeout=25.0`` seconds. Callers should implement a template
    fallback if ``RetryableError`` is raised after timeout expiry.

Design refs:
    ADR-004 — LangChain + Vertex AI Gemini; structured output via Pydantic
    TR-004  — AI agent document generation <30 s; timeout at 25 s
    TR-006  — chatbot <3 s; use Gemini Flash model name
    US-024  — structured output helper; Pydantic schema validation
"""
from __future__ import annotations

import logging
from typing import Any, TypeVar

import httpx
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, ValidationError

from app.base.errors import NonRetryableError, RetryableError

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=BaseModel)

# Default model names — callers may override (ADR-004, TR-006)
DEFAULT_MODEL_NAME = "gemini-1.5-pro"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TIMEOUT_SECONDS = 25.0


class StructuredOutputHelper:
    """Invokes Vertex AI Gemini via LangChain with enforced Pydantic schema.

    Args:
        model_name: Vertex AI model identifier. Defaults to
            ``"gemini-1.5-pro"`` for document agents; use
            ``"gemini-1.5-flash"`` for chatbot agent (TR-006).
        temperature: Sampling temperature. Default ``0.0`` for deterministic
            clinical output.
        timeout: Request timeout in seconds. Default 25 s (TR-004).
        project: GCP project ID. If ``None``, resolved from ADC credentials.
        location: GCP region. Defaults to ``"us-central1"``.

    Example::

        helper = StructuredOutputHelper(model_name="gemini-1.5-pro")
        output: DischargeSummaryOutput = await helper.invoke_structured(
            prompt="Generate discharge summary for...",
            output_schema=DischargeSummaryOutput,
        )
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        project: str | None = None,
        location: str = "us-central1",
    ) -> None:
        self._model_name = model_name
        self._temperature = temperature
        self._timeout = timeout
        self._project = project
        self._location = location

    async def invoke_structured(
        self,
        prompt: str,
        output_schema: type[_T],
    ) -> _T:
        """Invoke Vertex AI Gemini and return a validated Pydantic instance.

        Builds a LangChain ``ChatVertexAI | with_structured_output(output_schema)``
        chain, invokes it with ``prompt``, then validates the response.

        Args:
            prompt: Fully rendered prompt string (Jinja2 template output or
                inline string). Must NOT contain raw PHI — use minimum-necessary
                clinical identifiers (ICD-10 codes, encounter UUIDs).
            output_schema: Pydantic ``BaseModel`` subclass defining the
                expected response structure.

        Returns:
            Validated instance of ``output_schema``.

        Raises:
            RetryableError: On Vertex AI HTTP 429 (rate limit), connection
                timeout, or transient network error.
            NonRetryableError: On Pydantic ``ValidationError`` (schema
                mismatch) or unexpected LLM response format.
        """
        llm = ChatVertexAI(
            model_name=self._model_name,
            temperature=self._temperature,
            project=self._project,
            location=self._location,
            request_timeout=self._timeout,
        )
        chain = llm.with_structured_output(output_schema)

        try:
            result = await chain.ainvoke(prompt)
        except httpx.TimeoutException as exc:
            raise RetryableError(
                f"Vertex AI request timed out after {self._timeout}s",
                error_detail={"model": self._model_name, "timeout": self._timeout},
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RetryableError(
                    "Vertex AI rate limit (HTTP 429)",
                    error_detail={
                        "model": self._model_name,
                        "status_code": 429,
                    },
                ) from exc
            raise NonRetryableError(
                f"Vertex AI HTTP error {exc.response.status_code}",
                error_detail={
                    "model": self._model_name,
                    "status_code": exc.response.status_code,
                },
            ) from exc
        except Exception as exc:
            raise RetryableError(
                f"Vertex AI transient error: {type(exc).__name__}",
                error_detail={"model": self._model_name, "error": str(exc)},
            ) from exc

        # Validate response schema
        if not isinstance(result, output_schema):
            raise NonRetryableError(
                f"LLM response failed Pydantic validation for {output_schema.__name__}",
                error_detail={
                    "expected_schema": output_schema.__name__,
                    "received_type": type(result).__name__,
                },
            )

        logger.info(
            "structured_output_success",
            extra={
                "model": self._model_name,
                "output_schema": output_schema.__name__,
            },
        )
        return result  # type: ignore[return-value]
