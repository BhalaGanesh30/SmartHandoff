"""AlertSLAMonitor — detects unresolved HIGH-severity alerts past the 24-hour SLA.

For each alert meeting the breach criteria, the monitor:
  1. Sets sla_breached = True on the PharmacistAlert record.
  2. Publishes a CHARGE_PHARMACIST_ESCALATION event to the notification-requests topic.

The monitor is idempotent: alerts already tagged sla_breached=True are skipped.

Design refs:
    US-032 AC Scenario 3   — 24h SLA; CHARGE_PHARMACIST_ESCALATION
    ADR-001                — publish to Pub/Sub before side-effects
    design.md §3.1         — Medication Reconciliation Agent; Cloud Run
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Final

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pubsub.publisher import publish_message
from app.models.pharmacist_alert import PharmacistAlert

logger = logging.getLogger(__name__)

SLA_THRESHOLD_HOURS: Final[int] = 24
_ESCALATION_TOPIC: Final[str] = "notification-requests"


class AlertSLAMonitor:
    """Scans active HIGH-severity alerts and escalates those past the SLA threshold.

    Args:
        db: Async SQLAlchemy session.
        sla_hours: SLA threshold in hours. Defaults to 24.
    """

    def __init__(
        self,
        db: AsyncSession,
        sla_hours: int = SLA_THRESHOLD_HOURS,
    ) -> None:
        self._db = db
        self._threshold = timedelta(hours=sla_hours)

    async def run(self) -> dict[str, int]:
        """Execute the SLA monitor cycle.

        Returns:
            Dict with ``checked``, ``breached``, and ``skipped`` counters.
        """
        cutoff: datetime = datetime.now(timezone.utc) - self._threshold

        stmt = select(PharmacistAlert).where(
            and_(
                PharmacistAlert.severity == "HIGH",
                PharmacistAlert.status == "ACTIVE",
                PharmacistAlert.sla_breached.is_(False),
                PharmacistAlert.created_at <= cutoff,
            )
        )
        result = await self._db.execute(stmt)
        candidates: list[PharmacistAlert] = list(result.scalars().all())

        logger.info("SLA monitor: found %d candidate alert(s) for breach check", len(candidates))

        checked = 0
        breached = 0
        skipped = 0

        for alert in candidates:
            checked += 1
            try:
                await self._escalate(alert)
                breached += 1
            except Exception:
                logger.exception(
                    "SLA escalation failed for alert_id=%s — skipping", alert.id
                )
                skipped += 1

        await self._db.flush()
        logger.info(
            "SLA monitor complete: checked=%d breached=%d skipped=%d",
            checked,
            breached,
            skipped,
        )
        return {"checked": checked, "breached": breached, "skipped": skipped}

    async def _escalate(self, alert: PharmacistAlert) -> None:
        """Tag the alert as SLA-breached and publish an escalation notification.

        Steps are ordered per ADR-001: publish to Pub/Sub first, then mutate DB.

        Args:
            alert: The :class:`PharmacistAlert` that has breached the SLA.
        """
        await publish_message(
            topic=_ESCALATION_TOPIC,
            data={
                "event_type": "CHARGE_PHARMACIST_ESCALATION",
                "alert_id": str(alert.id),
                "alert_type": alert.alert_type,
                "encounter_id": str(alert.encounter_id),
                "drug_class": alert.drug_class,
                "drug_name": alert.drug_name,
                "severity": alert.severity,
                "created_at": alert.created_at.isoformat(),
                "sla_threshold_hours": SLA_THRESHOLD_HOURS,
            },
            attributes={"priority": "IMMEDIATE"},
        )

        alert.sla_breached = True
        self._db.add(alert)
        logger.warning(
            "SLA breach escalated: alert_id=%s encounter_id=%s drug_class=%s",
            alert.id,
            alert.encounter_id,
            alert.drug_class,
        )
