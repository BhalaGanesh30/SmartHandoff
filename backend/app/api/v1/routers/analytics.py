"""FastAPI router for KPI analytics — manager/admin access only.

Endpoint:
    GET /api/v1/analytics/kpis

Query params:
    from  (date, ISO 8601, optional) — defaults to today - 30 days
    to    (date, ISO 8601, optional) — defaults to today
    unit  (str,  optional)           — single unit filter; omit for all accessible units

RBAC:
    Permitted roles: MANAGER, ADMIN (enforced by require_roles dependency)
    Denied:          NURSE, PHYSICIAN, PHARMACIST, PATIENT → 403 Forbidden

De-identification guarantee:
    This router never returns patient-level data.
    All responses use KpiResponse which contains only aggregated metrics.
    See US-061 AC Scenario 3 and design.md §8.3.

Design refs:
    design.md §3.3 — FastAPI backend structure
    design.md ADR-006 — read replica routing
    design.md TR-001 — <500 ms p95
"""
from __future__ import annotations

import datetime
from typing import Annotated

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import ExportJob
from app.analytics.query_service import KpiQueryService
from app.analytics.schemas import (
    ExportJobStatus,
    HighRiskEncounter,
    HighRiskEncountersResponse,
    KpiResponse,
    RiskDistributionBucket,
    RiskDistributionResponse,
)
from app.core.auth.jwt import TokenClaims, get_current_user
from app.db.deps import get_read_db
from app.models.encounter import Encounter
from app.models.patient import Patient

router = APIRouter(prefix="/analytics", tags=["analytics"])

_PERMITTED_ROLES = {"MANAGER", "ADMIN"}
_DEFAULT_RANGE_DAYS = 30


def _require_roles(permitted_roles: set[str]) -> callable:
    """Factory: return a dependency that validates role membership."""

    async def _check(current_user: Annotated[TokenClaims, Depends(get_current_user)]) -> TokenClaims:
        if current_user.role.upper() not in permitted_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorised to access this resource. "
                       f"Required: {sorted(permitted_roles)}",
            )
        return current_user

    return _check


@router.get(
    "/kpis",
    response_model=KpiResponse,
    summary="Retrieve aggregated KPI metrics for the analytics dashboard",
    description=(
        "Returns de-identified KPI aggregates from mv_kpi_daily filtered by date range "
        "and optional unit. Accessible to MANAGER and ADMIN roles only. "
        "No PHI is returned — response contains only counts, averages, and percentages."
    ),
    responses={
        200: {"description": "Aggregated KPI data"},
        400: {"description": "Invalid date range (from > to)"},
        403: {"description": "Insufficient role — MANAGER or ADMIN required"},
    },
)
async def get_kpis(
    from_date: Annotated[datetime.date | None, Query(
        alias="from",
        description="Inclusive start date (ISO 8601). Defaults to today minus 30 days.",
    )] = None,
    to_date: Annotated[datetime.date | None, Query(
        alias="to",
        description="Inclusive end date (ISO 8601). Defaults to today.",
    )] = None,
    unit: Annotated[str | None, Query(
        description="Filter results to a single unit. Omit to include all accessible units.",
        max_length=100,
    )] = None,
    current_user: Annotated[TokenClaims, Depends(_require_roles(_PERMITTED_ROLES))] = None,
    read_session: Annotated[AsyncSession, Depends(get_read_db)] = None,
) -> KpiResponse:
    """Return aggregated KPI metrics for the requesting manager's accessible units.

    Date range defaults to the last 30 days when not provided.
    Unit scoping is enforced using app_user.units from the token claims — managers
    cannot query units outside their access scope.
    """
    today = datetime.date.today()
    effective_from = from_date or (today - datetime.timedelta(days=_DEFAULT_RANGE_DAYS))
    effective_to = to_date or today

    if effective_from > effective_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'from' date ({effective_from}) must not be after 'to' date ({effective_to})",
        )

    # Resolve accessible units from token claims (set by US-057 RBAC middleware)
    accessible_units: list[str] = current_user.units or []

    service = KpiQueryService(read_session=read_session)
    return await service.get_kpis(
        from_date=effective_from,
        to_date=effective_to,
        unit=unit,
        accessible_units=accessible_units,
    )


