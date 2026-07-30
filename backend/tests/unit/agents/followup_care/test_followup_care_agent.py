"""Unit tests for FollowUpCareAgent A03 processing."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.followup_care.agent import FollowUpCareAgent
from app.agents.followup_care.schemas import RiskTier
from app.agents.base_agent import RetryableError


SAMPLE_INFERENCE_RESPONSE = {
    "risk_score": 0.72,
    "risk_tier": "HIGH",
    "model_version": "1.0.0",
    "contributing_factors": [
        {"feature": "Prior Hospital Admissions (12 Months)", "shap_value": 0.35,
         "feature_value": 2.0, "direction": "increases_risk"},
    ],
}


@pytest.fixture
def agent():
    return FollowUpCareAgent(
        db_session_factory=AsyncMock(),
        read_session_factory=AsyncMock(),
        fhir_client=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_agent_returns_none_for_non_a03_events(agent):
    message = {"event_type": "A01", "encounter_id": "enc-uuid-001"}
    result = await agent.process(message)
    assert result is None


@pytest.mark.asyncio
async def test_agent_returns_none_for_a02_events(agent):
    message = {"event_type": "A02", "encounter_id": "enc-uuid-001", "bed_id": "bed-001", "previous_bed_id": "bed-002"}
    result = await agent.process(message)
    assert result is None


@pytest.mark.asyncio
async def test_a03_updates_encounter_risk_score(agent):
    message = {"event_type": "A03", "encounter_id": "enc-uuid-001"}

    with (
        patch(
            "app.agents.followup_care.agent.extract_features",
            new=AsyncMock(return_value={"age": 72.0, "los_days": 6.0, "num_comorbidities": 4.0,
                                        "num_prior_admissions_12mo": 2.0, "medication_count": 8.0,
                                        "discharge_disposition": 1.0, "primary_diagnosis_group": 0.0}),
        ),
        patch(
            "app.agents.followup_care.agent.call_readmission_inference",
            new=AsyncMock(return_value=SAMPLE_INFERENCE_RESPONSE),
        ),
    ):
        result = await agent.process(message)

    assert result is not None
    assert result.risk_score == pytest.approx(0.72)
    assert result.risk_tier == RiskTier.HIGH
    assert result.db_updated is True


@pytest.mark.asyncio
async def test_a03_creates_agent_task_record(agent):
    message = {"event_type": "A03", "encounter_id": "enc-uuid-001"}

    with (
        patch(
            "app.agents.followup_care.agent.extract_features",
            new=AsyncMock(return_value={"age": 65.0, "los_days": 3.0, "num_comorbidities": 1.0,
                                        "num_prior_admissions_12mo": 0.0, "medication_count": 3.0,
                                        "discharge_disposition": 0.0, "primary_diagnosis_group": 1.0}),
        ),
        patch(
            "app.agents.followup_care.agent.call_readmission_inference",
            new=AsyncMock(return_value=SAMPLE_INFERENCE_RESPONSE),
        ),
    ):
        result = await agent.process(message)

    assert result.agent_task_id is not None


@pytest.mark.asyncio
async def test_db_failure_raises_retryable_error(agent):
    message = {"event_type": "A03", "encounter_id": "enc-uuid-001"}

    # Make the write session raise an exception to simulate DB failure
    failing_session = AsyncMock()
    failing_session.__aenter__ = AsyncMock(return_value=failing_session)
    failing_session.__aexit__ = AsyncMock(return_value=None)
    failing_session.execute = AsyncMock(side_effect=Exception("DB connection refused"))
    agent._db_session_factory = MagicMock(return_value=failing_session)

    with (
        patch(
            "app.agents.followup_care.agent.extract_features",
            new=AsyncMock(return_value={"age": 72.0, "los_days": 6.0, "num_comorbidities": 4.0,
                                        "num_prior_admissions_12mo": 2.0, "medication_count": 8.0,
                                        "discharge_disposition": 1.0, "primary_diagnosis_group": 0.0}),
        ),
        patch(
            "app.agents.followup_care.agent.call_readmission_inference",
            new=AsyncMock(return_value=SAMPLE_INFERENCE_RESPONSE),
        ),
    ):
        with pytest.raises(RetryableError, match="DB write failed"):
            await agent.process(message)
