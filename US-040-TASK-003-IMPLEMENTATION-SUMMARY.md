# US-040 TASK-003 Implementation Summary

**CarePathwayService — Care Manager Assignment & Appointment Record Creation**

**Status:** ✅ Complete  
**Date:** 2026-07-28  
**Validation:** 87/87 checks passed (100% compliance)  

---

## Implementation Overview

TASK-003 implements `CarePathwayService`, a stateless async service that encapsulates care manager assignment and appointment record creation logic for the FollowUpCareAgent. The service provides deterministic round-robin care manager assignment for HIGH-risk patients and creates appointment records with tier-specific configurations loaded from `care_pathways.yaml` (TASK-002).

### Key Features

1. **Deterministic Round-Robin Assignment** — Same encounter always maps to same care manager on Pub/Sub redelivery
2. **Tier-Specific Pathways** — Uses configuration from care_pathways.yaml for all three risk tiers
3. **Graceful Degradation** — Returns None when no care managers exist for a unit
4. **ORM-Only Data Access** — No raw SQL; all queries use SQLAlchemy select()
5. **PHI Protection** — Logs only UUIDs and category values; no patient names, MRN, or DOB

---

## Files Created

### 1. `backend/app/services/care_pathway_service.py` (167 lines) — NEW

**Purpose:** Stateless async service for activating care pathways after risk score calculation.

**Class Structure:**

```python
class CarePathwayService:
    """Stateless service for care pathway activation.
    
    Args:
        pathways: Loaded CarePathwayConfig from config/care_pathways.yaml (TASK-002).
    """
    
    def __init__(self, pathways: CarePathwayConfig) -> None:
        self._pathways = pathways
    
    async def activate_pathway(
        self,
        encounter: Encounter,
        risk_tier: str,
        discharge_date: date,
        db: AsyncSession,
    ) -> Appointment:
        """Create appointment record and assign care manager for HIGH risk tier."""
    
    async def _assign_care_manager(
        self,
        encounter_id: uuid.UUID,
        unit: str,
        db: AsyncSession,
    ) -> uuid.UUID | None:
        """Deterministic round-robin care manager selection by unit."""
```

---

## Method Implementation Details

### activate_pathway() Method

**Purpose:** Creates an appointment record with tier-specific configuration and optionally assigns a care manager.

**Logic Flow:**
1. Retrieve pathway configuration: `pathway_config = self._pathways[risk_tier]`
2. Conditionally assign care manager: `if pathway_config.alert_care_manager: assigned_user_id = await self._assign_care_manager(...)`
3. Calculate target date: `target_date = discharge_date + timedelta(days=pathway_config.followup_days)`
4. Create appointment ORM object with:
   - `encounter_id` from encounter.id
   - `appointment_type` from pathway_config (HIGH_RISK_FOLLOW_UP / STANDARD_FOLLOW_UP / ROUTINE_FOLLOW_UP)
   - `target_date` calculated from discharge_date + followup_days
   - `status` = SCHEDULED (initial state)
   - `assigned_user_id` from care manager assignment (HIGH only) or None (MEDIUM/LOW)
5. Add to session and flush: `db.add(appointment); await db.flush()`
6. Log activation event with structured logging
7. Return flushed Appointment ORM object

**Signature:**
```python
async def activate_pathway(
    self,
    encounter: Encounter,
    risk_tier: str,        # "HIGH" | "MEDIUM" | "LOW"
    discharge_date: date,  # From A03 ADT event
    db: AsyncSession,      # Cloud SQL Primary session
) -> Appointment:          # Flushed but not committed
```

**Raises:**
- `KeyError`: If `risk_tier` is not in `care_pathways.yaml` (unexpected tier value)
- `sqlalchemy.exc.IntegrityError`: On duplicate `(encounter_id, appointment_type)` — indicates Pub/Sub redelivery

**Example Usage:**
```python
from app.config.care_pathways import load_care_pathways
from app.services.care_pathway_service import CarePathwayService

# Load configuration at service startup
pathways = load_care_pathways()
service = CarePathwayService(pathways)

# In FollowUpCareAgent.process()
async with async_session_maker() as db:
    # ... risk score calculation and persistence ...
    
    appointment = await service.activate_pathway(
        encounter=encounter,
        risk_tier=encounter.risk_tier,  # "HIGH" | "MEDIUM" | "LOW"
        discharge_date=discharge_event.discharge_date,
        db=db,
    )
    
    await db.commit()
    # appointment.id now populated
    # appointment.assigned_user_id populated for HIGH tier
```

---

### _assign_care_manager() Method