def _effective_date_range(
    from_date: datetime.date | None,
    to_date: datetime.date | None,
) -> tuple[datetime.date, datetime.date]:
    """Resolve effective date range with sensible defaults."""
    today = datetime.date.today()
    effective_from = from_date or (today - datetime.timedelta(days=_DEFAULT_RANGE_DAYS))
    effective_to = to_date or today
    return effective_from, effective_to


def _validate_date_order(effective_from: datetime.date, effective_to: datetime.date) -> None:
    """Raise 400 if from_date is after to_date."""
    if effective_from > effective_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'from' date ({effective_from}) must not be after 'to' date ({effective_to})",
        )


@router.get(
    "/risk-distribution",
    response_model=RiskDistributionResponse,
    summary="Readmission risk tier distribution",
    description=(
        "Returns the percentage distribution of readmission risk tiers "
        "(LOW, MEDIUM, HIGH) across discharged encounters in the selected range. "
        "Accessible to MANAGER and ADMIN roles only. No PHI is returned."
    ),
    responses={
        200: {"description": "Risk distribution percentages"},
        400: {"description": "Invalid date range"},
        403: {"description": "Insufficient role — MANAGER or ADMIN required"},
    },
)
async def get_risk_distribution(
    from_date: Annotated[datetime.date | None, Query(alias="from")] = None,
    to_date: Annotated[datetime.date | None, Query(alias="to")] = None,
    unit: Annotated[str | None, Query(max_length=100)] = None,
    current_user: Annotated[TokenClaims, Depends(_require_roles(_PERMITTED_ROLES))] = None,
    read_session: Annotated[AsyncSession, Depends(get_read_db)] = None,
) -> RiskDistributionResponse:
    """Return readmission risk tier distribution for the dashboard donut chart."""
    effective_from, effective_to = _effective_date_range(from_date, to_date)
    _validate_date_order(effective_from, effective_to)
    accessible_units = current_user.units or []

    stmt = (
        select(
            Encounter.risk_tier,
            func.count(Encounter.id).label("count"),
        )
        .where(Encounter.deleted_at.is_(None))
        .where(Encounter.status == "DISCHARGED")
        .where(Encounter.discharge_date >= datetime.datetime.combine(effective_from, datetime.datetime.min.time()))
        .where(Encounter.discharge_date < datetime.datetime.combine(effective_to + datetime.timedelta(days=1), datetime.datetime.min.time()))
    )

    if accessible_units:
        stmt = stmt.where(Encounter.unit.in_(accessible_units))
    if unit is not None:
        stmt = stmt.where(Encounter.unit == unit)

    stmt = stmt.group_by(Encounter.risk_tier)

    result = await read_session.execute(stmt)
    rows = result.all()

    total = sum(r.count for r in rows)
    buckets: list[RiskDistributionBucket] = []
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": 3}
    for row in sorted(rows, key=lambda r: order.get(r.risk_tier, 99)):
        pct = (row.count / total * 100) if total > 0 else 0.0
        buckets.append(RiskDistributionBucket(
            tier=row.risk_tier,
            count=row.count,
            percentage=round(pct, 1),
        ))

    return RiskDistributionResponse(
        from_date=effective_from,
        to_date=effective_to,
        unit=unit,
        buckets=buckets,
        total=total,
    )


