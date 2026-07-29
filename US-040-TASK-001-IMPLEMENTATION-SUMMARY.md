# US-040 TASK-001 Implementation Summary

**appointment SQLAlchemy ORM Model + Alembic Migration**

**Status:** ✅ Complete  
**Date:** 2026-07-28  
**Validation:** 63/63 checks passed (100% compliance)  

---

## Implementation Overview

TASK-001 adds the `appointment` table to support follow-up care pathway management for discharged patients. This table was not included in US-006's core schema and is required for US-040's risk-tiered appointment scheduling functionality implemented by the FollowUpCareAgent.

### Key Features

1. **Appointment ORM Model** — SQLAlchemy model with risk-tier-driven appointment types
2. **Status Lifecycle** — Four-state workflow (SCHEDULED → CONFIRMED → COMPLETED/MISSED)
3. **Care Manager Assignment** — FK to app_user for HIGH-risk tier appointments
4. **Alembic Migration** — Versioned DDL with full upgrade/downgrade support
5. **Encounter Integration** — Bidirectional ORM relationship with cascade delete

---

## Files Created

### 1. `backend/app/models/appointment.py` (156 lines) — NEW

**Purpose:** SQLAlchemy ORM model for the `appointment` table.

**Key Components:**

#### AppointmentType Enum
```python
class AppointmentType(str, enum.Enum):
    """Follow-up appointment type determined by risk tier (US-040).
    
    Mapping to risk tier and target date offset:
        HIGH_RISK_FOLLOW_UP   → risk_tier = HIGH,   target_date = discharge_date + 7 days
        STANDARD_FOLLOW_UP    → risk_tier = MEDIUM, target_date = discharge_date + 14 days
        ROUTINE_FOLLOW_UP     → risk_tier = LOW,    target_date = discharge_date + 30 days
    """
    HIGH_RISK_FOLLOW_UP = "HIGH_RISK_FOLLOW_UP"
    STANDARD_FOLLOW_UP = "STANDARD_FOLLOW_UP"
    ROUTINE_FOLLOW_UP = "ROUTINE_FOLLOW_UP"
```

#### AppointmentStatus Enum
```python
class AppointmentStatus(str, enum.Enum):
    """Appointment lifecycle status (US-040 Technical Notes).
    
    Lifecycle transitions:
        SCHEDULED → CONFIRMED → COMPLETED
                              → MISSED
    """
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
```

#### Appointment Class
- **Extends:** Base, TimestampMixin, SoftDeleteMixin
- **Primary Key:** `id` (UUID)
- **Foreign Keys:**
  - `encounter_id` → encounter.id (CASCADE DELETE)
  - `assigned_user_id` → app_user.id (SET NULL)
- **Unique Constraint:** (encounter_id, appointment_type)
- **Indexes:**
  - `idx_appointment_encounter_id` (FK lookups)
  - `idx_appointment_assigned_user` (care manager workload queries)
  - `idx_appointment_deleted_at` (soft delete filtering, from SoftDeleteMixin)

**Column Details:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | UUID | NO | uuid4() | Primary key |
| encounter_id | UUID | NO | — | FK to encounter.id |
| appointment_type | String(40) | NO | — | AppointmentType enum value |
| target_date | Date | NO | — | Calendar date for follow-up |
| status | String(20) | NO | SCHEDULED | AppointmentStatus enum value |
| assigned_user_id | UUID | YES | NULL | Care manager (HIGH-risk only) |
| created_at | TIMESTAMPTZ | NO | now() | From TimestampMixin |
| updated_at | TIMESTAMPTZ | NO | now() | From TimestampMixin |
| deleted_at | TIMESTAMPTZ | YES | NULL | From SoftDeleteMixin (DR-005) |

**Relationships:**
```python
encounter: Mapped["Encounter"] = relationship(
    "Encounter",
    back_populates="appointments",
    lazy="select",
)
assigned_user: Mapped["AppUser | None"] = relationship(
    "AppUser",
    lazy="select",
)
```

### 2. `backend/app/models/encounter.py` — MODIFIED (+4 lines)

**Changes:**
1. Added TYPE_CHECKING import for Appointment
2. Added appointments relationship:

```python
appointments: Mapped[list["Appointment"]] = relationship(
    "Appointment",
    back_populates="encounter",
    cascade="all, delete-orphan",
    lazy="select",
)
```

**Before:**
```python
if TYPE_CHECKING:
    from app.models.adt_event import AdtEvent
    from app.models.agent_task import AgentTask
    from app.models.bed import Bed
    from app.models.document import Document
    from app.models.medication import Medication
    from app.models.patient import Patient
```

