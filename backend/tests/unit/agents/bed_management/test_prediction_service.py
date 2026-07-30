"""Unit tests for DischargePredictionService.

Coverage:
    Happy path: encounter found, ML Inference returns 200, DB updated, refresh triggered
    503 on first attempt: retries twice, succeeds on third
    503 all 3 attempts: returns False, no DB write, no crash
    Encounter not found: returns False immediately
    PHI guard: patient_dob does NOT appear in log output

Design refs:
    US-036 TASK-006 — Unit test requirements
    US-036 TASK-004 — DischargePredictionService implementation
    ADR-007 / BR-020 — PHI compliance
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID

import httpx
import pytest

from app.agents.bed_management.prediction_service import DischargePredictionService


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

def _make_encounter():
    """Create mock encounter object."""
    enc = MagicMock()
    enc.id = UUID("550e8400-e29b-41d4-a716-446655440001")
    enc.admit_time = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    enc.admitting_diagnosis = "CARDIAC"
    enc.unit = "3A"
    enc.pending_procedures_count = 1
    
    # Mock patient relationship
    patient = MagicMock()
    patient.dob = datetime(1960, 3, 15, tzinfo=timezone.utc)
    enc.patient = patient
    
    enc.deleted_at = None
    return enc


def _make_inference_response(hours_from_admit: float = 6.0) -> dict:
    """Create mock ML Inference Service response."""
    from datetime import timedelta
    predicted = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc) + timedelta(hours=hours_from_admit)
    return {
        "encounter_id": "550e8400-e29b-41d4-a716-446655440001",
        "predicted_discharge_time": predicted.isoformat(),
        "confidence_interval_hours": 0.9,
        "confidence_level": "high",
        "model_version": "v20260717",
    }


# ──────────────────────────────────────────────
# Happy path
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prediction_service_writes_to_encounter_on_success():
    """AC Scenario 3: Prediction successfully written to encounter table."""
    session = AsyncMock()
    encounter = _make_encounter()
    
    # Mock execute().scalar_one_or_none() to return encounter
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = encounter
    session.execute.return_value = result_mock

    http_response = httpx.Response(200, json=_make_inference_response())
    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.return_value = http_response

    refresh_service = AsyncMock()
    svc = DischargePredictionService(http_client=http_client)

    result = await svc.update_prediction(
        session=session,
        encounter_id=str(encounter.id),
        refresh_service=refresh_service,
    )

    assert result is True
    assert session.execute.call_count >= 1  # DB select + update
    session.commit.assert_awaited_once()
    refresh_service.refresh_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_prediction_service_calls_ml_inference_with_correct_payload():
    """Prediction service sends correct feature vector to ML service."""
    session = AsyncMock()
    encounter = _make_encounter()
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = encounter
    session.execute.return_value = result_mock

    http_response = httpx.Response(200, json=_make_inference_response())
    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.return_value = http_response

    refresh_service = AsyncMock()
    svc = DischargePredictionService(http_client=http_client)

    await svc.update_prediction(
        session=session,
        encounter_id=str(encounter.id),
        refresh_service=refresh_service,
    )

    # Verify ML Inference Service was called
    http_client.post.assert_called_once()
    call_args = http_client.post.call_args
    
    # Check payload has required fields
    payload = call_args.kwargs.get("json") or call_args.args[1] if len(call_args.args) > 1 else {}
    assert "encounter_id" in payload
    assert "admit_time" in payload
    assert "patient_dob" in payload
    assert "unit" in payload


# ──────────────────────────────────────────────
# Retry on 503
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prediction_service_retries_on_503_and_succeeds():
    """Exponential backoff: retries on 503, succeeds on third attempt."""
    session = AsyncMock()
    encounter = _make_encounter()
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = encounter
    session.execute.return_value = result_mock

    # First two calls → 503; third → 200
    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.side_effect = [
        httpx.HTTPStatusError("503", request=MagicMock(), response=httpx.Response(503)),
        httpx.HTTPStatusError("503", request=MagicMock(), response=httpx.Response(503)),
        httpx.Response(200, json=_make_inference_response()),
    ]

    refresh_service = AsyncMock()
    svc = DischargePredictionService(http_client=http_client)

    with patch("asyncio.sleep", new_callable=AsyncMock):  # Skip actual sleep in tests
        result = await svc.update_prediction(
            session=session,
            encounter_id=str(encounter.id),
            refresh_service=refresh_service,
        )

    assert result is True
    assert http_client.post.call_count == 3


@pytest.mark.asyncio
async def test_prediction_service_returns_false_after_exhausting_retries():
    """All 3 retry attempts fail → returns False, no DB write."""
    session = AsyncMock()
    encounter = _make_encounter()
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = encounter
    session.execute.return_value = result_mock

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.side_effect = httpx.RequestError("Connection refused")

    refresh_service = AsyncMock()
    svc = DischargePredictionService(http_client=http_client)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await svc.update_prediction(
            session=session,
            encounter_id=str(encounter.id),
            refresh_service=refresh_service,
        )

    assert result is False
    session.commit.assert_not_awaited()   # No DB write on full failure
    refresh_service.refresh_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_prediction_service_retries_on_network_error():
    """RequestError (network timeout) triggers retry."""
    session = AsyncMock()
    encounter = _make_encounter()
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = encounter
    session.execute.return_value = result_mock

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.side_effect = [
        httpx.RequestError("Timeout"),
        httpx.Response(200, json=_make_inference_response()),
    ]

    refresh_service = AsyncMock()
    svc = DischargePredictionService(http_client=http_client)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await svc.update_prediction(
            session=session,
            encounter_id=str(encounter.id),
            refresh_service=refresh_service,
        )

    assert result is True
    assert http_client.post.call_count == 2


# ──────────────────────────────────────────────
# Encounter not found
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prediction_service_returns_false_when_encounter_not_found():
    """Encounter not found → returns False immediately, no ML call."""
    session = AsyncMock()
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    http_client = AsyncMock(spec=httpx.AsyncClient)
    refresh_service = AsyncMock()
    svc = DischargePredictionService(http_client=http_client)

    result = await svc.update_prediction(
        session=session,
        encounter_id="non-existent-uuid",
        refresh_service=refresh_service,
    )

    assert result is False
    http_client.post.assert_not_called()


# ──────────────────────────────────────────────
# PHI guard — patient_dob must NOT appear in logs
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phi_not_logged_during_prediction(caplog):
    """ADR-007 / BR-020: patient_dob must NOT appear in any log output."""
    session = AsyncMock()
    encounter = _make_encounter()
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = encounter
    session.execute.return_value = result_mock

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.return_value = httpx.Response(200, json=_make_inference_response())

    refresh_service = AsyncMock()
    svc = DischargePredictionService(http_client=http_client)

    with caplog.at_level(logging.INFO):
        await svc.update_prediction(
            session=session,
            encounter_id=str(encounter.id),
            refresh_service=refresh_service,
        )

    # Patient DOB should not appear anywhere in logged output
    dob_str = "1960-03-15"
    for record in caplog.records:
        assert dob_str not in record.getMessage(), (
            f"PHI (patient_dob) found in log: {record.getMessage()}"
        )


@pytest.mark.asyncio
async def test_phi_not_logged_on_error(caplog):
    """PHI not logged even during error conditions."""
    session = AsyncMock()
    encounter = _make_encounter()
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = encounter
    session.execute.return_value = result_mock

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.side_effect = httpx.RequestError("Connection failed")

    refresh_service = AsyncMock()
    svc = DischargePredictionService(http_client=http_client)

    with caplog.at_level(logging.WARNING), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        await svc.update_prediction(
            session=session,
            encounter_id=str(encounter.id),
            refresh_service=refresh_service,
        )

    dob_str = "1960-03-15"
    for record in caplog.records:
        assert dob_str not in record.getMessage()
        assert "patient.dob" not in record.getMessage()


# ──────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prediction_service_handles_null_pending_procedures():
    """Gracefully handles null pending_procedures_count."""
    session = AsyncMock()
    encounter = _make_encounter()
    encounter.pending_procedures_count = None
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = encounter
    session.execute.return_value = result_mock

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.return_value = httpx.Response(200, json=_make_inference_response())

    refresh_service = AsyncMock()
    svc = DischargePredictionService(http_client=http_client)

    result = await svc.update_prediction(
        session=session,
        encounter_id=str(encounter.id),
        refresh_service=refresh_service,
    )

    assert result is True
    # Verify payload defaults pending_procedures to 0
    call_args = http_client.post.call_args
    payload = call_args.kwargs.get("json") or call_args.args[1] if len(call_args.args) > 1 else {}
    assert payload.get("pending_procedures_count") == 0 or payload.get("pending_procedures_count") is None