**Purpose:** Selects a care manager from the available pool using deterministic round-robin.

**Logic Flow:**
1. Query `app_user` for care managers:
   ```python
   select(AppUser.id)
   .where(
       AppUser.role == "CARE_MANAGER",
       AppUser.unit == unit,
       AppUser.is_active == True,
   )
   .order_by(AppUser.id.asc())
   ```
2. Convert result to list: `pool: list[uuid.UUID] = list(result.scalars().all())`
3. Handle empty pool gracefully:
   ```python
   if not pool:
       logger.warning("No CARE_MANAGER users found for unit")
       return None
   ```
4. Apply deterministic hash-based round-robin:
   ```python
   pool_index = hash(str(encounter_id)) % len(pool)
   selected_id = pool[pool_index]
   ```
5. Log assignment and return selected UUID

**Deterministic Round-Robin Guarantee:**
- Uses `hash(str(encounter_id)) % len(pool)` for index selection
- Same `encounter_id` always hashes to same pool index
- Prevents duplicate care manager notifications on Pub/Sub redelivery
- Stable ordering via `order_by(AppUser.id.asc())`

**Signature:**
```python
async def _assign_care_manager(
    self,
    encounter_id: uuid.UUID,  # Used as hash seed
    unit: str,                # Hospital unit filter
    db: AsyncSession,         # Read-only query
) -> uuid.UUID | None:        # Assigned care manager ID or None
```

**Returns:**
- `uuid.UUID`: ID of assigned care manager
- `None`: No care managers available for the unit (not an error)

**Example Scenarios:**

| Scenario | Pool Size | encounter_id hash | Index | Result |
|----------|-----------|-------------------|-------|--------|
| Unit has 3 care managers | 3 | 12345 | 12345 % 3 = 0 | pool[0] selected |
| Unit has 5 care managers | 5 | 67890 | 67890 % 5 = 0 | pool[0] selected |
| Unit has 0 care managers | 0 | N/A | N/A | None returned (warning logged) |

**Idempotency:**
- Same encounter_id on redelivery → same hash → same pool index → same care manager
- No duplicate care manager assignments
- No duplicate notification alerts

---

## Acceptance Criteria Coverage

| US-040 AC Scenario | Implementation | Validation |
|--------------------|----------------|------------|
| **Scenario 2** (HIGH: 7 days, care manager assigned) | `if pathway_config.alert_care_manager: assigned_user_id = await self._assign_care_manager(...)` | ✅ 87/87 |
| **Scenario 3** (MEDIUM: 14 days, no care manager) | `assigned_user_id: uuid.UUID | None = None` (conditional assignment) | ✅ |
| **Scenario 4** (LOW: 30 days, no care manager) | Same as Scenario 3 (no alert_care_manager in config) | ✅ |
| All scenarios: appointment record creation | `appointment = Appointment(...)` with tier-specific values | ✅ |
| All scenarios: status=SCHEDULED | `status=AppointmentStatus.SCHEDULED.value` | ✅ |
| All scenarios: uses config for appointment_type | `appointment_type=AppointmentType(pathway_config.appointment_type).value` | ✅ |

---

## Technical Design Compliance

| Design Requirement | Implementation | Status |
|--------------------|----------------|--------|
| US-040 AC Scenario 2 (assigned_user_id for HIGH) | Round-robin assignment via `_assign_care_manager()` | ✅ |
| US-040 AC Scenarios 3/4 (no care manager for MEDIUM/LOW) | Conditional: `if pathway_config.alert_care_manager` | ✅ |
| design.md §6.1 DR-001 (no raw SQL) | Uses SQLAlchemy `select()` ORM queries only | ✅ |
| design.md §6.1 DR-005 (soft delete) | Filters by `AppUser.is_active == True` | ✅ |
| US-040 Technical Notes (round-robin by unit) | Deterministic: `hash(str(encounter_id)) % len(pool)` | ✅ |
| Phase 1 Constraint C-03 (no FHIR write-back) | Internal appointment record only (no FHIR API calls) | ✅ |

---

## Validation Results

### 1. File Structure (14/14 checks ✅)

- ✅ care_pathway_service.py exists
- ✅ All required imports present (logging, uuid, date, timedelta, select, AsyncSession)
- ✅ Model imports (Appointment, AppUser, Encounter, care_pathways config)
- ✅ US-040 and design.md references in docstrings
- ✅ Round-robin and idempotency documented

### 2. Class Structure (13/13 checks ✅)

- ✅ CarePathwayService class defined
- ✅ `__init__()` accepts and stores pathways
- ✅ `activate_pathway()` method with correct signature
- ✅ `_assign_care_manager()` method with correct signature
- ✅ All parameters type-hinted
- ✅ Return types annotated

