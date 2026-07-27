"""
Jinja2 prompt renderer for the Documentation Agent.

Renders the discharge_summary.jinja2 template with PHI-minimised
EncounterContext data. Logs rendered output at DEBUG level to the
audit log sink only — never to the application stdout log.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from agents.documentation.fhir_fetcher import EncounterContext

_TEMPLATES_DIR = Path(__file__).parent / "prompts"

# Audit logger: writes to a separate audit sink (Cloud Logging label: audit=true)
_audit_logger = logging.getLogger("audit.documentation_agent")

# Application logger: PHI-safe — must never log rendered prompt
_logger = logging.getLogger(__name__)


class PromptRenderer:
    """
    Renders Jinja2 prompt templates with PHI-minimised encounter context.

    Attributes:
        _env: Jinja2 Environment configured with StrictUndefined to catch
              template variable mismatches at render time.
    """

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            undefined=StrictUndefined,
            autoescape=False,  # Plain-text prompt; HTML escaping would corrupt clinical text
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_discharge_summary(self, encounter: EncounterContext) -> str:
        """
        Render the discharge summary prompt for a given EncounterContext.

        The rendered prompt is logged at DEBUG level ONLY via the audit logger.
        It is never written to the application log (stdout/stderr).

        Args:
            encounter: PHI-minimised encounter context from FHIREncounterFetcher.

        Returns:
            Rendered prompt string ready for the Vertex AI Gemini API call.

        Raises:
            jinja2.UndefinedError: If the template references a variable not
                present in the EncounterContext (caught by StrictUndefined).
        """
        template = self._env.get_template("discharge_summary.jinja2")
        rendered = template.render(encounter=encounter)

        # Audit log: DEBUG level, routed to audit sink only
        _audit_logger.debug(
            "Discharge summary prompt rendered",
            extra={
                "encounter_id": encounter.encounter_id,
                "prompt_char_length": len(rendered),
                # Full rendered prompt: audit log only, never stdout
                "prompt_preview_audit_only": rendered if os.getenv("AUDIT_LOG_FULL_PROMPT", "false") == "true" else "[REDACTED — set AUDIT_LOG_FULL_PROMPT=true to enable]",
            },
        )
        _logger.info(
            "Prompt rendered for encounter",
            extra={"encounter_id": encounter.encounter_id, "char_length": len(rendered)},
        )
        return rendered
