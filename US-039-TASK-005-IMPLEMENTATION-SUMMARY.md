# US-039 TASK-005 Implementation Summary

**GET /api/v1/encounters/{id}/risk — Risk Score API Endpoint**

**Status:** ✅ Complete  
**Date:** 2026-07-28  
**Validation:** 71/71 checks passed  

---

## Implementation Overview

TASK-005 implements the **Risk Score API Endpoint** that enables the Angular care manager dashboard to retrieve 30-day readmission risk assessments for discharged encounters. The endpoint returns risk scores, tier classifications, SHAP contributing factors, and model version information with RBAC enforcement.

### Key Components

1. **Response Schemas** (`risk.py`): Pydantic models for API responses
2. **API Router** (`encounters_risk.py`): FastAPI endpoint with RBAC and database queries
3. **Main App Registration** (`main.py`): Router registration in API Gateway
4. **Agent Update** (`agent.py`): JSON-structured output_summary for API consumption

---

## Files Created/Modified

### 1. `services/api-gateway/app/schemas/risk.py` (41 lines) — NEW
**Purpose:** Pydantic response models for the risk assessment endpoint.

**Key Components:**
- `RiskTier` enum: LOW, MEDIUM, HIGH, UNKNOWN
- `ContributingFactor` model: feature, shap_value, feature_value, direction
- `EncounterRiskResponse` model: encounter_id, risk_score, risk_tier, contributing_factors, model_version, assessed_at

**Design Refs:** US-039 AC Scenario 4; design.md §3.3 FastAPI routers

### 2. `services/api-gateway/app/routers/encounters_risk.py` (257 lines) — NEW
**Purpose:** FastAPI router implementing GET /api/v1/encounters/{encounter_id}/risk endpoint.

**Key Components:**
- **Endpoint:** `GET /encounters/{encounter_id}/risk`
- **RBAC:** Allows admin, physician, nurse; denies pharmacist, patient (unless own encounter)
- **Database Queries:**
  - Reads `Encounter.risk_score` and `Encounter.risk_tier` from read replica (ADR-006)
  - Fetches most recent completed `AgentTask` with `agent_type="FOLLOWUP_CARE"`
  - Parses `contributing_factors` and `model_version` from `output_summary` JSON
- **Unit-Scoped Access:** Physicians and nurses can only access encounters in their assigned units
- **Error Handling:**
  - HTTP 400: Invalid UUID format
  - HTTP 403: Access denied (role or unit mismatch)
  - HTTP 404: Encounter not found or soft-deleted
  - Graceful JSON parse fallback on malformed `output_summary`

**Database Models (Inline):**
- `Encounter`: id, patient_id, attending_physician_id, unit, risk_score, risk_tier, deleted_at
- `AgentTask`: id, encounter_id, agent_type, status, output_summary, completed_at

**Design Refs:** design.md §3.3 routers; design.md §8.3 RBAC matrix; ADR-006 read replica routing; US-039 AC Scenario 4

### 3. `services/api-gateway/main.py` (48 lines) — MODIFIED
**Purpose:** Register encounters_risk router in API Gateway.

**Changes:**
- Added import: `from app.routers.encounters_risk import router as encounters_risk_router`
- Added registration: `app.include_router(encounters_risk_router, prefix="/api/v1")`

**Result:** Endpoint now accessible at `/api/v1/encounters/{id}/risk`

### 4. `backend/app/agents/followup_care/agent.py` (161 lines) — MODIFIED
**Purpose:** Update `_create_agent_task` to store structured JSON in `output_summary`.

**Changes:**
- Added `import json` at module level
- Updated `_create_agent_task()` signature to accept `contributing_factors: list[dict]`
- Changed `output_summary` from plain string to JSON-serialized dict:
  ```python
  output_summary=json.dumps({
      "risk_tier": risk_tier,
      "model_version": model_version,
      "contributing_factors": contributing_factors,
  })
  ```
