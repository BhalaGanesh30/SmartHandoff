"""Unit tests for ChecklistService — LLM success, timeout fallback, error fallback.

Design refs: US-023 AC Scenarios 1, 4; ADR-004; AIR-021
"""
from __future__ import annotations

import asyncio
import os
import unittest.mock

import pytest
import pytest_asyncio

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

from app.checklist import ChecklistInput, ChecklistService
from app.models.handoff_checklist import ChecklistItem, HandoffChecklist


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service() -> ChecklistService:
    return ChecklistService(timeout_sec=5)


@pytest.fixture()
def discharge_input() -> ChecklistInput:
    """US-023 AC Scenario 1 — discharge with T2D and Heart Failure."""
    return ChecklistInput(
        encounter_id="ENC-001",
        diagnosis_codes=["E11.9", "I50.9"],
        unit_name="Med-Surg 4B",
        transition_type="A03",
        medication_names=["Metformin", "Furosemide"],
    )


def _make_llm_checklist(count: int = 3) -> HandoffChecklist:
    """Helper: build a HandoffChecklist simulating an LLM response."""
    items = [
        ChecklistItem(
            item=f"Verify clinical care item {i} completed before discharge",
            category="documentation",
            priority="HIGH",
        )
        for i in range(count)
    ]
    return HandoffChecklist(
        checklist=items,
        generated_type="LLM",
        transition_type="A03",
    )


# ---------------------------------------------------------------------------
# LLM success path (US-023 AC Scenario 1)
# ---------------------------------------------------------------------------


class TestChecklistServiceLLMSuccess:
    @pytest.mark.asyncio()
    async def test_generate_returns_llm_type_on_success(
        self, service: ChecklistService, discharge_input: ChecklistInput
    ) -> None:
        mock_result = _make_llm_checklist(count=4)

        with unittest.mock.patch.object(
            service, "_call_gemini", return_value=mock_result
        ):
            result = await service.generate(discharge_input)

        assert result.generated_type == "LLM"
        assert len(result.checklist) >= 3

    @pytest.mark.asyncio()
    async def test_generate_passes_correct_transition_type(
        self, service: ChecklistService, discharge_input: ChecklistInput
    ) -> None:
        mock_result = _make_llm_checklist()
        captured_input: list[ChecklistInput] = []

        async def mock_call(ctx: ChecklistInput) -> HandoffChecklist:
            captured_input.append(ctx)
            return mock_result

        with unittest.mock.patch.object(service, "_call_gemini", mock_call):
            await service.generate(discharge_input)

        assert captured_input[0].transition_type == "A03"


# ---------------------------------------------------------------------------
# Timeout fallback (US-023 AC Scenario 4)
# ---------------------------------------------------------------------------


class TestChecklistServiceTimeoutFallback:
    @pytest.mark.asyncio()
    async def test_timeout_returns_template_type(
        self, service: ChecklistService, discharge_input: ChecklistInput
    ) -> None:
        """US-023 AC Scenario 4 — 15s timeout fires → TEMPLATE fallback."""

        async def _slow_gemini(_ctx: ChecklistInput) -> HandoffChecklist:
            await asyncio.sleep(999)  # Will always time out
            return _make_llm_checklist()

        with unittest.mock.patch.object(service, "_call_gemini", _slow_gemini):
            result = await service.generate(discharge_input)

        assert result.generated_type == "TEMPLATE"

    @pytest.mark.asyncio()
    async def test_timeout_fallback_has_minimum_three_items(
        self, service: ChecklistService, discharge_input: ChecklistInput
    ) -> None:
        async def _slow_gemini(_ctx: ChecklistInput) -> HandoffChecklist:
            await asyncio.sleep(999)
            return _make_llm_checklist()

        with unittest.mock.patch.object(service, "_call_gemini", _slow_gemini):
            result = await service.generate(discharge_input)

        assert len(result.checklist) >= 3

    @pytest.mark.asyncio()
    async def test_timeout_fallback_transition_type_matches_input(
        self, service: ChecklistService, discharge_input: ChecklistInput
    ) -> None:
        async def _slow_gemini(_ctx: ChecklistInput) -> HandoffChecklist:
            await asyncio.sleep(999)
            return _make_llm_checklist()

        with unittest.mock.patch.object(service, "_call_gemini", _slow_gemini):
            result = await service.generate(discharge_input)

        assert result.transition_type == "A03"

    @pytest.mark.asyncio()
    async def test_error_in_gemini_returns_template_fallback(
        self, service: ChecklistService, discharge_input: ChecklistInput
    ) -> None:
        async def _error_gemini(_ctx: ChecklistInput) -> HandoffChecklist:
            raise RuntimeError("Vertex AI unavailable")

        with unittest.mock.patch.object(service, "_call_gemini", _error_gemini):
            result = await service.generate(discharge_input)

        assert result.generated_type == "TEMPLATE"


# ---------------------------------------------------------------------------
# Template fallback — direct load tests
# ---------------------------------------------------------------------------


class TestChecklistServiceTemplateFallback:
    @pytest.mark.parametrize("transition_type", ["A01", "A02", "A03"])
    def test_all_adt_transitions_have_fallback(
        self, service: ChecklistService, transition_type: str
    ) -> None:
        ctx = ChecklistInput(
            encounter_id="ENC-TEST",
            diagnosis_codes=["Z99.99"],
            unit_name="Test Unit",
            transition_type=transition_type,
        )
        result = service._load_template_fallback(ctx)
        assert result.generated_type == "TEMPLATE"
        assert len(result.checklist) >= 3

    def test_unknown_transition_type_uses_default(self, service: ChecklistService) -> None:
        ctx = ChecklistInput(
            encounter_id="ENC-TEST",
            diagnosis_codes=["Z99.99"],
            unit_name="Test Unit",
            transition_type="A99",  # Unknown
        )
        result = service._load_template_fallback(ctx)
        assert result.generated_type == "TEMPLATE"
        assert len(result.checklist) >= 1
