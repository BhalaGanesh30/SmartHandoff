"""Check current migration state and encounter schema."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_state():
    url = "postgresql+asyncpg://postgres:SmartHandoff%40123@localhost:9000/smarthandoff"
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        # Check alembic_version
        result = await conn.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num"))
        versions = [row[0] for row in result]
        print("\n📋 Current alembic_version entries:")
        print("=" * 60)
        for v in versions:
            print(f"  • {v}")
        
        # Check encounter table schema
        print("\n🏥 Encounter table columns:")
        print("=" * 60)
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'encounter'
            ORDER BY ordinal_position
        """))
        for row in result:
            print(f"  • {row[0]:<30} {row[1]:<20} (nullable: {row[2]})")
        
        # Check if bed_id exists
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.columns
            WHERE table_name = 'encounter' AND column_name = 'bed_id'
        """))
        has_bed_id = result.scalar() > 0
        print(f"\n{'✓' if has_bed_id else '✗'} bed_id column exists: {has_bed_id}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_state())
