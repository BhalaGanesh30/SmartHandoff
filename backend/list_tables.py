"""List tables in smarthandoff database."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def list_tables():
    url = "postgresql+asyncpg://postgres:SmartHandoff%40123@localhost:9000/smarthandoff"
    engine = create_async_engine(url)
    
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname='public' 
            ORDER BY tablename
        """))
        tables = [row[0] for row in result]
        
        print("\nTables in smarthandoff database:")
        print("=" * 50)
        for table in tables:
            print(f"  ✓ {table}")
        print(f"\nTotal: {len(tables)} tables")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(list_tables())
