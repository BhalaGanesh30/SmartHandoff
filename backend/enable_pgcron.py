"""Enable pg_cron extension in postgres database."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def create_extension():
    """Create pg_cron extension in smarthandoff database."""
    # Connect to smarthandoff database (@ symbol is %40 in URL encoding)
    url = "postgresql+asyncpg://postgres:SmartHandoff%40123@localhost:9000/smarthandoff"
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_cron"))
        print("✓ pg_cron extension created in smarthandoff database")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_extension())
