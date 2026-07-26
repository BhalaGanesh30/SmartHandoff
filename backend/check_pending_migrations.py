"""Check which backend migrations are pending."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
from pathlib import Path

async def check_pending():
    url = "postgresql+asyncpg://postgres:SmartHandoff%40123@localhost:9000/smarthandoff"
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        # Get applied backend migrations (exclude notification service ones)
        result = await conn.execute(text("""
            SELECT version_num 
            FROM alembic_version 
            WHERE version_num NOT IN ('0001', '0002')
            ORDER BY version_num
        """))
        applied = {row[0] for row in result}
    
    await engine.dispose()
    
    # Get all migration files
    versions_dir = Path(__file__).parent / "alembic" / "versions"
    all_revisions = set()
    
    for file in versions_dir.glob("*.py"):
        if file.name == "__init__.py":
            continue
        # Extract revision ID from filename (first part before underscore)
        revision = file.name.split("_")[0]
        all_revisions.add(revision)
    
    # Find pending migrations
    pending = all_revisions - applied
    
    print("\n📊 Migration Status:")
    print("=" * 80)
    print(f"✓ Applied: {len(applied)} migrations")
    print(f"⏳ Pending: {len(pending)} migrations")
    print()
    
    if pending:
        print("Pending migrations:")
        for rev in sorted(pending):
            # Find the full filename
            for file in versions_dir.glob(f"{rev}_*.py"):
                print(f"  • {rev} - {file.name[13:]}")  # Skip revision ID and underscore
    
    print()
    print("Applied backend migrations:")
    for rev in sorted(applied):
        for file in versions_dir.glob(f"{rev}_*.py"):
            print(f"  ✓ {rev} - {file.name[13:]}")

if __name__ == "__main__":
    asyncio.run(check_pending())
