# US-040 TASK-002 Implementation Summary

**config/care_pathways.yaml — Risk Tier Pathway Configuration & Pydantic Config Model**

**Status:** ✅ Complete  
**Date:** 2026-07-28  
**Validation:** 70/70 checks passed (100% compliance)  

---

## Implementation Overview

TASK-002 externalizes risk tier-to-pathway mapping into a YAML configuration file, allowing clinical administrators to adjust follow-up windows without code changes or redeployment. The configuration is loaded at service startup using a Pydantic model that validates all pathway parameters.

### Key Features

1. **YAML Configuration** — Single source of truth for all pathway parameters
2. **Pydantic Validation** — Type-safe configuration loading with automatic validation
3. **Runtime Flexibility** — Configurable follow-up days without code changes
4. **Cache Optimization** — @lru_cache decorator for single-load performance
5. **Three Risk Tiers** — HIGH (7 days), MEDIUM (14 days), LOW (30 days)

---

## Files Created

### 1. `backend/config/care_pathways.yaml` (35 lines) — NEW

**Purpose:** Risk tier-to-pathway mapping configuration file.

**Structure:**
```yaml
care_pathways:
  HIGH:
    followup_days: 7
    appointment_type: HIGH_RISK_FOLLOW_UP
    alert_care_manager: true
    required_followup_days: 7

  MEDIUM:
    followup_days: 14
    appointment_type: STANDARD_FOLLOW_UP
    alert_care_manager: false
    required_followup_days: null

  LOW:
    followup_days: 30
    appointment_type: ROUTINE_FOLLOW_UP
    alert_care_manager: false
    required_followup_days: null
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| `followup_days` | int | Calendar days from discharge_date for target_date calculation |
| `appointment_type` | str | AppointmentType enum value persisted to appointment table |
| `alert_care_manager` | bool | Whether to publish CARE_MANAGER_ALERT to notification-requests |
| `required_followup_days` | int\|null | Days value in alert payload (HIGH tier only) |

**Risk Tier Mapping:**

| Tier | Follow-up Days | Appointment Type | Care Manager Alert | Required Days |
|------|----------------|------------------|-------------------|---------------|
| **HIGH** | 7 | HIGH_RISK_FOLLOW_UP | ✅ Yes | 7 |
| **MEDIUM** | 14 | STANDARD_FOLLOW_UP | ❌ No | null |
| **LOW** | 30 | ROUTINE_FOLLOW_UP | ❌ No | null |

**Configuration Update Workflow:**
1. Update `care_pathways.yaml` with new follow-up day values
2. Commit to repository
3. Deploy updated config to Cloud Run (no code changes required)
4. Service restart loads new configuration

### 2. `backend/app/config/care_pathways.py` (82 lines) — NEW

**Purpose:** Pydantic configuration model for validating and loading care pathways.

**Key Components:**

#### TierPathwayConfig Class
```python
class TierPathwayConfig(BaseModel):
    """Configuration for a single risk tier pathway.
    
    Attributes:
        followup_days:         Calendar days from discharge_date to set appointment target_date.
        appointment_type:      AppointmentType enum value for the created appointment record.
        alert_care_manager:    Whether to publish a CARE_MANAGER_ALERT to notification-requests.
        required_followup_days: Days value embedded in the CARE_MANAGER_ALERT payload (HIGH only).
    """
    
    followup_days: int = Field(..., gt=0, description="Calendar days from discharge for follow-up")
    appointment_type: str = Field(..., description="AppointmentType enum value")
    alert_care_manager: bool = Field(..., description="Whether to publish CARE_MANAGER_ALERT")
    required_followup_days: int | None = Field(
        None,
        description="Days value in alert payload; None for non-alert tiers",
    )
