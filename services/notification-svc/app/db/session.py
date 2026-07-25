"""SQLAlchemy async session factory for notification-service.

Provides async session management for database operations.
"""
from __future__ import annotations

import os
from typing import AsyncGenerator

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://localhost/smarthandoff")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=0,
)

# Async session factory
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize database connection pool.
    
    Called on service startup to verify database connectivity.
    """
    async with engine.begin() as conn:
        # Test connection
        await conn.execute(sa.text("SELECT 1"))


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.
    
    Usage:
        @app.post("/endpoint")
        async def handler(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        finally:
            await session.close()