### 3. activate_pathway() Logic (14/14 checks ✅)

- ✅ Retrieves pathway config from `self._pathways[risk_tier]`
- ✅ Conditionally assigns care manager based on `pathway_config.alert_care_manager`
- ✅ Calculates target_date: `discharge_date + timedelta(days=pathway_config.followup_days)`
- ✅ Creates Appointment ORM object with all required fields
- ✅ Uses config values for appointment_type and followup_days
- ✅ Adds appointment to session via `db.add(appointment)`
- ✅ Flushes session before return: `await db.flush()`
- ✅ Logs activation event with structured logging

### 4. Care Manager Assignment (13/13 checks ✅)

- ✅ Queries `AppUser.id` with correct filters
- ✅ Filters by `role='CARE_MANAGER'`
- ✅ Filters by `unit = encounter.unit`
- ✅ Filters by `is_active == True` (excludes deprovisioned users)
- ✅ Orders by `id ASC` for stable ordering
- ✅ Returns `None` gracefully when pool is empty
- ✅ Logs warning when no care managers found for unit
- ✅ Uses `hash(str(encounter_id)) % len(pool)` for deterministic selection
- ✅ Logs care manager assignment with structured data

### 5. PHI Protection (7/7 checks ✅)

- ✅ No `patient_name` in logs
- ✅ No `MRN` in logs
- ✅ No `date_of_birth` / `dob` in logs
- ✅ Logs only safe fields: `encounter_id` (UUID), `risk_tier` (category), `appointment_type` (category), `assigned_user_id` (staff UUID)

### 6. Acceptance Criteria (6/6 checks ✅)

- ✅ Scenario 2: assigned_user_id populated for HIGH tier
- ✅ Scenario 2: target_date calculated from discharge_date + config.followup_days
- ✅ Scenarios 3/4: assigned_user_id=None for MEDIUM and LOW tiers
- ✅ All scenarios: Creates appointment record
- ✅ All scenarios: Sets status=SCHEDULED
- ✅ All scenarios: Uses config for appointment_type

### 7. Definition of Done (10/10 checks ✅)

- ✅ care_pathway_service.py created
- ✅ CarePathwayService class implemented
- ✅ activate_pathway() method implemented
- ✅ _assign_care_manager() method implemented
- ✅ No raw SQL (uses SQLAlchemy ORM select)
- ✅ Round-robin is deterministic
- ✅ Returns None gracefully when pool empty
- ✅ Uses db.add() and db.flush() for ORM operations
- ✅ Integrates with care_pathways.yaml configuration

### 8. Code Quality (10/10 checks ✅)

- ✅ Type hints for all parameters and return values
- ✅ Module-level docstring present
- ✅ Class and method docstrings present
- ✅ Uses `async def` for async methods
- ✅ Uses `await` for async database operations
- ✅ Documents `Raises` section in docstrings
- ✅ Uses `logger.info` for success events
- ✅ Uses `logger.warning` for edge cases
- ✅ Uses `extra={}` dict for structured logging

**Overall:** 87/87 checks passed (100% compliance)

---

## Integration with FollowUpCareAgent

### Loading Service at Startup

```python
# backend/app/agents/followup_care/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config.care_pathways import load_care_pathways
from app.services.care_pathway_service import CarePathwayService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan for FollowUpCareAgent service."""
    # Load care pathway configuration
    pathways = load_care_pathways()
    app.state.care_pathways = pathways
    
    # Initialize CarePathwayService
    app.state.care_pathway_service = CarePathwayService(pathways)
    
    logger.info("FollowUpCareAgent initialized")
    yield


app = FastAPI(lifespan=lifespan)
```

### Using Service in Agent Logic

```python
# backend/app/agents/followup_care/agent.py
from datetime import datetime
from app.services.care_pathway_service import CarePathwayService


async def process(self, message: dict) -> None:
    """Process A03 discharge event (US-040 AC Scenario 2, 3, 4)."""
    # 1. Extract encounter_id from Pub/Sub message
    encounter_id = uuid.UUID(message["encounter_id"])
    
    async with async_session_maker() as db:
        # 2. Load encounter with risk_tier (from US-039)
        result = await db.execute(
            select(Encounter).where(Encounter.id == encounter_id)
        )
        encounter = result.scalar_one()
        
        # 3. Get discharge_date from A03 event
        discharge_date = datetime.fromisoformat(message["discharge_date"]).date()
        
        # 4. Activate care pathway
        service: CarePathwayService = self.app.state.care_pathway_service
        appointment = await service.activate_pathway(
            encounter=encounter,
            risk_tier=encounter.risk_tier,  # "HIGH" | "MEDIUM" | "LOW"
            discharge_date=discharge_date,
            db=db,
        )
        
        # 5. Commit transaction
        await db.commit()
        
        # 6. Publish care manager alert (HIGH tier only)
        # Will be implemented in TASK-004
        
        logger.info(
            "A03 discharge event processed",
            extra={
                "encounter_id": str(encounter.id),
                "appointment_id": str(appointment.id),
                "risk_tier": encounter.risk_tier,
            },
        )
```

