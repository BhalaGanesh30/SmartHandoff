"""Unit tests for CarePathwayService.

Tests:
    - activate_pathway() creates appointment with correct type/target_date/status for each tier
    - HIGH tier: assigned_user_id populated from round-robin care manager pool
    - MEDIUM/LOW tier: assigned_user_id is None (no care manager required)
    - _assign_care_manager() returns None gracefully when pool is empty
    - Deterministic round-robin: same encounter_id always yields same pool_index
"""
from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.care_pathways import load_care_pathways
from app.services.care_pathway_service import CarePathwayService


@pytest.fixture()
def pathways():
    return load_care_pathways()


@pytest.fixture()
def service(pathways):
    return CarePathwayService(pathways=pathways)


@pytest.fixture()
def mock_encounter():
    enc = MagicMock()
    enc.id = uuid.uuid4()
    enc.unit = "ICU-West"
    enc.discharge_date = MagicMock()
    return enc


@pytest.fixture()
def discharge_date():
    return date(2026, 7, 20)


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


class TestActivatePathwayHigh:
    async def test_high_appointment_type(self, service, mock_encounter, discharge_date, mock_db):
        with patch.object(service, "_assign_care_manager", new=AsyncMock(return_value=uuid.uuid4())):
            appointment = await service.activate_pathway(
                encounter=mock_encounter, risk_tier="HIGH", discharge_date=discharge_date, db=mock_db
            )
        assert appointment.appointment_type == "HIGH_RISK_FOLLOW_UP"

    async def test_high_target_date_is_7_days(self, service, mock_encounter, discharge_date, mock_db):
        from datetime import timedelta
        expected_date = discharge_date + timedelta(days=7)
        with patch.object(service, "_assign_care_manager", new=AsyncMock(return_value=uuid.uuid4())):
            appointment = await service.activate_pathway(
                encounter=mock_encounter, risk_tier="HIGH", discharge_date=discharge_date, db=mock_db
            )
        assert appointment.target_date == expected_date

    async def test_high_status_is_scheduled(self, service, mock_encounter, discharge_date, mock_db):
        with patch.object(service, "_assign_care_manager", new=AsyncMock(return_value=uuid.uuid4())):
            appointment = await service.activate_pathway(
                encounter=mock_encounter, risk_tier="HIGH", discharge_date=discharge_date, db=mock_db
            )
        assert appointment.status == "SCHEDULED"

    async def test_high_assigned_user_id_populated(self, service, mock_encounter, discharge_date, mock_db):
        care_manager_id = uuid.uuid4()
        with patch.object(service, "_assign_care_manager", new=AsyncMock(return_value=care_manager_id)):
            appointment = await service.activate_pathway(
                encounter=mock_encounter, risk_tier="HIGH", discharge_date=discharge_date, db=mock_db
            )
        assert appointment.assigned_user_id == care_manager_id


class TestActivatePathwayMedium:
    async def test_medium_appointment_type(self, service, mock_encounter, discharge_date, mock_db):
        appointment = await service.activate_pathway(
            encounter=mock_encounter, risk_tier="MEDIUM", discharge_date=discharge_date, db=mock_db
        )
        assert appointment.appointment_type == "STANDARD_FOLLOW_UP"

    async def test_medium_target_date_is_14_days(self, service, mock_encounter, discharge_date, mock_db):
        from datetime import timedelta
        expected_date = discharge_date + timedelta(days=14)
        appointment = await service.activate_pathway(
            encounter=mock_encounter, risk_tier="MEDIUM", discharge_date=discharge_date, db=mock_db
        )
        assert appointment.target_date == expected_date

    async def test_medium_assigned_user_id_is_none(self, service, mock_encounter, discharge_date, mock_db):
        appointment = await service.activate_pathway(
            encounter=mock_encounter, risk_tier="MEDIUM", discharge_date=discharge_date, db=mock_db
        )
        assert appointment.assigned_user_id is None


class TestActivatePathwayLow:
    async def test_low_appointment_type(self, service, mock_encounter, discharge_date, mock_db):
        appointment = await service.activate_pathway(
            encounter=mock_encounter, risk_tier="LOW", discharge_date=discharge_date, db=mock_db
        )
        assert appointment.appointment_type == "ROUTINE_FOLLOW_UP"

    async def test_low_target_date_is_30_days(self, service, mock_encounter, discharge_date, mock_db):
        from datetime import timedelta
        expected_date = discharge_date + timedelta(days=30)
        appointment = await service.activate_pathway(
            encounter=mock_encounter, risk_tier="LOW", discharge_date=discharge_date, db=mock_db
        )
        assert appointment.target_date == expected_date

    async def test_low_assigned_user_id_is_none(self, service, mock_encounter, discharge_date, mock_db):
        appointment = await service.activate_pathway(
            encounter=mock_encounter, risk_tier="LOW", discharge_date=discharge_date, db=mock_db
        )
        assert appointment.assigned_user_id is None


class TestAssignCareManager:
    async def test_returns_none_when_pool_is_empty(self, service, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service._assign_care_manager(
            encounter_id=uuid.uuid4(), unit="ICU-West", db=mock_db
        )
        assert result is None

    async def test_deterministic_round_robin_single_manager(self, service, mock_db):
        manager_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [manager_id]
        mock_db.execute = AsyncMock(return_value=mock_result)

        encounter_id = uuid.uuid4()
        result1 = await service._assign_care_manager(encounter_id, "ICU", mock_db)
        result2 = await service._assign_care_manager(encounter_id, "ICU", mock_db)
        assert result1 == result2 == manager_id

    async def test_deterministic_round_robin_pool_of_three(self, service, mock_db):
        ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ids
        mock_db.execute = AsyncMock(return_value=mock_result)

        encounter_id = uuid.uuid4()
        expected_index = hash(str(encounter_id)) % 3
        result = await service._assign_care_manager(encounter_id, "ED", mock_db)
        assert result == ids[expected_index]