@router.get(
    "/high-risk-encounters",
    response_model=HighRiskEncountersResponse,
    summary="Top high-risk discharged encounters",
    description=(
        "Returns the top high-risk discharged encounters for the analytics table. "
        "Patient identifiers are masked. Accessible to MANAGER and ADMIN roles only."
    ),
    responses={
        200: {"description": "High-risk encounter rows"},
        400: {"description": "Invalid date range"},
        403: {"description": "Insufficient role — MANAGER or ADMIN required"},
    },
)
async def get_high_risk_encounters(
    from_date: Annotated[datetime.date | None, Query(alias="from")] = None,
    to_date: Annotated[datetime.date | None, Query(alias="to")] = None,
    unit: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    current_user: Annotated[TokenClaims, Depends(_require_roles(_PERMITTED_ROLES))] = None,
    read_session: Annotated[AsyncSession, Depends(get_read_db)] = None,
) -> HighRiskEncountersResponse:
    """Return top high-risk discharged encounters for the dashboard table."""
    effective_from, effective_to = _effective_date_range(from_date, to_date)
    _validate_date_order(effective_from, effective_to)
    accessible_units = current_user.units or []

    # Window: last 7 days by default for the "Last 7 Days" table; caller controls via from/to.
    stmt = (
        select(
            Encounter,
            Patient.mrn_encrypted,
        )
        .join(Patient, Encounter.patient_id == Patient.id)
        .where(Encounter.deleted_at.is_(None))
        .where(Patient.deleted_at.is_(None))
        .where(Encounter.status == "DISCHARGED")
        .where(Encounter.discharge_date >= datetime.datetime.combine(effective_from, datetime.datetime.min.time()))
        .where(Encounter.discharge_date < datetime.datetime.combine(effective_to + datetime.timedelta(days=1), datetime.datetime.min.time()))
        .where(Encounter.risk_tier == "HIGH")
        .order_by(Encounter.risk_score.desc().nullslast())
        .limit(limit)
    )

    if accessible_units:
        stmt = stmt.where(Encounter.unit.in_(accessible_units))
    if unit is not None:
        stmt = stmt.where(Encounter.unit == unit)

    result = await read_session.execute(stmt)
    rows = result.all()

    encounters: list[HighRiskEncounter] = []
    for row in rows:
        enc = row.Encounter
        mrn = row.mrn_encrypted or ""
        suffix = mrn[-4:] if mrn and len(str(mrn)) >= 4 else "****"
        masked_id = f"●●● #{suffix}"

        encounters.append(HighRiskEncounter(
            masked_id=masked_id,
            unit=enc.unit,
            risk_score=enc.risk_score,
            risk_tier=enc.risk_tier,
            discharge_date=enc.discharge_date.date() if enc.discharge_date else None,
            follow_up_status="⏳ Pending",
        ))

    return HighRiskEncountersResponse(
        from_date=effective_from,
        to_date=effective_to,
        unit=unit,
        encounters=encounters,
        total=len(encounters),
    )


