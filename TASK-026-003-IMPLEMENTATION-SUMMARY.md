# TASK-026-003 Implementation Summary

**Date:** 2026-07-25  
**Task:** Add `completeness_status` and `missing_fields` Columns to `Document` Model + Alembic Migration  
**Status:** ✓ COMPLETE

---

## Overview

Successfully implemented database schema changes for TASK-026-003 to support document completeness validation:
1. Added `completeness_status` VARCHAR(20) column to track validation result
2. Added `missing_fields` JSONB column to store list of missing required fields
3. Created Alembic migration for backwards-compatible schema update
4. Added `update_completeness()` method to DocumentRepository for persisting validation results

---

## Files Modified

### ORM Models (1 file)

1. **[backend/app/models/document.py](backend/app/models/document.py)**
   - **Added Import:** `from sqlalchemy.dialects.postgresql import JSONB`
   - **Added Column:** `completeness_status: Mapped[str | None]` 
     - Type: VARCHAR(20), nullable
     - Values: "COMPLETE" or "INCOMPLETE"
     - Default: NULL (until validator runs)
     - Comment: "COMPLETE or INCOMPLETE — set by CompletenessValidator after document generation"
   - **Added Column:** `missing_fields: Mapped[list | None]`
     - Type: JSONB, nullable
     - Default: `[]` (empty array)
     - Server default: `'[]'::jsonb`
     - Comment: "Ordered list of field names absent from the document. Empty list when COMPLETE."

### Repository Layer (1 file)

2. **[backend/app/db/repositories/document_repository.py](backend/app/db/repositories/document_repository.py)**
   - **Added Import:** `from agents.documentation.completeness_validator import CompletenessResult, CompletenessStatus`
   - **Added Method:** `async def update_completeness(document: Document, result: CompletenessResult) -> Document`
     - Persists CompletenessValidator result to database
     - Sets `document.completeness_status` from `result.status.value`
     - Sets `document.missing_fields` from `result.missing_fields`
     - Reverts `document.status` to DRAFT if INCOMPLETE (holds back from review queue)
     - Commits changes and refreshes document instance
     - Logs validation result for audit trail

### Alembic Migrations (1 file)

3. **[backend/alembic/versions/k5h8g1c46f50_add_completeness_columns_to_document.py](backend/alembic/versions/k5h8g1c46f50_add_completeness_columns_to_document.py)** *(NEW)*
   - **Revision:** `k5h8g1c46f50`
   - **Revises:** `j4g7f0b35e49` (US-067 patient opt-out)
   - **Upgrade:**
     - `ADD COLUMN completeness_status VARCHAR(20) NULL`
     - `ADD COLUMN missing_fields JSONB NULL DEFAULT '[]'::jsonb`
   - **Downgrade:**
     - `DROP COLUMN missing_fields`
     - `DROP COLUMN completeness_status`
   - **Backwards Compatible:** Existing rows receive NULL/[] defaults
   - **Rollback Safe:** DR-001 compliance — no data loss on downgrade

### Validation Script (1 file)

4. **[validate_task026_003.py](validate_task026_003.py)** *(NEW)*
   - Automated validation script with 4 check categories
   - Verifies model columns, migration structure, repository method, and syntax
   - **Result:** ✓ ALL CHECKS PASSED

---

## Changes Summary

| Category | Action | Count |
|----------|--------|-------|
| ORM Models Modified | Added columns + import | 1 |
| Repository Modified | Added method + import | 1 |
| Migrations Created | New migration file | 1 |
| Validation Created | Validation script | 1 |
| **Total Files Changed** | | **4** |

---

## Database Schema Changes

### `document` Table — New Columns

| Column Name | Type | Nullable | Default | Comment |
|-------------|------|----------|---------|---------|
| `completeness_status` | VARCHAR(20) | YES | NULL | COMPLETE or INCOMPLETE — set by CompletenessValidator |
| `missing_fields` | JSONB | YES | `[]` | Ordered list of missing field names |

---

## Acceptance Criteria Coverage

| US-026 AC | Requirement | Implementation |
|-----------|-------------|----------------|
| **Scenario 1** | `Document.completeness_status = "COMPLETE"` after validator runs | ✓ Column added; `update_completeness()` sets value |
| **Scenario 2** | `Document.completeness_status = "INCOMPLETE"`, `missing_fields = ["follow_up_instructions"]` | ✓ Both columns added; repository method updates both |
| **Scenario 2** | INCOMPLETE doc status reverted to DRAFT | ✓ `update_completeness()` sets status=DRAFT on INCOMPLETE |
| **Scenario 4** | Tasks API can read `completeness_status` and `missing_fields` | ✓ Columns accessible via ORM; no API changes needed |

---

## Definition of Done Checklist

- [x] `Document.completeness_status` (`String(20)`, nullable) added to ORM model
- [x] `Document.missing_fields` (`JSONB`, server_default `[]`) added to ORM model
- [x] Alembic migration file generated and reviewed — `upgrade()` and `downgrade()` both present
- [x] `DocumentRepository.update_completeness()` method implemented
- [x] INCOMPLETE documents have `status` reverted to `DRAFT` inside `update_completeness()`
- [x] No existing column definitions modified (append-only migration)
- [x] All validation checks passed (syntax, types, logic)