- Updated `_create_agent_task()` call in `process()` to pass `contributing_factors=contributing_factors`

**Result:** API endpoint can now parse structured data from `AgentTask.output_summary` for dashboard display

### 5. `validate_us039_task005_risk_api.py` (370 lines) — NEW
**Purpose:** Comprehensive validation script covering all implementation requirements.

**Validation Categories (71 checks total):**
1. **Schema Files** (19 checks): RiskTier enum, ContributingFactor, EncounterRiskResponse fields
2. **Router Implementation** (21 checks): Endpoint definition, database queries, JSON parsing, error handling
3. **RBAC Enforcement** (7 checks): Allowed roles, role checks, unit-scoped access
4. **Main Registration** (4 checks): Router import and registration
5. **Agent JSON Output** (8 checks): JSON module import, JSON serialization, parameter updates
6. **Response Structure** (6 checks): Field types and optionality
7. **Error Handling** (6 checks): HTTP error codes, graceful fallbacks, logging

**Result:** ✅ 71/71 checks passed

---

## Acceptance Criteria Coverage

| AC Scenario | Implementation | Status |
|-------------|----------------|--------|
| AC Scenario 1: GET /api/v1/encounters/ENC-001/risk returns persisted score | Router queries `Encounter.risk_score` and `Encounter.risk_tier` from database | ✅ |
| AC Scenario 4: Response includes risk_score, risk_tier, contributing_factors (top 5), model_version with physician JWT | EncounterRiskResponse model with all 6 fields (+ assessed_at); RBAC enforces physician access | ✅ |
| design.md §8.3 RBAC: Physician ✓, Admin ✓, Nurse ✓ (unit-scoped); Pharmacist ✗, Patient ✗ | `_ALLOWED_ROLES = {"admin", "physician", "nurse"}`; unit-scoped check for physicians/nurses | ✅ |
| ADR-006: Read queries route to read replica | Uses `get_read_db()` dependency with `READ_REPLICA_URL` environment variable | ✅ |
| US-039 DoD: GET /api/v1/encounters/{id}/risk endpoint with contributing_factors from SHAP | Endpoint implemented; contributing_factors parsed from AgentTask.output_summary JSON | ✅ |

---

## Known Limitations

1. **Simplified Auth Dependency**
   - Current implementation uses placeholder `get_current_user()` that returns mock user
   - Production requires JWT validation with Auth0/Firebase/Cognito integration
   - Role and unit claims must be extracted from validated JWT

2. **Inline Database Models**
   - Router defines simplified `Encounter` and `AgentTask` models inline
   - Production should import shared models from backend package or separate schema module
   - Current approach avoids circular dependencies for MVP

3. **Database Connection**
   - Uses environment variable `READ_REPLICA_URL` (fallback to `DATABASE_URL`)
   - Requires Cloud SQL Proxy or connection string with SSL/TLS for production
   - Session factory is module-singleton (lazy initialization)

4. **Unit-Scoped Access Logic**
   - Physicians can access encounters where they are `attending_physician_id` OR encounter is in their assigned units
   - Nurses restricted to encounters in assigned units only
   - Logic assumes `current_user.units` claim exists in JWT

---

## Integration Points

### Upstream Dependencies
- **US-039 TASK-004 (FollowUpCareAgent)**: Persists `risk_score`, `risk_tier` to Encounter table; creates AgentTask with JSON output_summary
- **US-039 TASK-002 (ML Inference Service)**: Provides contributing_factors (SHAP values) in inference response
- **US-039 TASK-003 (Feature Labels Config)**: Human-readable feature labels used in contributing_factors
- **Database Models**: Encounter (risk_score, risk_tier fields), AgentTask (output_summary field)

### Downstream Consumers
- **EP-009 (Angular Dashboard)**: Care manager dashboard will consume this endpoint to display:
  - Risk score gauge (0.0–1.0)
  - Risk tier badge (LOW/MEDIUM/HIGH with color coding)
  - Contributing factors table (top 5 SHAP features with direction indicators)
  - Model version and assessment timestamp