**After:**
```python
if TYPE_CHECKING:
    from app.models.adt_event import AdtEvent
    from app.models.agent_task import AgentTask
    from app.models.appointment import Appointment  # NEW
    from app.models.bed import Bed
    from app.models.document import Document
    from app.models.medication import Medication
    from app.models.patient import Patient
```

### 3. `backend/alembic/versions/u5r8q1p46n10_add_appointment_table.py` (152 lines) — NEW

**Purpose:** Alembic migration to create the `appointment` table.

**Revision Metadata:**
- **revision:** u5r8q1p46n10
- **down_revision:** t4q7p0l35o09 (add_boarding_alert_fields_to_encounter)
- **Created:** 2026-07-28

**upgrade() Function:**
```python
def upgrade() -> None:
    """Create appointment table with indexes and constraints."""
    op.create_table(
        "appointment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "encounter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("encounter.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("appointment_type", sa.String(40), nullable=False, comment="AppointmentType enum value"),
        sa.Column("target_date", sa.Date(), nullable=False, comment="Calendar date by which follow-up must occur"),
        sa.Column("status", sa.String(20), nullable=False, server_default="SCHEDULED", comment="AppointmentStatus lifecycle value"),
        sa.Column(
            "assigned_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
            comment="Care manager assigned for HIGH-risk follow-up; NULL for MEDIUM/LOW",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, comment="Soft-delete timestamp (DR-005); NULL = active"),
    )

    # Create indexes for query performance
    op.create_index("idx_appointment_encounter_id", "appointment", ["encounter_id"])
    op.create_index("idx_appointment_assigned_user", "appointment", ["assigned_user_id"])
    op.create_index("idx_appointment_deleted_at", "appointment", ["deleted_at"])

    # Create unique constraint to prevent duplicate appointments per encounter/type
    op.create_unique_constraint("uq_appointment_encounter_type", "appointment", ["encounter_id", "appointment_type"])
```

**downgrade() Function:**
```python
def downgrade() -> None:
    """Drop appointment table and all associated indexes/constraints."""
    op.drop_constraint("uq_appointment_encounter_type", "appointment", type_="unique")
    op.drop_index("idx_appointment_deleted_at", table_name="appointment")
    op.drop_index("idx_appointment_assigned_user", table_name="appointment")
    op.drop_index("idx_appointment_encounter_id", table_name="appointment")
    op.drop_table("appointment")
```

**Reversibility:** Fully reversible — `alembic downgrade -1` cleanly removes all objects.

### 4. `validate_us040_task001_appointment_orm.py` (335 lines) — NEW

**Purpose:** Comprehensive validation script with 63 automated checks.

**Validation Categories:**
1. **Appointment ORM Model** (29 checks) — Enums, columns, relationships, constraints
2. **Encounter Relationship** (5 checks) — Bidirectional mapping, cascade, import
3. **Alembic Migration** (24 checks) — Syntax, upgrade/downgrade, indexes, FKs
4. **Definition of Done** (5 checks) — All required components present

**Result:** ✅ 63/63 checks passed (100% compliance)

---

## Acceptance Criteria Coverage

| US-040 AC Scenario | Implementation | Status |
|--------------------|----------------|--------|
| **Scenario 2** (HIGH-risk: 7 days, care manager) | `appointment_type=HIGH_RISK_FOLLOW_UP`, `assigned_user_id` FK, `target_date` column | ✅ |
| **Scenario 3** (MEDIUM-risk: 14 days) | `appointment_type=STANDARD_FOLLOW_UP`, `target_date` column | ✅ |
| **Scenario 4** (LOW-risk: 30 days) | `appointment_type=ROUTINE_FOLLOW_UP`, `target_date` column | ✅ |

---

## Technical Design Compliance

| Design Requirement | Implementation | Status |
|--------------------|----------------|--------|
| DR-001 (all DDL via Alembic) | Migration file `u5r8q1p46n10_add_appointment_table.py` | ✅ |
| DR-005 (soft deletes) | `deleted_at` column, SoftDeleteMixin | ✅ |
| DR-014 (versioned migrations) | Revision ID, down_revision pointer | ✅ |
| Phase 1 constraint (C-03) | Internal SmartHandoff record only (no FHIR write-back) | ✅ |

---

## Database Schema

### Table: `appointment`

