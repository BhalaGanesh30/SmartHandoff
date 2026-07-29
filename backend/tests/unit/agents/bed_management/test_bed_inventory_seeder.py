"""Unit tests for BedInventorySeeder (seeder.py).

Coverage:
  SC-4: First-run inserts all 200 beds (rowcount returned correctly)
  SC-4: Second-run is idempotent — returns 0 new inserts
  SC-4: mv_bed_board refresh triggered after seeding
  DoD: FileNotFoundError on missing YAML
  DoD: Pydantic ValidationError on malformed YAML

Design refs:
    US-035 TASK-006 — Unit test coverage for seeder.py
    US-035 TASK-003 — BedInventorySeeder implementation
"""
from __future__ import annotations

import pathlib
import pytest
from unittest.mock import AsyncMock, MagicMock
import yaml

from app.agents.bed_management.seeder import BedInventorySeeder
from app.agents.bed_management.refresh_service import BedBoardRefreshService


@pytest.fixture
def valid_yaml_path(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a minimal valid bed_inventory.yaml for testing."""
    config = {
        "units": [
            {
                "unit": "3A",
                "beds": [
                    {
                        "room": "301",
                        "bed_number": "A",
                        "bed_type": "MEDICAL",
                        "isolation_required": False,
                        "gender_designation": "ANY",
                    },
                    {
                        "room": "301",
                        "bed_number": "B",
                        "bed_type": "MEDICAL",
                        "isolation_required": False,
                        "gender_designation": "ANY",
                    },
                ],
            }
        ]
    }
    p = tmp_path / "bed_inventory.yaml"
    p.write_text(yaml.dump(config))
    return p


@pytest.fixture
def invalid_yaml_path(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create an invalid YAML file (missing required field)."""
    config = {
        "units": [
            {
                "unit": "3A",
                "beds": [
                    {
                        "room": "301",
                        # missing bed_number
                        "bed_type": "MEDICAL",
                        "isolation_required": False,
                        "gender_designation": "ANY",
                    },
                ],
            }
        ]
    }
    p = tmp_path / "invalid_bed_inventory.yaml"
    p.write_text(yaml.dump(config))
    return p


@pytest.fixture
def mock_refresh_service():
    """Mock BedBoardRefreshService."""
    svc = MagicMock(spec=BedBoardRefreshService)
    svc.refresh_sync = AsyncMock()
    return svc


@pytest.fixture
def mock_session_factory():
    """Session mock where each INSERT returns rowcount=1."""
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.rowcount = 1
    session.execute.return_value = execute_result
    session.commit = AsyncMock()

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


@pytest.fixture
def mock_session_factory_no_inserts():
    """Session mock where INSERT returns rowcount=0 (all conflicts)."""
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.rowcount = 0  # All rows already exist
    session.execute.return_value = execute_result
    session.commit = AsyncMock()

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 4: First-run insertion
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_inserts_beds_on_first_run(
    valid_yaml_path, mock_refresh_service, mock_session_factory
):
    """First run inserts all beds from YAML config."""
    seeder = BedInventorySeeder(
        session_factory=mock_session_factory,
        refresh_service=mock_refresh_service,
        config_path=valid_yaml_path,
    )
    inserted = await seeder.seed()

    assert inserted == 2  # 2 beds in the minimal YAML fixture
    mock_refresh_service.refresh_sync.assert_awaited_once()


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 4: Idempotency on second run
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_is_idempotent_on_second_run(
    valid_yaml_path, mock_refresh_service, mock_session_factory_no_inserts
):
    """ON CONFLICT DO NOTHING returns rowcount=0 on conflict."""
    seeder = BedInventorySeeder(
        session_factory=mock_session_factory_no_inserts,
        refresh_service=mock_refresh_service,
        config_path=valid_yaml_path,
    )
    inserted = await seeder.seed()

    assert inserted == 0
    mock_refresh_service.refresh_sync.assert_awaited_once()


# ──────────────────────────────────────────────────────────────────────────────
# mv_bed_board refresh triggered
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_triggers_mv_refresh(
    valid_yaml_path, mock_refresh_service, mock_session_factory
):
    """Seeding triggers mv_bed_board refresh via refresh_sync()."""
    seeder = BedInventorySeeder(
        session_factory=mock_session_factory,
        refresh_service=mock_refresh_service,
        config_path=valid_yaml_path,
    )
    await seeder.seed()

    # Seeder uses refresh_sync (blocking) not refresh_async
    mock_refresh_service.refresh_sync.assert_awaited_once()


# ──────────────────────────────────────────────────────────────────────────────
# Error handling
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_raises_file_not_found(mock_refresh_service):
    """Missing YAML config file raises FileNotFoundError."""
    factory = MagicMock()
    seeder = BedInventorySeeder(
        session_factory=factory,
        refresh_service=mock_refresh_service,
        config_path=pathlib.Path("/nonexistent/bed_inventory.yaml"),
    )
    with pytest.raises(FileNotFoundError):
        await seeder.seed()


@pytest.mark.asyncio
async def test_seed_raises_validation_error_on_invalid_yaml(
    invalid_yaml_path, mock_refresh_service, mock_session_factory
):
    """Malformed YAML (missing required field) raises ValidationError."""
    from pydantic import ValidationError
    
    seeder = BedInventorySeeder(
        session_factory=mock_session_factory,
        refresh_service=mock_refresh_service,
        config_path=invalid_yaml_path,
    )
    
    with pytest.raises(ValidationError):
        await seeder.seed()


# ──────────────────────────────────────────────────────────────────────────────
# YAML parsing
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_loads_multiple_units(
    tmp_path, mock_refresh_service, mock_session_factory
):
    """Seed correctly parses YAML with multiple units."""
    config = {
        "units": [
            {
                "unit": "3A",
                "beds": [
                    {
                        "room": "301",
                        "bed_number": "A",
                        "bed_type": "MEDICAL",
                        "isolation_required": False,
                        "gender_designation": "ANY",
                    },
                ],
            },
            {
                "unit": "ICU",
                "beds": [
                    {
                        "room": "ICU-1",
                        "bed_number": "1",
                        "bed_type": "ICU",
                        "isolation_required": True,
                        "gender_designation": "ANY",
                    },
                    {
                        "room": "ICU-1",
                        "bed_number": "2",
                        "bed_type": "ICU",
                        "isolation_required": True,
                        "gender_designation": "ANY",
                    },
                ],
            },
        ]
    }
    p = tmp_path / "multi_unit.yaml"
    p.write_text(yaml.dump(config))
    
    seeder = BedInventorySeeder(
        session_factory=mock_session_factory,
        refresh_service=mock_refresh_service,
        config_path=p,
    )
    inserted = await seeder.seed()
    
    assert inserted == 3  # 1 bed in 3A + 2 beds in ICU