### Environment Variables
- `READ_REPLICA_URL`: Cloud SQL read replica connection string (optional, falls back to DATABASE_URL)
- `DATABASE_URL`: Primary database connection string (fallback for read queries)
- JWT configuration (future): Auth provider URL, audience, client ID

---

## API Specification

### Endpoint
```
GET /api/v1/encounters/{encounter_id}/risk
```

### Request
- **Path Parameter:** `encounter_id` (UUID string)
- **Headers:** `Authorization: Bearer <JWT>` (future — currently placeholder)

### Response (HTTP 200)
```json
{
  "encounter_id": "550e8400-e29b-41d4-a716-446655440000",
  "risk_score": 0.67,
  "risk_tier": "MEDIUM",
  "contributing_factors": [
    {
      "feature": "Age (years)",
      "shap_value": 0.15,
      "feature_value": 78.0,
      "direction": "increases_risk"
    },
    {
      "feature": "Length of Stay (days)",
      "shap_value": 0.12,
      "feature_value": 12.0,
      "direction": "increases_risk"
    },
    {
      "feature": "Number of Comorbidities",
      "shap_value": 0.08,
      "feature_value": 5.0,
      "direction": "increases_risk"
    },
    {
      "feature": "Prior Admissions (12 months)",
      "shap_value": 0.06,
      "feature_value": 2.0,
      "direction": "increases_risk"
    },
    {
      "feature": "Active Medications Count",
      "shap_value": -0.03,
      "feature_value": 3.0,
      "direction": "decreases_risk"
    }
  ],
  "model_version": "1.0.0",
  "assessed_at": "2026-07-28T14:30:00.123456"
}
```

### Error Responses
- **HTTP 400:** `{"detail": "Invalid encounter ID format"}` — UUID parsing failed
- **HTTP 403:** `{"detail": "Access denied — encounter not in your assigned unit"}` — Unit-scoped RBAC failure
- **HTTP 403:** `{"detail": "Access denied - requires one of: admin, physician, nurse"}` — Role-based RBAC failure
- **HTTP 404:** `{"detail": "Encounter not found"}` — Encounter doesn't exist or soft-deleted

---

## Definition of Done Checklist

| Criterion | Status | Evidence |
|-----------|--------|----------|
| ✅ GET /api/v1/encounters/{id}/risk endpoint implemented | ✅ | encounters_risk.py router with get_encounter_risk() function |
| ✅ RBAC enforced: Physician ✓, Admin ✓, Nurse ✓ (unit-scoped); Pharmacist ✗, Patient ✗ | ✅ | _ALLOWED_ROLES, role check, unit-scoped access logic |
| ✅ contributing_factors and model_version parsed from AgentTask output_summary JSON | ✅ | json.loads() with try-except, ContributingFactor model instantiation |
| ✅ Router registered in api-gateway main.py | ✅ | Import and app.include_router() call |
| ✅ TASK-004 agent.py updated to store output_summary as structured JSON | ✅ | json.dumps() with risk_tier, model_version, contributing_factors |
| ✅ Response includes risk_score, risk_tier, contributing_factors, model_version, assessed_at | ✅ | EncounterRiskResponse schema with 6 fields |
| ✅ Read queries route to read replica (ADR-006) | ✅ | get_read_db() dependency with READ_REPLICA_URL |
| ✅ Error handling: 400 (invalid UUID), 403 (forbidden), 404 (not found) | ✅ | HTTPException raises with status codes |
| ✅ Graceful fallback for missing/malformed AgentTask data | ✅ | Empty lists, None defaults, try-except for JSON parsing |
| ✅ Validation script passes | ✅ | 71/71 checks passed |
| ✅ Task status updated | ✅ | task_005_risk_api_endpoint.md: Draft → Complete, date: 2026-07-28 |
| ✅ Implementation summary created | ✅ | US-039-TASK-005-IMPLEMENTATION-SUMMARY.md |

