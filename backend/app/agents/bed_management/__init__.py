"""BedManagementAgent package — ADT event-driven bed status state machine.

Subscribes to adt-events Pub/Sub topic and updates bed status based on A01/A02/A03 events.

Modules:
    agent — BedManagementAgent Pub/Sub subscriber
    notifier — HousekeepingNotifier for DIRTY bed alerts
    refresh_service — BedBoardRefreshService for materialized view refresh
    seeder — BedInventorySeeder for initial bed inventory setup
    ed_location_loader — Hot-reloadable ED location code loader (US-038)
    boarding_monitor — BoardingMonitor for ED boarding alerts (US-038 TASK-002)
    boarding_schemas — Pydantic schemas for boarding alert workflow (US-038 TASK-002)
    boarding_publisher — BoardingAlertPublisher for Pub/Sub dispatch (US-038 TASK-003)
    boarding_resolver — Resolve boarding alerts on bed assignment (US-038 TASK-004)

Design refs:
    US-035 AC Scenarios 1, 2
    US-038 — ED boarding alert at 2-hour threshold
    ADR-001, ADR-004
"""
from __future__ import annotations

__all__ = [
    "BedManagementAgent",
    "BedStatus",
    "BedStatusUpdateResult",
    "BedBoardRefreshService",
    "BedInventorySeeder",
    "BedInventoryEntry",
    "BedInventoryConfig",
    "HousekeepingNotifier",
    "HousekeepingNotificationPayload",
    "ed_location_loader",
    "boarding_monitor",
    "boarding_schemas",
    "boarding_publisher",
    "boarding_resolver",
]

from app.agents.bed_management.agent import BedManagementAgent
from app.agents.bed_management.notifier import HousekeepingNotifier
from app.agents.bed_management.refresh_service import BedBoardRefreshService
from app.agents.bed_management.schemas import (
    BedInventoryConfig,
    BedInventoryEntry,
    BedStatus,
    BedStatusUpdateResult,
    HousekeepingNotificationPayload,
)
from app.agents.bed_management.seeder import BedInventorySeeder
from app.agents.bed_management import ed_location_loader
from app.agents.bed_management import boarding_monitor
from app.agents.bed_management import boarding_schemas
from app.agents.bed_management import boarding_publisher
from app.agents.bed_management import boarding_resolver