```sql
CREATE TABLE appointment (
    id                  UUID PRIMARY KEY,
    encounter_id        UUID NOT NULL REFERENCES encounter(id) ON DELETE CASCADE,
    appointment_type    VARCHAR(40) NOT NULL,
    target_date         DATE NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED',
    assigned_user_id    UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,
    
    CONSTRAINT uq_appointment_encounter_type UNIQUE (encounter_id, appointment_type)
);

CREATE INDEX idx_appointment_encounter_id ON appointment (encounter_id);
CREATE INDEX idx_appointment_assigned_user ON appointment (assigned_user_id);
CREATE INDEX idx_appointment_deleted_at ON appointment (deleted_at);
```

### Relationships

```
patient (1) ─────< (∞) encounter (1) ─────< (∞) appointment
                                           
app_user (1) ─────< (∞) appointment (assigned_user_id, nullable)
```

**Cascade Behavior:**
- Delete encounter → **CASCADE DELETE** all appointments
- Delete app_user → **SET NULL** on assigned_user_id
- Delete appointment → **ORPHAN DELETE** from encounter.appointments collection

---

## Validation Results

### 1. Appointment ORM Model (29/29 checks ✅)

- ✅ from __future__ import annotations
- ✅ Imports Base, TimestampMixin, SoftDeleteMixin
- ✅ AppointmentType enum (3 values)
- ✅ AppointmentStatus enum (4 values)
- ✅ All required columns (id, encounter_id, appointment_type, target_date, status, assigned_user_id)
- ✅ Foreign keys with correct ondelete behavior
- ✅ UniqueConstraint on (encounter_id, appointment_type)
- ✅ Relationships to Encounter and AppUser
- ✅ Indexes on encounter_id and assigned_user_id

### 2. Encounter Relationship (5/5 checks ✅)

- ✅ Appointment imported in TYPE_CHECKING block
- ✅ appointments: Mapped[list["Appointment"]] relationship
- ✅ cascade="all, delete-orphan"
- ✅ back_populates="encounter"

### 3. Alembic Migration (24/24 checks ✅)

- ✅ Revision metadata correct (u5r8q1p46n10, down_revision=t4q7p0l35o09)
- ✅ upgrade() function creates table with all 9 columns
- ✅ Foreign keys with CASCADE/SET NULL
- ✅ All 3 indexes created
- ✅ Unique constraint created
- ✅ downgrade() function drops all objects in reverse order
- ✅ Python syntax valid (ast.parse)

### 4. Definition of Done (5/5 checks ✅)

- ✅ All required files created (2/2)
- ✅ Appointment class with all required columns
- ✅ AppointmentType enum complete (3 values)
- ✅ AppointmentStatus enum complete (4 values)
- ✅ Encounter.appointments relationship added

**Overall:** 63/63 checks passed (100% compliance)

---

## Known Limitations

1. **Migration Not Applied to Database**
   - Migration file created but not executed against a database
   - Requires `DATABASE_URL` environment variable to be set
   - Actual `alembic upgrade head` deferred to deployment

2. **No FHIR Write-back**
   - Phase 1 constraint (C-03): internal SmartHandoff record only
   - FHIR Appointment resource creation deferred to Phase 2

3. **No Auto-Confirmation Logic**
   - Status transitions (SCHEDULED → CONFIRMED → COMPLETED/MISSED) are manual updates
   - Future enhancement: automated confirmation workflows

4. **No Target Date Validation**
   - ORM model accepts any future/past date
   - Business logic in FollowUpCareAgent will enforce target_date = discharge_date + offset

---

## Next Steps (Future Tasks)

1. **US-040 TASK-002:** FollowUpCareAgent Modification
   - Add appointment creation logic after risk score calculation
   - Implement risk-tier-to-appointment-type mapping
   - Calculate target_date based on discharge_date + offset (7/14/30 days)
   - Assign care manager from app_user for HIGH-risk tier

2. **US-040 TASK-003:** Care Manager Assignment Logic
   - Query app_user with role=CARE_MANAGER, scoped to patient's unit
   - Round-robin or least-loaded assignment strategy
   - Handle no-care-manager-available fallback

3. **US-040 TASK-004:** Appointment API Endpoint
   - GET /api/v1/appointments?encounter_id={id}
   - PATCH /api/v1/appointments/{id} (status updates)
   - RBAC enforcement (care manager, physician, admin)

4. **US-040 TASK-005:** Unit Tests
   - Test appointment ORM model CRUD operations
   - Test unique constraint enforcement
   - Test cascade delete behavior
   - Test FollowUpCareAgent appointment creation logic

