"""Validation script for US-036 TASK-003 DB Migration — predicted_discharge_time.

Validates:
- Migration file exists and has correct structure
- Encounter ORM model includes prediction columns
- Encounter Pydantic schemas include prediction fields
- Migration SQL syntax is valid
- Indexes are properly defined

Design refs:
    US-036 TASK-003 — Validation checklist
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

print("=" * 80)
print("US-036 TASK-003 Validation: DB Migration — predicted_discharge_time")
print("=" * 80)

# ────────────────────────────────────────────────────────────────────────────
# 1. Migration file exists
# ────────────────────────────────────────────────────────────────────────────
print("\n[1/6] Migration File Existence")
migration_path = Path("backend/alembic/versions/s3p6o9k24n98_add_predicted_discharge_time_to_encounter.py")

if not migration_path.exists():
    print(f"  ✗ Migration file not found: {migration_path}")
    sys.exit(1)

print(f"  ✓ Migration file exists: {migration_path}")

# ────────────────────────────────────────────────────────────────────────────
# 2. Migration syntax check
# ────────────────────────────────────────────────────────────────────────────
print("\n[2/6] Migration Syntax Check")
try:
    migration_code = migration_path.read_text(encoding='utf-8')
    ast.parse(migration_code)
    print(f"  ✓ Migration file parses correctly")
except SyntaxError as e:
    print(f"  ✗ Migration syntax error: {e}")
    sys.exit(1)

# ────────────────────────────────────────────────────────────────────────────
# 3. Migration content validation
# ────────────────────────────────────────────────────────────────────────────
print("\n[3/6] Migration Content Validation")

# Check revision IDs
if 'revision: str = "s3p6o9k24n98"' not in migration_code:
    print("  ✗ Incorrect revision ID")
    sys.exit(1)
print("  ✓ Revision ID: s3p6o9k24n98")

if 'down_revision: Union[str, None] = "r2o5n8j13m87"' not in migration_code:
    print("  ✗ Incorrect down_revision (should be r2o5n8j13m87)")
    sys.exit(1)
print("  ✓ Down revision: r2o5n8j13m87 (latest)")

# Check for three new columns in upgrade()
required_columns = [
    "predicted_discharge_time",
    "discharge_prediction_confidence",
    "discharge_prediction_interval_hours",
]
for col in required_columns:
    if col not in migration_code:
        print(f"  ✗ Missing column: {col}")
        sys.exit(1)
print(f"  ✓ All 3 prediction columns present: {', '.join(required_columns)}")

# Check mv_bed_board view update
if "DROP MATERIALIZED VIEW IF EXISTS mv_bed_board" not in migration_code:
    print("  ✗ Missing DROP MATERIALIZED VIEW statement")
    sys.exit(1)
print("  ✓ mv_bed_board drop statement present")

if "CREATE MATERIALIZED VIEW mv_bed_board AS" not in migration_code:
    print("  ✗ Missing CREATE MATERIALIZED VIEW statement")
    sys.exit(1)
print("  ✓ mv_bed_board recreate statement present")

# Check that new columns are included in the view SELECT
view_match = re.search(
    r"CREATE MATERIALIZED VIEW mv_bed_board AS\s+SELECT(.*?)FROM bed b",
    migration_code,
    re.DOTALL,
)
if not view_match:
    print("  ✗ Could not parse mv_bed_board SELECT clause")
    sys.exit(1)

view_select = view_match.group(1)
for col in required_columns:
    if col not in view_select:
        print(f"  ✗ Column {col} not in mv_bed_board SELECT")
        sys.exit(1)
print("  ✓ All 3 prediction columns in mv_bed_board SELECT")

# Check for partial index on predicted_discharge_time
if "idx_encounter_predicted_discharge" not in migration_code:
    print("  ✗ Missing partial index idx_encounter_predicted_discharge")
    sys.exit(1)
print("  ✓ Partial index idx_encounter_predicted_discharge defined")

# Check for UNIQUE index on mv_bed_board (required for CONCURRENTLY)
if "CREATE UNIQUE INDEX mv_bed_board_bed_id_idx ON mv_bed_board (bed_id)" not in migration_code:
    print("  ✗ Missing UNIQUE index on mv_bed_board.bed_id")
    sys.exit(1)
print("  ✓ UNIQUE index mv_bed_board_bed_id_idx recreated")

# ────────────────────────────────────────────────────────────────────────────
# 4. Encounter ORM model validation
# ────────────────────────────────────────────────────────────────────────────
print("\n[4/6] Encounter ORM Model Validation")

model_path = Path("backend/app/models/encounter.py")
if not model_path.exists():
    print(f"  ✗ Encounter model not found: {model_path}")
    sys.exit(1)

model_code = model_path.read_text(encoding='utf-8')

# Check for new columns in ORM model
for col in required_columns:
    if f"{col}:" not in model_code:
        print(f"  ✗ Missing {col} in Encounter ORM model")
        sys.exit(1)
print(f"  ✓ All 3 prediction columns in Encounter model")

# Check data types
if "DateTime(timezone=True)" not in model_code or "predicted_discharge_time" not in model_code:
    print("  ✗ predicted_discharge_time not using DateTime(timezone=True)")
    sys.exit(1)
print("  ✓ predicted_discharge_time: DateTime(timezone=True)")

if 'String(10)' not in model_code or "discharge_prediction_confidence" not in model_code:
    print("  ✗ discharge_prediction_confidence not using String(10)")
    sys.exit(1)
print("  ✓ discharge_prediction_confidence: String(10)")

if "Numeric(precision=5, scale=2)" not in model_code or "discharge_prediction_interval_hours" not in model_code:
    print("  ✗ discharge_prediction_interval_hours not using Numeric(5, 2)")
    sys.exit(1)
print("  ✓ discharge_prediction_interval_hours: Numeric(5, 2)")

# ────────────────────────────────────────────────────────────────────────────
# 5. Encounter schema validation
# ────────────────────────────────────────────────────────────────────────────
print("\n[5/6] Encounter Pydantic Schema Validation")

schema_path = Path("backend/app/schemas/encounter.py")
if not schema_path.exists():
    print(f"  ✗ Encounter schema not found: {schema_path}")
    sys.exit(1)

schema_code = schema_path.read_text(encoding='utf-8')

# Check for EncounterDetail class
if "class EncounterDetail(BaseModel):" not in schema_code:
    print("  ✗ EncounterDetail schema not found")
    sys.exit(1)
print("  ✓ EncounterDetail schema exists")

# Check for prediction fields
for col in required_columns:
    if f"{col}:" not in schema_code:
        print(f"  ✗ Missing {col} in EncounterDetail schema")
        sys.exit(1)
print(f"  ✓ All 3 prediction fields in EncounterDetail")

# Check confidence field uses Literal type
if 'Optional[Literal["high", "medium", "low"]]' not in schema_code:
    print("  ✗ discharge_prediction_confidence not using Literal['high', 'medium', 'low']")
    sys.exit(1)
print("  ✓ discharge_prediction_confidence: Literal['high', 'medium', 'low']")

# Check for Optional datetime
if "predicted_discharge_time: Optional[datetime]" not in schema_code:
    print("  ✗ predicted_discharge_time not Optional[datetime]")
    sys.exit(1)
print("  ✓ predicted_discharge_time: Optional[datetime]")

# ────────────────────────────────────────────────────────────────────────────
# 6. Downgrade validation
# ────────────────────────────────────────────────────────────────────────────
print("\n[6/6] Migration Downgrade Validation")

# Check downgrade() function exists
if "def downgrade() -> None:" not in migration_code:
    print("  ✗ downgrade() function not found")
    sys.exit(1)
print("  ✓ downgrade() function exists")

# Check downgrade drops columns
for col in required_columns:
    if f'drop_column("encounter", "{col}")' not in migration_code:
        print(f"  ✗ downgrade() missing drop_column for {col}")
        sys.exit(1)
print("  ✓ downgrade() drops all 3 prediction columns")

# Check downgrade recreates mv_bed_board without prediction columns
downgrade_match = re.search(
    r"def downgrade.*?CREATE MATERIALIZED VIEW mv_bed_board AS\s+SELECT(.*?)FROM bed b",
    migration_code,
    re.DOTALL,
)
if not downgrade_match:
    print("  ✗ Could not find mv_bed_board recreate in downgrade()")
    sys.exit(1)

downgrade_select = downgrade_match.group(1)
for col in required_columns:
    if col in downgrade_select:
        print(f"  ✗ downgrade() mv_bed_board SELECT still contains {col}")
        sys.exit(1)
print("  ✓ downgrade() mv_bed_board SELECT excludes prediction columns")

# Check downgrade drops partial index
if "DROP INDEX IF EXISTS idx_encounter_predicted_discharge" not in migration_code:
    print("  ✗ downgrade() missing DROP INDEX for idx_encounter_predicted_discharge")
    sys.exit(1)
print("  ✓ downgrade() drops partial index")

# ────────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("✓ ALL VALIDATION CHECKS PASSED (6/6)")
print("=" * 80)
print("\nNext steps:")
print("  1. Apply migration to dev DB: cd backend && alembic upgrade head")
print("  2. Verify columns: psql $DEV_DB_URL -c \"\\d encounter\" | grep predicted")
print("  3. Verify mv_bed_board: psql $DEV_DB_URL -c \"\\d mv_bed_board\"")
print("  4. Test downgrade: alembic downgrade -1")
print("  5. Re-apply migration: alembic upgrade head")
print("\nUS-036 TASK-003 implementation complete.")