---

## File Summary

| File | Lines | Status | Purpose |
|------|-------|--------|---------|
| `services/api-gateway/app/schemas/risk.py` | 41 | NEW | Pydantic response models |
| `services/api-gateway/app/routers/encounters_risk.py` | 257 | NEW | FastAPI endpoint with RBAC and DB queries |
| `services/api-gateway/main.py` | 48 | MODIFIED | Router registration (+2 lines) |
| `backend/app/agents/followup_care/agent.py` | 161 | MODIFIED | JSON output_summary (+8 lines) |
| `validate_us039_task005_risk_api.py` | 370 | NEW | Comprehensive validation script (71 checks) |
| **Total** | **877** | **3 new, 2 modified** | **5 files** |

---

## Next Steps

1. **US-039 TASK-006**: Unit Tests (pytest test suite for risk API endpoint, mocks for DB and auth)
2. **US-039 TASK-007**: Code Review & DoD Signoff (final acceptance gate)
3. **Integration Testing**: End-to-end testing with Angular dashboard consuming the endpoint
4. **Auth Integration**: Replace placeholder `get_current_user()` with JWT validation (Auth0/Firebase/Cognito)
5. **Shared Models**: Refactor inline database models to shared package for code reuse

---

## Technical Notes

### RBAC Logic

```python
# Role-based access control
_ALLOWED_ROLES = {"admin", "physician", "nurse"}  # Pharmacist and Patient excluded

# Unit-scoped access for physicians and nurses
if current_user.role in {"physician", "nurse"}:
    if encounter.unit not in current_user.units:
        # Exception: Physicians can access encounters where they are attending
        if current_user.role == "physician" and str(encounter.attending_physician_id) != current_user.sub:
            raise HTTPException(403, "Access denied — encounter not in your assigned unit")
        # Nurses have no exception
        elif current_user.role == "nurse":
            raise HTTPException(403, "Access denied — encounter not in your assigned unit")
```

### Database Query Pattern

```python
# 1. Fetch Encounter with risk_score and risk_tier (read replica)
encounter = await session.execute(
    select(Encounter).where(
        Encounter.id == enc_uuid,
        Encounter.deleted_at.is_(None),  # Soft delete check
    )
)

# 2. Fetch most recent FOLLOWUP_CARE AgentTask (read replica)
agent_task = await session.execute(
    select(AgentTask)
    .where(
        AgentTask.encounter_id == enc_uuid,
        AgentTask.agent_type == "FOLLOWUP_CARE",
        AgentTask.status == "COMPLETED",
    )
    .order_by(AgentTask.completed_at.desc())
    .limit(1)
)

# 3. Parse JSON output_summary
summary = json.loads(agent_task.output_summary)
contributing_factors = [ContributingFactor(**cf) for cf in summary.get("contributing_factors", [])]
```

### JSON Output Format (from Agent)

```json
{
  "risk_tier": "MEDIUM",
  "model_version": "1.0.0",
  "contributing_factors": [
    {
      "feature": "Age (years)",
      "shap_value": 0.15,
      "feature_value": 78.0,
      "direction": "increases_risk"
    }
  ]
}
```

---

## Performance Considerations

- **Read Replica Routing:** All GET queries use `READ_REPLICA_URL` to offload primary database (ADR-006)
- **Query Optimization:** Single transaction with 2 SELECT queries (Encounter + AgentTask)
- **JSON Parsing:** Try-except ensures graceful degradation if output_summary is malformed
- **Session Pooling:** SQLAlchemy async engine uses connection pooling with `pool_pre_ping=True`
- **Expected Latency:** < 100ms (DB query latency dominates; minimal compute in endpoint)

---

**Implementation Complete:** 2026-07-28  
**Validation:** ✅ 71/71 checks passed  
**Status:** Ready for TASK-006 (Unit Tests)
