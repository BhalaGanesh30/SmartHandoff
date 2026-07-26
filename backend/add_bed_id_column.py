"""Add bed_id foreign key to encounter table."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def add_bed_id_column():
    url = "postgresql+asyncpg://postgres:SmartHandoff%40123@localhost:9000/smarthandoff"
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        # Check if bed_id already exists
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.columns
            WHERE table_name = 'encounter' AND column_name = 'bed_id'
        """))
        has_bed_id = result.scalar() > 0
        
        if has_bed_id:
            print("✓ bed_id column already exists")
        else:
            # Add bed_id column
            await conn.execute(text("""
                ALTER TABLE encounter 
                ADD COLUMN bed_id UUID
            """))
            print("✓ Added bed_id column to encounter table")
            
            # Add foreign key constraint
            await conn.execute(text("""
                ALTER TABLE encounter 
                ADD CONSTRAINT fk_encounter_bed 
                FOREIGN KEY (bed_id) REFERENCES bed(id) ON DELETE SET NULL
            """))
            print("✓ Added foreign key constraint to bed table")
            
            # Add index for better query performance
            await conn.execute(text("""
                CREATE INDEX ix_encounter_bed_id ON encounter(bed_id)
            """))
            print("✓ Added index on bed_id")
    
    await engine.dispose()
    print("\n✅ Encounter table updated successfully!")

if __name__ == "__main__":
    asyncio.run(add_bed_id_column())