5. **Database Migration Execution:**
   ```bash
   # Set DATABASE_URL for local/staging/production
   export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/smarthandoff"
   
   # Apply migration
   alembic upgrade head
   
   # Verify current revision
   alembic current  # Should show: u5r8q1p46n10 (head)
   
   # Test reversibility
   alembic downgrade -1
   alembic current  # Should show: t4q7p0l35o09
   
   # Reapply
   alembic upgrade head
   ```

---

## File Summary

| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/models/appointment.py` | 156 | Appointment ORM model with enums |
| `backend/app/models/encounter.py` (modified) | +4 | Added appointments relationship |
| `backend/alembic/versions/u5r8q1p46n10_add_appointment_table.py` | 152 | Alembic migration DDL |
| `validate_us040_task001_appointment_orm.py` | 335 | Automated validation script (63 checks) |
| **Total** | **647** | **4 files** |

---

## Definition of Done Checklist

| Criterion | Status | Evidence |
|-----------|--------|----------|
| ✅ Appointment ORM model created | ✅ | backend/app/models/appointment.py |
| ✅ AppointmentType enum (3 values) | ✅ | HIGH_RISK_FOLLOW_UP, STANDARD_FOLLOW_UP, ROUTINE_FOLLOW_UP |
| ✅ AppointmentStatus enum (4 values) | ✅ | SCHEDULED, CONFIRMED, COMPLETED, MISSED |
| ✅ All required columns | ✅ | id, encounter_id, appointment_type, target_date, status, assigned_user_id, timestamps |
| ✅ Foreign keys with correct behavior | ✅ | encounter.id CASCADE, app_user.id SET NULL |
| ✅ UniqueConstraint on (encounter_id, appointment_type) | ✅ | Prevents duplicate appointments per discharge |
| ✅ Encounter.appointments relationship | ✅ | Bidirectional with cascade="all, delete-orphan" |
| ✅ Alembic migration created | ✅ | u5r8q1p46n10_add_appointment_table.py |
| ✅ Indexes on encounter_id, assigned_user_id, deleted_at | ✅ | Query performance optimized |
| ✅ Migration reversible | ✅ | downgrade() drops all objects cleanly |
| ✅ Validation script passes | ✅ | 63/63 checks passed (100%) |
| ✅ Task status updated | ✅ | task_001_appointment_orm_migration.md: Complete, 2026-07-28 |
| ✅ Implementation summary created | ✅ | US-040-TASK-001-IMPLEMENTATION-SUMMARY.md |

---

## Integration Notes

### ORM Usage Example (Future FollowUpCareAgent Code)

```python
from app.models.appointment import Appointment, AppointmentType, AppointmentStatus
from app.models.encounter import Encounter
from datetime import date, timedelta

# After risk score calculation in FollowUpCareAgent
encounter = await session.get(Encounter, encounter_id)

# Map risk_tier to appointment_type and offset
tier_to_type_offset = {
    "HIGH": (AppointmentType.HIGH_RISK_FOLLOW_UP, 7),
    "MEDIUM": (AppointmentType.STANDARD_FOLLOW_UP, 14),
    "LOW": (AppointmentType.ROUTINE_FOLLOW_UP, 30),
}

appointment_type, days_offset = tier_to_type_offset[encounter.risk_tier]
target_date = encounter.discharge_date.date() + timedelta(days=days_offset)

# Create appointment record
appointment = Appointment(
    encounter_id=encounter.id,
    appointment_type=appointment_type.value,
    target_date=target_date,
    status=AppointmentStatus.SCHEDULED.value,
    assigned_user_id=care_manager_id if encounter.risk_tier == "HIGH" else None,
)
session.add(appointment)
await session.commit()
```

### Query Examples

```python
# Get all appointments for an encounter
encounter = await session.get(Encounter, encounter_id)
appointments = encounter.appointments  # ORM lazy-load

# Get HIGH-risk appointments needing care manager assignment
high_risk_appointments = await session.scalars(
    select(Appointment)
    .where(
        Appointment.appointment_type == AppointmentType.HIGH_RISK_FOLLOW_UP.value,
        Appointment.assigned_user_id.is_(None),
        Appointment.deleted_at.is_(None),  # Active only
    )
)

# Get care manager workload
care_manager_appointments = await session.scalars(
    select(Appointment)
    .where(
        Appointment.assigned_user_id == care_manager_id,
        Appointment.status.in_([AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value]),
        Appointment.deleted_at.is_(None),
    )
)
```

---

**Implementation Complete:** 2026-07-28  
**Validation:** ✅ 63/63 checks passed  
**Status:** ✅ Ready for TASK-002 (FollowUpCareAgent Modification)  
**Database Migration:** Pending deployment (requires DATABASE_URL)
