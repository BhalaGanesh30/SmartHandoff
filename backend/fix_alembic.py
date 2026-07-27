"""Fix alembic_version table for notification service."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def fix_alembic_version():
    url = "postgresql+asyncpg://postgres:SmartHandoff%40123@localhost:9000/smarthandoff"
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        # Clear existing version entries
        await conn.execute(text("DELETE FROM alembic_version"))
        print("✓ Cleared alembic_version table")
        
        # Add backend revisions
        backend_revisions = ['d5f2a3b14e60', 'l6i9h2d57g61', 'n8k1j4f69i63']
        for rev in backend_revisions:
            await conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{rev}')"))
        print(f"✓ Added {len(backend_revisions)} backend migration revisions")
        
        # Now notification service can add its own
        print("✓ Ready for notification service migrations")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_alembic_version())
