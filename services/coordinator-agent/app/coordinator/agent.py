"""Transition Coordinator Agent — orchestrates AgentTask creation on ADT events.

Receives a validated ``ADTEvent``, maps the event type to the set of
``AgentTaskType`` values, then creates all ``AgentTask`` ORM records in a
single atomic database transaction.

Idempotency:
  The upsert strategy uses ``INSERT … ON CONFLICT (encounter_id, agent_type)
  DO NOTHING`` so that redelivered Pub/Sub messages do not create duplicate
  tasks (AR-008, US-020 technical notes).

Latency target:
  Task creation p95 <2 seconds from Pub/Sub message receipt (FR-004,
  US-020 SC-1). The coordinator performs only DB writes — no LLM calls —
  keeping the hot path synchronous with the asyncio event loop.

Design refs:
    FR-004   — trigger agent workflow within 2 seconds of ADT event
    FR-010   — coordinator orchestrates task assignment across 5 specialist agents
    ADR-001  — coordinator is a Pub/Sub consumer; downstream agents are too
    TR-001   — API/DB response p95 <500ms; avoid N+1 (selectinload)
    AR-008   — idempotency guard for duplicate Pub/Sub deliveries
    US-020   — SC-1 to SC-4, DoD
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from prometheus_client import Counter, Histogram
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.coordinator.task_mapping import AgentTaskType, get_task_types_for_event

if TYPE_CHECKING:
    from app.models.adt_event import ADTEvent
    from app.models.agent_task import AgentTask  # noqa: F401

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

COORDINATOR_TASKS_CREATED = Counter(
    "coordinator_agent_tasks_created_total",
    "Total AgentTask records created by event type",
    ["event_type"],
)

COORDINATOR_LATENCY = Histogram(
    "coordinator_task_creation_latency_seconds",
    "Latency from Pub/Sub message receipt to all AgentTask rows committed",
    buckets=[0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0],
)


# ---------------------------------------------------------------------------
# TransitionCoordinatorAgent
# ---------------------------------------------------------------------------


class TransitionCoordinatorAgent:
    """Orchestrates ``AgentTask`` creation for every incoming ADT event.

    Args:
        db_session: ``AsyncSession`` factory (callable returning
            ``AsyncSession`` context manager). Injected at construction so
            the coordinator is testable without a live database.

    Example::

        agent = TransitionCoordinatorAgent(db_session=async_session_factory)
        await agent.process_event(adt_event)
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def process_event(self, event: "ADTEvent") -> int:
        """Create ``AgentTask`` records for all task types mapped to ``event``.

        Performs a single ``INSERT … ON CONFLICT DO NOTHING`` statement that
        inserts all task rows atomically. Returns the number of tasks actually
        inserted (may be 0 for redelivered messages that already have rows).

        Args:
            event: Validated ``ADTEvent`` from the Pub/Sub subscriber.

        Returns:
            Number of ``AgentTask`` rows inserted (0 on idempotent replay).

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On DB connection/constraint errors
                (propagated so the Pub/Sub subscriber can NACK the message).
        """
        start = time.monotonic()

        task_types: list[AgentTaskType] = get_task_types_for_event(
            event.event_type.value
        )

        if not task_types:
            logger.warning(
                "coordinator_no_tasks_mapped",
                extra={
                    "encounter_id": str(event.encounter_id),
                    "event_type": event.event_type.value,
                },
            )
            return 0

        rows_inserted = await self._create_tasks_atomically(event, task_types)

        elapsed = time.monotonic() - start
        COORDINATOR_LATENCY.observe(elapsed)
        COORDINATOR_TASKS_CREATED.labels(
            event_type=event.event_type.value
        ).inc(rows_inserted)

        logger.info(
            "coordinator_tasks_created",
            extra={
                "encounter_id": str(event.encounter_id),
                "event_type": event.event_type.value,
                "tasks_inserted": rows_inserted,
                "latency_seconds": round(elapsed, 4),
            },
        )

        return rows_inserted

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _create_tasks_atomically(
        self,
        event: "ADTEvent",
        task_types: list[AgentTaskType],
    ) -> int:
        """Execute a single INSERT … ON CONFLICT DO NOTHING for all task rows.

        All rows share the same ``encounter_id`` and ``status=PENDING``.
        The conflict target is ``(encounter_id, agent_type)`` — the unique
        constraint defined on the ``agent_task`` table (US-006).

        Returns the count of rows actually inserted (not skipped by conflict).
        """
        from app.models.agent_task import AgentTask  # noqa: PLC0415

        task_values = [
            {
                "encounter_id": event.encounter_id,
                "agent_type": task_type.value,
                "status": "PENDING",
                "event_type": event.event_type.value,
            }
            for task_type in task_types
        ]

        async with self._db_session() as session:
            async with session.begin():
                stmt = (
                    pg_insert(AgentTask)
                    .values(task_values)
                    .on_conflict_do_nothing(
                        index_elements=["encounter_id", "agent_type"]
                    )
                    .returning(AgentTask.id)
                )
                result = await session.execute(stmt)
                return len(result.fetchall())