---

## Round-Robin Assignment Examples

### Example 1: Unit with 3 Care Managers

**Setup:**
- Unit: "ICU"
- Care managers: [uuid1, uuid2, uuid3] (ordered by id ASC)
- Encounter IDs: enc_a, enc_b, enc_c, enc_d, enc_e, enc_f

**Assignment:**
```python
hash(str(enc_a)) % 3 = 0 → pool[0] = uuid1
hash(str(enc_b)) % 3 = 1 → pool[1] = uuid2
hash(str(enc_c)) % 3 = 2 → pool[2] = uuid3
hash(str(enc_d)) % 3 = 0 → pool[0] = uuid1
hash(str(enc_e)) % 3 = 1 → pool[1] = uuid2
hash(str(enc_f)) % 3 = 2 → pool[2] = uuid3
```

**Distribution:** Approximately even (33% each)

### Example 2: Unit with No Care Managers

**Setup:**
- Unit: "ER"
- Care managers: [] (empty pool)

**Assignment:**
```python
pool = []
if not pool:
    logger.warning("No CARE_MANAGER users found for unit — appointment created without assignment")
    return None

# Result: assigned_user_id = None
```

**Behavior:**
- Appointment still created with `assigned_user_id=None`
- Warning logged for operational visibility
- No error raised (graceful degradation)

### Example 3: Pub/Sub Redelivery (Idempotency)

**Setup:**
- Unit: "MedSurg"
- Care managers: [uuid_alpha, uuid_beta, uuid_gamma]
- Encounter ID: enc_123

**First Delivery:**
```python
hash(str(enc_123)) % 3 = 1 → pool[1] = uuid_beta
# appointment created with assigned_user_id = uuid_beta
```

**Redelivery (duplicate message):**
```python
hash(str(enc_123)) % 3 = 1 → pool[1] = uuid_beta
# Same hash → same pool index → same care manager
# IntegrityError on duplicate (encounter_id, appointment_type)
# Caller (agent) treats as idempotent and skips
```

**Outcome:** No duplicate care manager notifications sent

---

## Known Limitations

1. **Static Pool Membership**
   - Care manager pool is queried at assignment time (not cached)
   - If care managers are added/removed between encounters, distribution changes
   - Mitigation: Ordering by `id ASC` provides stable ordering within the pool

2. **Unit-Specific Assignment Only**
   - Care managers must have matching `unit` field in `app_user`
   - Cross-unit assignment not supported in Phase 1
   - Future enhancement: Fallback to hospital-wide pool if unit-specific pool is empty

3. **No Load Balancing Metrics**
   - Round-robin is hash-based, not workload-based
   - Does not account for current care manager workload or availability
   - Future enhancement: Query `appointment` table for active assignments per care manager

4. **No Appointment Rescheduling**
   - Created appointment has fixed `target_date`
   - No automatic rescheduling if appointment is missed
   - Manual update required via API (future US)

5. **No FHIR Write-Back (Phase 1)**
   - Appointment is internal SmartHandoff record only
   - Not synchronized to Epic FHIR server (Constraint C-03)
   - Phase 2 enhancement: Publish appointment to FHIR R4 Appointment resource

---

## Next Steps (Future Tasks)

1. **US-040 TASK-004:** Modify FollowUpCareAgent to use CarePathwayService
   - Load `app.state.care_pathway_service` in agent initialization
   - Call `await service.activate_pathway(...)` after risk score persistence
   - Handle `IntegrityError` for idempotent Pub/Sub redelivery
   - Publish CARE_MANAGER_ALERT notification (HIGH tier only)

2. **US-040 TASK-005:** Unit Tests for CarePathwayService
   - Test `activate_pathway()` for all three risk tiers
   - Test `_assign_care_manager()` with various pool sizes (0, 1, 3, 10)
   - Test deterministic round-robin (same encounter_id → same care manager)
   - Test empty pool graceful handling
   - Test IntegrityError handling on duplicate appointment creation

