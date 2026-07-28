"""FastAPI router for encounter risk score retrieval.

Endpoint:
    GET /api/v1/encounters/{encounter_id}/risk

RBAC:
    Physician  : ✓ (own patients — unit-scoped enforcement at query level)
    Admin      : ✓ (all encounters)
    Nurse      : Read (unit-scoped — same as Physician enforcement)
    Pharmacist : ✗ (403)
    Patient    : Own encounter only (encounter-scoped JWT)

Design refs:
    design.md §3.3  — FastAPI routers
    design.md §8.3  — RBAC permission matrix
    ADR-006         — GET queries route to read replica
    US-039 AC Scenario 4
"""
from __future__ import annotations

import json
import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.schemas.risk import ContributingFactor, EncounterRiskResponse, RiskTier

router = APIRouter(tags=["encounters"])
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────
# Database setup (simplified for API Gateway - uses read replica)
# ──────────────────────────────────────────────────────────────────────────

# Import backend models (shared via Python path or package)
# For this implementation, we'll use inline model definitions that match backend
from sqlalchemy import Column, String, Float, DateTime, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Encounter(Base):
    """Simplified Encounter model for API Gateway read queries."""
    __tablename__ = "encounters"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True)
    patient_id = Column(PGUUID(as_uuid=True))
    attending_physician_id = Column(PGUUID(as_uuid=True))
    unit = Column(String)
    risk_score = Column(Float, nullable=True)
    risk_tier = Column(String, nullable=True)
    deleted_at = Column(DateTime, nullable=True)


class AgentTaskStatusEnum(str):
    """Agent task status values."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentTask(Base):
    """Simplified AgentTask model for API Gateway read queries."""
    __tablename__ = "agent_tasks"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True)
    encounter_id = Column(PGUUID(as_uuid=True))
    agent_type = Column(String)
    status = Column(String)
    output_summary = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)


# Database session factory (read replica)
_read_session_factory = None


def get_read_session_factory():
    """Get or create the read replica session factory."""
    global _read_session_factory
    if _read_session_factory is None:
        # Read from READ_REPLICA_URL or fallback to DATABASE_URL
        db_url = os.getenv("READ_REPLICA_URL", os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/smarthandoff"))
        engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
        _read_session_factory = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _read_session_factory


async def get_read_db() -> AsyncSession:
    """FastAPI dependency — async read session from replica."""
    factory = get_read_session_factory()
    async with factory() as session:
        yield session


# ──────────────────────────────────────────────────────────────────────────
# Simplified auth dependencies (placeholder - would use JWT validation)
# ──────────────────────────────────────────────────────────────────────────

class CurrentUser(BaseModel):
    """Decoded JWT user claims."""
    sub: str  # User ID
    role: str
    units: list[str] = []


async def get_current_user() -> CurrentUser:
    """Extract and validate JWT from Authorization header.
    
    Placeholder implementation - production would validate JWT signature.
    """
    # TODO: Implement proper JWT validation with Auth0/Firebase/Cognito
    # For now, return a mock admin user for testing
    return CurrentUser(sub="user-123", role="physician", units=["ICU", "ER"])


async def require_any_role(allowed_roles: set[str]):
    """Dependency factory for role-based access control."""
    async def check_role(current_user: CurrentUser = None) -> None:
        if current_user is None:
            current_user = await get_current_user()
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied - requires one of: {', '.join(allowed_roles)}",
            )
    return check_role


# ──────────────────────────────────────────────────────────────────────────
# Endpoint implementation
# ──────────────────────────────────────────────────────────────────────────

_ALLOWED_ROLES = {"admin", "physician", "nurse"}


@router.get(
    "/encounters/{encounter_id}/risk",
    response_model=EncounterRiskResponse,
    summary="Get 30-day readmission risk score for a discharged encounter",
)
async def get_encounter_risk(
    encounter_id: str,
) -> EncounterRiskResponse:
    """Return the risk score, tier, and contributing factors for an encounter.

    Data is read from:
        1. ``encounter.risk_score`` / ``encounter.risk_tier`` — the primary source
        2. The most recent completed ``AgentTask`` with ``agent_type="FOLLOWUP_CARE"``
           — used to retrieve ``contributing_factors`` and ``model_version``
           stored in the task ``output_summary`` JSON payload

    Routes to the read replica (ADR-006).

    Raises:
        404: Encounter not found or soft-deleted.
        403: Caller lacks required role.
        400: Invalid encounter ID format.
    """
    # Get current user and check permissions
    current_user = await get_current_user()
    if current_user.role not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied - requires one of: {', '.join(_ALLOWED_ROLES)}",
        )
    
    # Validate encounter ID format
    try:
        enc_uuid = uuid.UUID(encounter_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid encounter ID format"
        )

    # Get database session
    factory = get_read_session_factory()
    async with factory() as session:
        # Fetch encounter (read replica)
        enc_result = await session.execute(
            select(Encounter).where(
                Encounter.id == enc_uuid,
                Encounter.deleted_at.is_(None),
            )
        )
        encounter: Encounter | None = enc_result.scalar_one_or_none()
        
        if encounter is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Encounter not found"
            )

        # Role-scoped access check for Nurses and Physicians (unit-scoped)
        if current_user.role in {"physician", "nurse"}:
            if encounter.unit not in current_user.units:
                # Allow physicians to access encounters where they are the attending
                if current_user.role == "physician" and str(encounter.attending_physician_id) != current_user.sub:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied — encounter not in your assigned unit",
                    )
                elif current_user.role == "nurse":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied — encounter not in your assigned unit",
                    )

        # Fetch the most recent completed FOLLOWUP_CARE AgentTask for this encounter
        task_result = await session.execute(
            select(AgentTask)
            .where(
                AgentTask.encounter_id == enc_uuid,
                AgentTask.agent_type == "FOLLOWUP_CARE",
                AgentTask.status == AgentTaskStatusEnum.COMPLETED,
            )
            .order_by(AgentTask.completed_at.desc())
            .limit(1)
        )
        agent_task: AgentTask | None = task_result.scalar_one_or_none()

        # Parse contributing_factors from AgentTask output_summary JSON
        contributing_factors: list[ContributingFactor] = []
        model_version: str | None = None
        assessed_at: str | None = None

        if agent_task and agent_task.output_summary:
            try:
                summary = json.loads(agent_task.output_summary) if isinstance(agent_task.output_summary, str) else {}
                model_version = summary.get("model_version")
                cf_data = summary.get("contributing_factors", [])
                contributing_factors = [ContributingFactor(**cf) for cf in cf_data]
                if agent_task.completed_at:
                    assessed_at = agent_task.completed_at.isoformat()
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.warning(
                    "Could not parse AgentTask output_summary for encounter_id=%s: %s",
                    encounter_id,
                    exc,
                )

    return EncounterRiskResponse(
        encounter_id=encounter_id,
        risk_score=encounter.risk_score,
        risk_tier=RiskTier(encounter.risk_tier) if encounter.risk_tier else RiskTier.UNKNOWN,
        contributing_factors=contributing_factors,
        model_version=model_version,
        assessed_at=assessed_at,
    )