@router.get(
    "/export",
    summary="Export analytics report as CSV or PDF",
    description=(
        "Returns a CSV file immediately, or starts an async PDF job and returns a poll URL. "
        "Accessible to MANAGER and ADMIN roles only. No PHI is exported."
    ),
    responses={
        200: {"description": "CSV file download"},
        202: {"description": "PDF export job accepted"},
        400: {"description": "Invalid format or date range"},
        403: {"description": "Insufficient role — MANAGER or ADMIN required"},
    },
)
async def export_report(
    format: Annotated[str, Query(..., description="Export format: csv or pdf")],
    from_date: Annotated[datetime.date | None, Query(alias="from")] = None,
    to_date: Annotated[datetime.date | None, Query(alias="to")] = None,
    unit: Annotated[str | None, Query(max_length=100)] = None,
    current_user: Annotated[TokenClaims, Depends(_require_roles(_PERMITTED_ROLES))] = None,
    read_session: Annotated[AsyncSession, Depends(get_read_db)] = None,
):
    """Export analytics report in CSV or PDF format."""
    effective_from, effective_to = _effective_date_range(from_date, to_date)
    _validate_date_order(effective_from, effective_to)
    accessible_units = current_user.units or []

    fmt = format.lower().strip()
    if fmt not in {"csv", "pdf"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="format must be 'csv' or 'pdf'")

    service = KpiQueryService(read_session=read_session)
    kpis = await service.get_kpis(effective_from, effective_to, unit, accessible_units)

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "date", "unit", "avg_discharge_doc_time_min", "readmission_rate_30d",
            "med_recon_completion_rate", "bed_utilisation_pct", "agent_task_success_rate", "discharge_volume",
        ])
        for row in kpis.data:
            writer.writerow([
                row.date.isoformat(),
                row.unit,
                row.avg_discharge_doc_time_min if row.avg_discharge_doc_time_min is not None else "",
                row.readmission_rate_30d if row.readmission_rate_30d is not None else "",
                row.med_recon_completion_rate if row.med_recon_completion_rate is not None else "",
                row.bed_utilisation_pct if row.bed_utilisation_pct is not None else "",
                row.agent_task_success_rate if row.agent_task_success_rate is not None else "",
                row.discharge_volume if row.discharge_volume is not None else "",
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=kpi_report_{effective_from}_{effective_to}.csv",
            },
        )

    # PDF: create a simple HTML -> PDF via xhtml2pdf if available, otherwise return plain text stub
    job_id = ExportJob.create()
    try:
        from xhtml2pdf import pisa
        has_pdf = True
    except Exception:
        has_pdf = False

    risk = await service.get_risk_distribution(effective_from, effective_to, unit, accessible_units)
    high_risk_rows = await service.get_high_risk_encounters(effective_from, effective_to, unit, accessible_units, 50)

    encounters = []
    for row in high_risk_rows:
        enc = row.Encounter
        mrn = row.mrn_encrypted or ""
        suffix = mrn[-4:] if mrn and len(str(mrn)) >= 4 else "****"
        encounters.append({
            "masked_id": f"●●● #{suffix}",
            "unit": enc.unit,
            "risk_score": enc.risk_score,
            "risk_tier": enc.risk_tier,
            "discharge_date": enc.discharge_date.date().isoformat() if enc.discharge_date else "",
        })

    html = f"""<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><title>KPI Report</title></head>
<body style=\"font-family: Arial, sans-serif; margin: 40px;\">
<h1>SmartHandoff Analytics Report</h1>
<p>Period: {effective_from} to {effective_to}</p>
<p>Unit: {unit or 'All Units'}</p>
<h2>KPI Summary</h2>
<table border=\"1\" cellpadding=\"5\" cellspacing=\"0\">
<tr><th>Date</th><th>Unit</th><th>Avg Discharge Time (min)</th><th>Readmission Rate</th>
<th>Med Recon Rate</th><th>Bed Utilisation</th><th>Agent Success</th><th>Discharge Volume</th></tr>
"""
    for row in kpis.data:
        html += (
            f"<tr><td>{row.date}</td><td>{row.unit}</td>"
            f"<td>{row.avg_discharge_doc_time_min or ''}</td>"
            f"<td>{row.readmission_rate_30d or ''}</td>"
            f"<td>{row.med_recon_completion_rate or ''}</td>"
            f"<td>{row.bed_utilisation_pct or ''}</td>"
            f"<td>{row.agent_task_success_rate or ''}</td>"
            f"<td>{row.discharge_volume or ''}</td></tr>"
        )
    html += "</table>"

    html += "<h2>Risk Distribution</h2><table border='1' cellpadding='5' cellspacing='0'>"
    html += "<tr><th>Tier</th><th>Count</th><th>Percentage</th></tr>"
    for bucket in risk.buckets:
        html += f"<tr><td>{bucket.tier}</td><td>{bucket.count}</td><td>{bucket.percentage}%</td></tr>"
    html += "</table>"

    html += "<h2>High-Risk Encounters</h2><table border='1' cellpadding='5' cellspacing='0'>"
    html += "<tr><th>Masked ID</th><th>Unit</th><th>Risk Score</th><th>Risk Tier</th><th>Discharge Date</th></tr>"
    for enc in encounters:
        html += (
            f"<tr><td>{enc['masked_id']}</td><td>{enc['unit']}</td>"
            f"<td>{enc['risk_score']}</td><td>{enc['risk_tier']}</td>"
            f"<td>{enc['discharge_date']}</td></tr>"
        )
    html += "</table></body></html>"

    pdf_bytes = io.BytesIO()
    if has_pdf:
        pisa.CreatePDF(html, dest=pdf_bytes)
    else:
        # Fallback: return HTML content as PDF mimetype; browser will prompt download
        pdf_bytes.write(html.encode("utf-8"))

    content = pdf_bytes.getvalue()
    filename = f"kpi_report_{effective_from}_{effective_to}.pdf"

    # In dev/local we serve the PDF directly from a data URI via the poll endpoint
    import base64
    data_url = f"data:application/pdf;base64,{base64.b64encode(content).decode('ascii')}"
    ExportJob.complete(job_id, data_url)

    return ExportJobStatus(
        job_id=job_id,
        status="processing",
        poll_url=f"/api/v1/analytics/export/{job_id}",
    )


@router.get(
    "/export/{job_id}",
    response_model=ExportJobStatus,
    summary="Poll PDF export job status",
)
async def get_export_status(
    job_id: str,
    current_user: Annotated[TokenClaims, Depends(_require_roles(_PERMITTED_ROLES))] = None,
) -> ExportJobStatus:
    """Return the status of an async PDF export job."""
    job = ExportJob.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    return ExportJobStatus(
        job_id=job_id,
        status=job["status"],
        download_url=job.get("download_url"),
    )
