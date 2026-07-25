"""Checklist sub-package — AI-generated handoff checklist orchestration.

Exports:
    ChecklistService — generates HandoffChecklist via Gemini or template fallback.
    ChecklistInput   — PHI-safe input model for checklist generation context.

Design refs:
    ADR-004  — LangChain + Vertex AI structured output
    AIR-021  — minimum-necessary PHI
    US-023   — Generate Context-Aware Handoff Checklist via LLM
"""
from app.checklist.checklist_service import ChecklistInput, ChecklistService

__all__ = ["ChecklistInput", "ChecklistService"]