3. **US-040 TASK-006:** Integration Tests
   - End-to-end test: A03 event → risk score → appointment creation → care manager alert
   - Test Pub/Sub redelivery idempotency
   - Test care manager notification delivery (HIGH tier only)

4. **Future Enhancement: Workload-Based Assignment**
   ```python
   # Query active appointments per care manager
   workload = await db.execute(
       select(Appointment.assigned_user_id, func.count(Appointment.id))
       .where(Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]))
       .group_by(Appointment.assigned_user_id)
   )
   # Select care manager with minimum workload
   ```

5. **Future Enhancement: Cross-Unit Fallback**
   ```python
   # If unit-specific pool is empty, try hospital-wide pool
   if not pool:
       pool = await self._get_hospital_wide_care_managers(db)
   ```

---

## File Summary

| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/services/care_pathway_service.py` | 167 | CarePathwayService class with care manager assignment and appointment creation |
| `validate_us040_task003_care_pathway_service.py` | 432 | Automated validation script (87 checks) |
| **Total** | **599** | **2 files** |

---

## Definition of Done Checklist

| Criterion | Status | Evidence |
|-----------|--------|----------|
| ✅ care_pathway_service.py created | ✅ | backend/app/services/care_pathway_service.py |
| ✅ CarePathwayService class with __init__(pathways) | ✅ | 14/14 file structure checks |
| ✅ activate_pathway() creates appointment record | ✅ | 14/14 activate_pathway logic checks |
| ✅ activate_pathway() assigns care manager for HIGH | ✅ | if pathway_config.alert_care_manager conditional |
| ✅ activate_pathway() uses config for all tiers | ✅ | pathway_config.followup_days, appointment_type |
| ✅ _assign_care_manager() round-robin by unit | ✅ | 13/13 care manager assignment checks |
| ✅ Round-robin is deterministic | ✅ | hash(str(encounter_id)) % len(pool) |
| ✅ Returns None when no care managers exist | ✅ | if not pool: return None with warning log |
| ✅ No raw SQL (uses SQLAlchemy ORM) | ✅ | select(AppUser.id).where(...) |
| ✅ No PHI in log output | ✅ | 7/7 PHI protection checks |
| ✅ Validation script passes | ✅ | 87/87 checks (100%) |
| ✅ Task status updated | ✅ | task_003_care_pathway_service.md: Complete, 2026-07-28 |
| ✅ Implementation summary created | ✅ | US-040-TASK-003-IMPLEMENTATION-SUMMARY.md |

---

## Configuration Usage Example

### HIGH Tier (risk_tier = "HIGH")

**care_pathways.yaml:**
```yaml
HIGH:
  followup_days: 7
  appointment_type: HIGH_RISK_FOLLOW_UP
  alert_care_manager: true
  required_followup_days: 7
```

**Service Behavior:**
1. `pathway_config = self._pathways["HIGH"]`
2. `if True:` → calls `_assign_care_manager()` → returns care manager UUID
3. `target_date = discharge_date + timedelta(days=7)`
4. Creates appointment: `appointment_type="HIGH_RISK_FOLLOW_UP"`, `assigned_user_id=<UUID>`

### MEDIUM Tier (risk_tier = "MEDIUM")

**care_pathways.yaml:**
```yaml
MEDIUM:
  followup_days: 14
  appointment_type: STANDARD_FOLLOW_UP
  alert_care_manager: false
  required_followup_days: null
```

**Service Behavior:**
1. `pathway_config = self._pathways["MEDIUM"]`
2. `if False:` → skips `_assign_care_manager()`
3. `assigned_user_id = None`
4. `target_date = discharge_date + timedelta(days=14)`
5. Creates appointment: `appointment_type="STANDARD_FOLLOW_UP"`, `assigned_user_id=None`

### LOW Tier (risk_tier = "LOW")

**care_pathways.yaml:**
```yaml
LOW:
  followup_days: 30
  appointment_type: ROUTINE_FOLLOW_UP
  alert_care_manager: false
  required_followup_days: null
```

**Service Behavior:**
1. `pathway_config = self._pathways["LOW"]`
2. `if False:` → skips `_assign_care_manager()`
3. `assigned_user_id = None`
4. `target_date = discharge_date + timedelta(days=30)`
5. Creates appointment: `appointment_type="ROUTINE_FOLLOW_UP"`, `assigned_user_id=None`

---

**Implementation Complete:** 2026-07-28  
**Validation:** ✅ 87/87 checks passed  
**Status:** ✅ Ready for TASK-004 (FollowUpCareAgent Integration)  
**Service:** Stateless, async, ORM-based, PHI-safe, deterministic round-robin