```

**Pydantic Validation Rules:**
- `followup_days` must be > 0 (gt=0 constraint)
- `appointment_type` must be a non-empty string
- `alert_care_manager` must be boolean
- `required_followup_days` is optional (int or None)

#### CarePathwayConfig Type Alias
```python
CarePathwayConfig = dict[str, TierPathwayConfig]
```

Maps risk tier strings (HIGH/MEDIUM/LOW) to TierPathwayConfig instances.

#### load_care_pathways() Function
```python
@lru_cache(maxsize=1)
def load_care_pathways(config_path: Path = _CONFIG_PATH) -> CarePathwayConfig:
    """Load and validate care pathway configuration from YAML.
    
    Cached after first call — the YAML file is read once at startup.
    
    Args:
        config_path: Absolute path to care_pathways.yaml (defaults to bundled config).
    
    Returns:
        Dict mapping risk tier string (HIGH/MEDIUM/LOW) to TierPathwayConfig.
    
    Raises:
        FileNotFoundError: If care_pathways.yaml does not exist at config_path.
        pydantic.ValidationError: If the YAML structure does not match TierPathwayConfig.
    """
```

**Features:**
- **@lru_cache(maxsize=1)** — Configuration loaded once at startup, cached for subsequent calls
- **FileNotFoundError** — Fail-fast if configuration file is missing
- **Pydantic Validation** — Automatic type checking and constraint validation
- **Logging** — INFO-level log on successful load with tier list

**Usage Example:**
```python
from app.config.care_pathways import load_care_pathways

# Load configuration (cached after first call)
pathways = load_care_pathways()

# Access HIGH tier configuration
high_pathway = pathways["HIGH"]
print(high_pathway.followup_days)          # 7
print(high_pathway.appointment_type)       # "HIGH_RISK_FOLLOW_UP"
print(high_pathway.alert_care_manager)     # True
print(high_pathway.required_followup_days) # 7

