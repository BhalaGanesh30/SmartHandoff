"""add sla_escalation_sent_at to agent_task

Revision ID: r2o5n8j13m87
Revises: q1n4m7i02l86
Create Date: 2026-07-28 16:00:00.000000

US-034 TASK-001: Add sla_escalation_sent_at nullable timestamp to agent_task
for SLA escalation idempotency (prevents duplicate CHARGE_PHARMACIST_ESCALATION
notifications).

Design refs:
    US-034 Scenario 3 — sla_escalation_sent_at prevents duplicate escalation
    US-034 Scenario 4 — Override clears sla_escalation_sent_at
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'r2o5n8j13m87'
down_revision = 'q1n4m7i02l86'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add sla_escalation_sent_at column and partial index for SLA monitor."""
    op.add_column(
        "agent_task",
        sa.Column(
            "sla_escalation_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Timestamp when a CHARGE_PHARMACIST_ESCALATION notification was last sent "
                "for this task. NULL means no escalation has been sent. "
                "Set by MedRecSLAMonitor (US-034); cleared by override endpoint (US-034 AC4)."
            ),
        ),
    )
    
    # Partial index for medication SLA monitor polling query (US-034 TASK-002).
    # Only indexes tasks that need SLA checking: MEDICATION_RECONCILIATION tasks
    # that are IN_PROGRESS or PENDING and have not yet had an escalation sent.
    op.create_index(
        "ix_agent_task_medrec_sla_pending",
        "agent_task",
        ["agent_type", "status", "encounter_id"],
        postgresql_where=sa.text(
            "agent_type = 'MEDICATION_RECONCILIATION' "
            "AND status IN ('IN_PROGRESS', 'PENDING') "
            "AND sla_escalation_sent_at IS NULL"
        ),
    )


def downgrade() -> None:
    """Remove sla_escalation_sent_at column and partial index."""
    op.drop_index(
        "ix_agent_task_medrec_sla_pending",
        table_name="agent_task",
    )
    op.drop_column("agent_task", "sla_escalation_sent_at")
