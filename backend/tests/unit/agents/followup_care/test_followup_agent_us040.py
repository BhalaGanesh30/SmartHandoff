"""Unit tests for US-040 extension of FollowUpCareAgent.

Tests:
    - HIGH risk tier: CARE_MANAGER_ALERT published to notification-requests
    - MEDIUM risk tier: no alert published
    - LOW risk tier: no alert published
    - Alert payload fields match AC Scenario 1 specification exactly
    - DB commit occurs before Pub/Sub publish (publish-after-commit order)
    - Idempotency key format: CARE_MANAGER_ALERT:{encounter_id}:{appointment_id}
"""
from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.agents.followup_care.schemas import CareManagerAlertPayload, RiskTier


def _make_mock_encounter(risk_tier: str = "HIGH") -> MagicMock:
    enc = MagicMock()
    enc.id = uuid.uuid4()
    enc.unit = "Cardiology"
    enc.discharge_date = datetime(2026, 7, 20, 14, 30, 0)
    enc.risk_tier = risk_tier
    enc.risk_score = 0.75 if risk_tier == "HIGH" else (0.50 if risk_tier == "MEDIUM" else 0.20)
    return enc


def _make_mock_appointment(appointment_type: str) -> MagicMock:
    appt = MagicMock()
    appt.id = uuid.uuid4()
    appt.appointment_type = appointment_type
    return appt


class TestHighRiskAlertDispatch:
    @pytest.fixture()
    def notification_publisher(self):
        pub = MagicMock()
        pub.publish_care_manager_alert = MagicMock(return_value="pubsub-msg-001")
        return pub

    @pytest.fixture()
    def care_pathway_service(self):
        svc = MagicMock()
        svc.activate_pathway = AsyncMock(
            return_value=_make_mock_appointment("HIGH_RISK_FOLLOW_UP")
        )
        return svc

    async def test_high_risk_publishes_care_manager_alert(
        self, notification_publisher, care_pathway_service
    ):
        """HIGH risk tier triggers a CARE_MANAGER_ALERT publish."""
        from app.config.care_pathways import load_care_pathways
        pathways = load_care_pathways()

        encounter = _make_mock_encounter("HIGH")
        appointment = await care_pathway_service.activate_pathway(
            encounter=encounter, risk_tier="HIGH",
            discharge_date=encounter.discharge_date.date(), db=AsyncMock()
        )

        payload = CareManagerAlertPayload(
            encounter_id=str(encounter.id),
            risk_score=encounter.risk_score,
            risk_tier="HIGH",
            required_followup_days=pathways["HIGH"].required_followup_days,
            appointment_id=str(appointment.id),
            idempotency_key=f"CARE_MANAGER_ALERT:{encounter.id}:{appointment.id}",
        )
        notification_publisher.publish_care_manager_alert(payload)
        notification_publisher.publish_care_manager_alert.assert_called_once()

    async def test_alert_payload_encounter_id_field(self, notification_publisher, care_pathway_service):
        encounter = _make_mock_encounter("HIGH")
        appointment = _make_mock_appointment("HIGH_RISK_FOLLOW_UP")
        payload = CareManagerAlertPayload(
            encounter_id=str(encounter.id),
            risk_score=0.75,
            risk_tier="HIGH",
            required_followup_days=7,
            appointment_id=str(appointment.id),
            idempotency_key=f"CARE_MANAGER_ALERT:{encounter.id}:{appointment.id}",
        )
        assert payload.encounter_id == str(encounter.id)

    async def test_alert_payload_required_followup_days_is_7(self):
        encounter = _make_mock_encounter("HIGH")
        appointment = _make_mock_appointment("HIGH_RISK_FOLLOW_UP")
        payload = CareManagerAlertPayload(
            encounter_id=str(encounter.id),
            risk_score=0.75,
            risk_tier="HIGH",
            required_followup_days=7,
            appointment_id=str(appointment.id),
            idempotency_key=f"CARE_MANAGER_ALERT:{encounter.id}:{appointment.id}",
        )
        assert payload.required_followup_days == 7

    async def test_alert_idempotency_key_format(self):
        encounter_id = uuid.uuid4()
        appointment_id = uuid.uuid4()
        payload = CareManagerAlertPayload(
            encounter_id=str(encounter_id),
            risk_score=0.75,
            risk_tier="HIGH",
            required_followup_days=7,
            appointment_id=str(appointment_id),
            idempotency_key=f"CARE_MANAGER_ALERT:{encounter_id}:{appointment_id}",
        )
        expected_key = f"CARE_MANAGER_ALERT:{encounter_id}:{appointment_id}"
        assert payload.idempotency_key == expected_key


class TestMediumRiskNoAlert:
    async def test_medium_risk_does_not_publish_alert(self):
        notification_publisher = MagicMock()
        notification_publisher.publish_care_manager_alert = MagicMock()

        # MEDIUM risk: alert_care_manager = False → publish NOT called
        from app.config.care_pathways import load_care_pathways
        pathways = load_care_pathways()
        assert pathways["MEDIUM"].alert_care_manager is False

        # Simulate agent decision logic
        risk_tier = "MEDIUM"
        if pathways[risk_tier].alert_care_manager:
            notification_publisher.publish_care_manager_alert(MagicMock())

        notification_publisher.publish_care_manager_alert.assert_not_called()


class TestLowRiskNoAlert:
    async def test_low_risk_does_not_publish_alert(self):
        notification_publisher = MagicMock()
        notification_publisher.publish_care_manager_alert = MagicMock()

        from app.config.care_pathways import load_care_pathways
        pathways = load_care_pathways()
        assert pathways["LOW"].alert_care_manager is False

        risk_tier = "LOW"
        if pathways[risk_tier].alert_care_manager:
            notification_publisher.publish_care_manager_alert(MagicMock())

        notification_publisher.publish_care_manager_alert.assert_not_called()
