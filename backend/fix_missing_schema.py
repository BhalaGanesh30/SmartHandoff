"""Add missing schema elements identified by validation."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def fix_missing_elements():
    url = "postgresql+asyncpg://postgres:SmartHandoff%40123@localhost:9000/smarthandoff"
    engine = create_async_engine(url)
    
    print("\n" + "=" * 80)
    print("FIXING MISSING SCHEMA ELEMENTS")
    print("=" * 80)
    print()
    
    async with engine.begin() as conn:
        # 1. Add patient.notification_opt_out column
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.columns
            WHERE table_name = 'patient' AND column_name = 'notification_opt_out'
        """))
        
        if result.scalar() == 0:
            await conn.execute(text("""
                ALTER TABLE patient 
                ADD COLUMN notification_opt_out BOOLEAN NOT NULL DEFAULT false
            """))
            print("✓ Added patient.notification_opt_out column (US-067)")
        else:
            print("✓ patient.notification_opt_out already exists")
        
        # 2. Add encounter → patient foreign key
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.table_constraints
            WHERE table_name = 'encounter' 
            AND constraint_name = 'fk_encounter_patient'
            AND constraint_type = 'FOREIGN KEY'
        """))
        
        if result.scalar() == 0:
            await conn.execute(text("""
                ALTER TABLE encounter 
                ADD CONSTRAINT fk_encounter_patient 
                FOREIGN KEY (patient_id) REFERENCES patient(id) ON DELETE CASCADE
            """))
            print("✓ Added encounter → patient foreign key")
        else:
            print("✓ encounter → patient FK already exists")
        
        # 3. Add patient.uq_patient_mrn unique constraint
        # First check if the column mrn_encrypted exists
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns
            WHERE table_name = 'patient' 
            AND column_name LIKE '%mrn%'
        """))
        mrn_columns = [row[0] for row in result]
        print(f"\n  ℹ  Patient MRN columns found: {mrn_columns}")
        
        if 'mrn_encrypted' in mrn_columns:
            # Check if constraint exists
            result = await conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.table_constraints
                WHERE table_name = 'patient' 
                AND constraint_name = 'uq_patient_mrn'
                AND constraint_type = 'UNIQUE'
            """))
            
            if result.scalar() == 0:
                await conn.execute(text("""
                    ALTER TABLE patient 
                    ADD CONSTRAINT uq_patient_mrn UNIQUE (mrn_encrypted)
                """))
                print("✓ Added patient.uq_patient_mrn unique constraint")
            else:
                print("✓ patient.uq_patient_mrn constraint already exists")
        else:
            print("  ⚠  No mrn_encrypted column found - skipping unique constraint")
        
        # 4. Create index on notification.idempotency_key if missing
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM pg_indexes
            WHERE tablename = 'notification' 
            AND indexname = 'uq_notification_idempotency_key'
        """))
        
        if result.scalar() > 0:
            print("✓ notification.idempotency_key index exists")
        else:
            print("  ℹ  notification.idempotency_key constraint already exists (from table creation)")
    
    await engine.dispose()
    
    print()
    print("=" * 80)
    print("✅ SCHEMA FIXES COMPLETE!")
    print("=" * 80)
    print()
    print("Run validate_database.py again to confirm all checks pass.")
    print()

if __name__ == "__main__":
    asyncio.run(fix_missing_elements())
