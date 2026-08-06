"""Query service for KPI analytics — reads exclusively from the read replica.

All methods in this service use the read-replica AsyncSession.
No write operations are permitted here.

Design refs:
    design.md ADR-006 — CQRS read/write session routing
    design.md TR-010 — 100% of dashboard GET requests routed to read replica
    US-061 Technical Notes — mv_kpi_daily columns
"""
from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import KpiDailyView
from app.analytics.schemas import KpiDataPoint, KpiResponse, RiskDistributionBucket, RiskDistributionResponse
from app.models.encounter import Encounter
from app.models.patient import Patient
from sqlalchemy import func


class KpiQueryService:
    """Encapsulates all read-replica queries for the KPI analytics endpoint.

    Inject the read-replica AsyncSession — never the write session.
    """

    def __init__(self, read_session: AsyncSession) -> None:
        self._session = read_session

    async def get_kpis(
        self,
        from_date: datetime.date,
        to_date: datetime.date,
        unit: str | None,
        accessible_units: list[str],
    ) -> KpiResponse:
        """Return aggregated KPI data points filtered by date range and unit.

        Args:
            from_date: Inclusive start date for the query window.
            to_date: Inclusive end date for the query window.
            unit: Optional unit filter. If None, returns all accessible_units.
            accessible_units: Units the requesting manager is permitted to view
                              (derived from app_user.units — enforced upstream in RBAC).

        Returns:
            KpiResponse with de-identified aggregated data points.
        """
        stmt = (
            select(KpiDailyView)
            .where(KpiDailyView.date >= from_date)
            .where(KpiDailyView.date <= to_date)
            .order_by(KpiDailyView.date.asc(), KpiDailyView.unit.asc())
        )

        if accessible_units:
            stmt = stmt.where(KpiDailyView.unit.in_(accessible_units))

        if unit is not None:
            stmt = stmt.where(KpiDailyView.unit == unit)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        data_points = [KpiDataPoint.model_validate(row) for row in rows]

        return KpiResponse(
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            data=data_points,
            total_rows=len(data_points),
        )

    async def get_risk_distribution(
        self,
        from_date: datetime.date,
        to_date: datetime.date,
        unit: str | None,
        accessible_units: list[str],
    ) -> RiskDistributionResponse:
        """Return risk tier distribution for discharged encounters."""
        stmt = (
            select(Encounter.risk_tier, func.count(Encounter.id).label("count"))
            .where(Encounter.deleted_at.is_(None))
            .where(Encounter.status == "DISCHARGED")
            .where(Encounter.discharge_date >= datetime.datetime.combine(from_date, datetime.datetime.min.time()))
            .where(Encounter.discharge_date < datetime.datetime.combine(to_date + datetime.timedelta(days=1), datetime.datetime.min.time()))
            .group_by(Encounter.risk_tier)
        )
        if accessible_units:
            stmt = stmt.where(Encounter.unit.in_(accessible_units))
        if unit is not None:
            stmt = stmt.where(Encounter.unit == unit)

        result = await self._session.execute(stmt)
        rows = result.all()
        total = sum(r.count for r in rows)
        order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": 3}
        buckets = [
            RiskDistributionBucket(
                tier=row.risk_tier,
                count=row.count,
                percentage=round((row.count / total * 100) if total > 0 else 0.0, 1),
            )
            for row in sorted(rows, key=lambda r: order.get(r.risk_tier, 99))
        ]
        return RiskDistributionResponse(
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            buckets=buckets,
            total=total,
        )

    async def get_high_risk_encounters(
        self,
        from_date: datetime.date,
        to_date: datetime.date,
        unit: str | None,
        accessible_units: list[str],
        limit: int,
    ) -> list:
        """Return top high-risk discharged encounters (raw rows)."""
        stmt = (
            select(Encounter, Patient.mrn_encrypted)
            .join(Patient, Encounter.patient_id == Patient.id)
            .where(Encounter.deleted_at.is_(None))
            .where(Patient.deleted_at.is_(None))
            .where(Encounter.status == "DISCHARGED")
            .where(Encounter.discharge_date >= datetime.datetime.combine(from_date, datetime.datetime.min.time()))
            .where(Encounter.discharge_date < datetime.datetime.combine(to_date + datetime.timedelta(days=1), datetime.datetime.min.time()))
            .where(Encounter.risk_tier == "HIGH")
            .order_by(Encounter.risk_score.desc().nullslast())
            .limit(limit)
        )
        if accessible_units:
            stmt = stmt.where(Encounter.unit.in_(accessible_units))
        if unit is not None:
            stmt = stmt.where(Encounter.unit == unit)

        result = await self._session.execute(stmt)
        return result.all()