---

## Integration Points

### Upstream Dependencies (Completed)

- **US-006:** Document ORM model base exists ✓
- **US-025 / TASK-025-006:** DocumentRepository class exists ✓
- **TASK-026-002:** CompletenessValidator produces CompletenessResult ✓

### Downstream Integration Points

- **Documentation Agent:** Will call `update_completeness()` after document generation
- **Tasks API:** Can now query `completeness_status` and `missing_fields` columns
- **Physician Dashboard:** Can display completeness status and missing field list
- **US-026 Scenario 3:** Config-driven required fields work without code changes

---

## Technical Notes

### Design Decisions

1. **NULL Default:** `completeness_status` defaults to NULL (not "PENDING") to clearly distinguish "not yet validated" from validation states.

2. **JSONB Type:** `missing_fields` uses JSONB for:
   - Native PostgreSQL array handling
   - Index support for querying by specific missing fields
   - Easy JSON serialization for API responses

3. **Status Reversion:** INCOMPLETE documents revert to DRAFT status to prevent premature physician review of incomplete summaries (US-026 AC Scenario 2).

4. **Append-Only Migration:** No modifications to existing columns ensures rollback safety (DR-001).

### Database Impact

- **Storage:** ~25 bytes per document (VARCHAR(20) + empty JSONB array)
- **Index:** No new indexes required (low cardinality on completeness_status)
- **Migration Time:** Instant (default values, no data backfill)

### Error Handling

- `update_completeness()` propagates SQLAlchemy exceptions to caller
- Caller (Documentation Agent) handles retry logic via BaseAgent
- Failed validation persists NULL status (distinguishable from COMPLETE/INCOMPLETE)

---

## Validation Results

```
================================================================================
TASK-026-003 Implementation Validation
================================================================================

1. Validating Document model...
   ✓ JSONB import present
   ✓ completeness_status column present with correct type
   ✓ missing_fields column present with correct type

2. Validating Alembic migration...
   ✓ Migration file exists
   ✓ Revision IDs correct
   ✓ upgrade() function correct
   ✓ downgrade() function correct

3. Validating DocumentRepository...
   ✓ Imports present
   ✓ update_completeness() method present
   ✓ Method signature correct
   ✓ Status update logic correct
   ✓ Commit and refresh logic present

4. Validating Python syntax...
   ✓ backend/app/models/document.py
   ✓ backend/app/db/repositories/document_repository.py
   ✓ backend/alembic/versions/k5h8g1c46f50_add_completeness_columns_to_document.py

================================================================================
Validation Summary
================================================================================
✓ PASSED     Document Model
✓ PASSED     Alembic Migration
✓ PASSED     DocumentRepository
✓ PASSED     Python Syntax
================================================================================

✓ ALL CHECKS PASSED
```

---

## Next Steps

### Immediate (Database Migration)

1. **Run Migration:**
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Verify Schema:**
   ```sql
   \d document
   -- Should show completeness_status VARCHAR(20) NULL
   -- Should show missing_fields JSONB NULL DEFAULT '[]'::jsonb
   ```

### Integration (Documentation Agent)

3. **Update Documentation Agent:**
   - Import `DocumentRepository.update_completeness()`
   - Call after `create_discharge_document()` and `CompletenessValidator.validate()`
   - Example:
     ```python
     document = await repo.create_discharge_document(encounter_id, summary)
     result = validator.validate(summary.model_dump())
     document = await repo.update_completeness(document, result)
     ```

4. **Update Tasks API Endpoint:**
   - Add `completeness_status` and `missing_fields` to response schema
   - Return to frontend for display in physician dashboard

### Testing

5. **Create Unit Tests:**
   - Test `update_completeness()` with COMPLETE result
   - Test `update_completeness()` with INCOMPLETE result
   - Verify status reversion to DRAFT on INCOMPLETE
   - Verify missing_fields list persisted correctly

6. **Integration Test:**
   - Generate discharge summary via Documentation Agent
   - Verify completeness validation runs automatically
   - Verify INCOMPLETE documents held in DRAFT status
   - Verify missing_fields list displayed in UI

---

## Security & Compliance

- **DR-001:** Backwards-compatible migration with safe rollback ✓
- **DR-013:** No PHI in `missing_fields` (field names only, not values) ✓
- **SEC-003:** Structured logging without PHI exposure ✓
- **AIR-012:** Completeness check after every document generation ✓

---

## References

- **Task Spec:** `.propel/context/tasks/EP-004/US-026/task_003_document_model_migration.md`
- **User Story:** US-026 — Document Completeness Validation
- **Epic:** EP-004 — Clinical Document Generation
- **Upstream Tasks:** 
  - TASK-026-001: CompletenessConfig YAML
  - TASK-026-002: CompletenessValidator implementation
- **Migration Chain:** 
  - Previous: j4g7f0b35e49 (US-067 patient opt-out)
  - Current: k5h8g1c46f50 (TASK-026-003)

---

**Implementation Status:** ✓ COMPLETE  
**Validation Status:** ✓ ALL CHECKS PASSED  
**Ready for Integration:** YES  
**Database Migration Required:** YES (run `alembic upgrade head`)