# Access MEDIUM tier
medium_pathway = pathways["MEDIUM"]
print(medium_pathway.followup_days)        # 14
print(medium_pathway.alert_care_manager)   # False
print(medium_pathway.required_followup_days) # None
```

### 3. `validate_us040_task002_care_pathways.py` (360 lines) — NEW

**Purpose:** Comprehensive validation script with 70 automated checks.

**Validation Categories:**
1. **YAML File Structure** (18 checks) — File exists, parses correctly, all tiers present, correct values
2. **Pydantic Model** (14 checks) — Imports, class definitions, fields, constraints, decorators
3. **Configuration Loading** (21 checks) — Import success, dict structure, type validation, value correctness
4. **Acceptance Criteria** (10 checks) — AC Scenarios 2, 3, 4 compliance
5. **Definition of Done** (7 checks) — All files created, components present, co-location

**Result:** ✅ 70/70 checks passed (100% compliance)

---

## Acceptance Criteria Coverage

| US-040 AC Scenario | Implementation | Status |
|--------------------|----------------|--------|
| **Scenario 2** (HIGH: 7 days, care manager alert) | `followup_days=7`, `alert_care_manager=true`, `required_followup_days=7` | ✅ |
| **Scenario 3** (MEDIUM: 14 days, no alert) | `followup_days=14`, `alert_care_manager=false`, `required_followup_days=null` | ✅ |
| **Scenario 4** (LOW: 30 days, no alert) | `followup_days=30`, `alert_care_manager=false`, `required_followup_days=null` | ✅ |

---

## Technical Design Compliance

| Design Requirement | Implementation | Status |
|--------------------|----------------|--------|
| US-040 DoD (configurable follow-up days) | YAML file with `followup_days` per tier | ✅ |
| design.md §10.3 (no hardcoded config) | Externalized YAML configuration | ✅ |
| Pydantic validation | TierPathwayConfig with Field constraints | ✅ |
| Single-load performance | @lru_cache(maxsize=1) decorator | ✅ |

---

## Validation Results

### 1. YAML File Structure (18/18 checks ✅)

- ✅ care_pathways.yaml exists
- ✅ YAML parses successfully
- ✅ care_pathways key exists
- ✅ HIGH tier defined with correct values (7 days, HIGH_RISK_FOLLOW_UP, alert=true, required_days=7)
- ✅ MEDIUM tier defined with correct values (14 days, STANDARD_FOLLOW_UP, alert=false, required_days=null)
- ✅ LOW tier defined with correct values (30 days, ROUTINE_FOLLOW_UP, alert=false, required_days=null)

### 2. Pydantic Model (14/14 checks ✅)

- ✅ from __future__ import annotations
- ✅ Imports yaml, Pydantic, BaseModel
- ✅ TierPathwayConfig class with all 4 fields
- ✅ followup_days > 0 constraint (gt=0)
- ✅ CarePathwayConfig type alias
- ✅ load_care_pathways() function with @lru_cache

### 3. Configuration Loading (21/21 checks ✅)

- ✅ load_care_pathways() returns dict
- ✅ All 3 tiers present (HIGH, MEDIUM, LOW)
- ✅ All tier instances are TierPathwayConfig
- ✅ All field values match YAML specification

### 4. Acceptance Criteria (10/10 checks ✅)

- ✅ All AC Scenarios 2, 3, 4 values validated

### 5. Definition of Done (7/7 checks ✅)

- ✅ All required files created
- ✅ YAML has all 3 risk tiers
- ✅ Pydantic model components present
- ✅ Files co-located in correct directories

**Overall:** 70/70 checks passed (100% compliance)

---

## Integration with FollowUpCareAgent

### Loading Configuration at Startup

```python
# backend/app/agents/followup_care/main.py
from app.config.care_pathways import load_care_pathways

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan for FollowUpCareAgent service."""
    # Load care pathway configuration
    app.state.care_pathways = load_care_pathways()
    logger.info("Care pathway configuration loaded")
    
    yield

app = FastAPI(lifespan=lifespan)
```

### Using Configuration in Agent Logic

```python
# backend/app/agents/followup_care/agent.py
from datetime import date, timedelta

async def process(self, message: dict) -> None:
    """Process A03 discharge event."""
    # ... risk calculation ...
    
    # Get pathway configuration for this risk tier
    pathways = self.app.state.care_pathways
    pathway = pathways[encounter.risk_tier]  # "HIGH", "MEDIUM", or "LOW"
    
    # Calculate target_date based on discharge_date + followup_days
    target_date = encounter.discharge_date.date() + timedelta(days=pathway.followup_days)
    
    # Create appointment record
    appointment = Appointment(
        encounter_id=encounter.id,
        appointment_type=pathway.appointment_type,  # "HIGH_RISK_FOLLOW_UP" etc.
        target_date=target_date,
        status=AppointmentStatus.SCHEDULED.value,
        assigned_user_id=care_manager_id if pathway.alert_care_manager else None,
    )
    session.add(appointment)
    
    # Conditionally publish care manager alert
    if pathway.alert_care_manager:
        await publish_care_manager_alert(
            encounter_id=encounter.id,
            required_followup_days=pathway.required_followup_days,
        )
```

### Configuration Update Workflow

```bash
# 1. Update configuration
vim backend/config/care_pathways.yaml
# Change HIGH.followup_days from 7 to 5

# 2. Commit and push
git add backend/config/care_pathways.yaml
git commit -m "US-040: Adjust HIGH tier follow-up window to 5 days"
git push

# 3. Deploy (Cloud Build automatically triggers)
# No code changes required!

# 4. Verify new configuration
curl https://followup-agent.run.app/health
# Service restarts with new configuration via @lru_cache
```

---

## Known Limitations

1. **No Runtime Configuration Reload**
   - Configuration is loaded once at startup via @lru_cache
   - Changes require service restart (Cloud Run rolling update)
   - Future enhancement: File watcher for hot-reload

2. **No Tier Validation Against Encounter**
   - Configuration assumes tier values match Encounter.risk_tier enum
   - No runtime check that YAML tiers align with RiskTier enum values
   - Recommendation: Add validation in load_care_pathways()

3. **No Historical Audit of Configuration Changes**
   - Git history is the only audit trail for config updates
   - No in-app record of when pathways changed
   - Future enhancement: Configuration change event logging

4. **No Multi-Environment Configuration**
   - Single care_pathways.yaml for all environments (dev/staging/prod)
   - Different follow-up windows per environment requires branching
   - Future enhancement: Environment-specific overrides

---

## Next Steps (Future Tasks)

1. **US-040 TASK-003:** Modify FollowUpCareAgent to use configuration
   - Load `app.state.care_pathways` in agent initialization
   - Replace hardcoded follow-up day values with `pathway.followup_days`
   - Implement conditional care manager alert based on `pathway.alert_care_manager`

2. **Add Tier Validation:**
   ```python
   from app.models.encounter import RiskTier
   
   @model_validator(mode="after")
   def _validate_tiers(self) -> CarePathwayConfig:
       """Ensure YAML tiers match RiskTier enum."""
       expected_tiers = {t.value for t in RiskTier if t != RiskTier.UNKNOWN}
       actual_tiers = set(self.keys())
       missing = expected_tiers - actual_tiers
       if missing:
           raise ValueError(f"Missing pathway config for tiers: {missing}")
       return self
   ```

3. **Configuration Change Logging:**
   ```python
   # After loading configuration
   config_hash = hashlib.md5(config_path.read_bytes()).hexdigest()
   logger.info(
       "Care pathway configuration loaded",
       extra={
           "config_hash": config_hash,
           "tiers": list(pathways.keys()),
           "high_followup_days": pathways["HIGH"].followup_days,
       },
   )
   ```

4. **Unit Tests (US-040 TASK-005):**
   - Test `load_care_pathways()` with valid YAML
   - Test FileNotFoundError when YAML missing
   - Test pydantic.ValidationError for invalid YAML
   - Test @lru_cache behavior (single load)
   - Test all tier configurations

---

## File Summary

| File | Lines | Purpose |
|------|-------|---------|
| `backend/config/care_pathways.yaml` | 35 | Risk tier pathway configuration |
| `backend/app/config/care_pathways.py` | 82 | Pydantic config loader |
| `validate_us040_task002_care_pathways.py` | 360 | Automated validation script (70 checks) |
| **Total** | **477** | **3 files** |

---

## Definition of Done Checklist

| Criterion | Status | Evidence |
|-----------|--------|----------|
| ✅ care_pathways.yaml created | ✅ | backend/config/care_pathways.yaml |
| ✅ All 3 risk tiers defined | ✅ | HIGH, MEDIUM, LOW with all fields |
| ✅ HIGH: 7 days, HIGH_RISK_FOLLOW_UP, alert=true | ✅ | 18/18 YAML structure checks |
| ✅ MEDIUM: 14 days, STANDARD_FOLLOW_UP, alert=false | ✅ | Scenario 3 AC checks |
| ✅ LOW: 30 days, ROUTINE_FOLLOW_UP, alert=false | ✅ | Scenario 4 AC checks |
| ✅ TierPathwayConfig Pydantic model | ✅ | app/config/care_pathways.py |
| ✅ followup_days > 0 validation | ✅ | Field(gt=0) constraint |
| ✅ CarePathwayConfig type alias | ✅ | dict[str, TierPathwayConfig] |
| ✅ load_care_pathways() function | ✅ | @lru_cache decorator |
| ✅ FileNotFoundError handling | ✅ | config_path.exists() check |
| ✅ Pydantic ValidationError on invalid YAML | ✅ | TierPathwayConfig(**values) |
| ✅ Configuration co-located with app config | ✅ | backend/config/ and app/config/ |
| ✅ Validation script passes | ✅ | 70/70 checks (100%) |
| ✅ Task status updated | ✅ | task_002_care_pathways_config.md: Complete, 2026-07-28 |
| ✅ Implementation summary created | ✅ | US-040-TASK-002-IMPLEMENTATION-SUMMARY.md |

---

## Configuration Reference

### Field Mapping to US-040 Requirements

| YAML Field | US-040 Requirement | Used By |
|------------|-------------------|---------|
| `followup_days` | AC Scenario 2, 3, 4 (7/14/30 days) | Appointment target_date calculation |
| `appointment_type` | appointment.appointment_type column | Appointment record persistence |
| `alert_care_manager` | AC Scenario 2 (care manager alert) | Conditional Pub/Sub publish |
| `required_followup_days` | Alert payload field | CARE_MANAGER_ALERT message |

### Expected Agent Behavior per Tier

| Tier | Appointment Target | Alert Published | Care Manager Assigned |
|------|-------------------|----------------|----------------------|
| **HIGH** | discharge_date + 7 days | ✅ Yes (CARE_MANAGER_ALERT) | ✅ Yes (assigned_user_id set) |
| **MEDIUM** | discharge_date + 14 days | ❌ No | ❌ No (assigned_user_id = null) |
| **LOW** | discharge_date + 30 days | ❌ No | ❌ No (assigned_user_id = null) |

---

**Implementation Complete:** 2026-07-28  
**Validation:** ✅ 70/70 checks passed  
**Status:** ✅ Ready for TASK-003 (FollowUpCareAgent Integration)  
**Configuration:** Externalized, validated, and cached for performance
