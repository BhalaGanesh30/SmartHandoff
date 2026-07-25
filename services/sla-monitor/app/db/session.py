"""SQLAlchemy async session factories for SLA monitor.

Provides separate read (replica) and write (primary) session context managers
per TR-010 (read replica routing) and US-021 Technical Notes.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.settings import settings

# Primary (write) engine
_write_engine = create_async_engine(
    settings.database_write_url,
    pool_size=10,
    max_overflow=5,
    echo=False,
)

# Read replica engine (TR-010)
_read_engine = create_async_engine(
    settings.database_read_url,
    pool_size=10,
    max_overflow=5,
    echo=False,
)

_WriteSession = async_sessionmaker(_write_engine, class_=AsyncSession, expire_on_commit=False)
_ReadSession = async_sessionmaker(_read_engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_write_session() -> AsyncIterator[AsyncSession]:
    """Async context manager yielding a write (primary) DB session."""
    async with _WriteSession() as session:
        yield session


@asynccontextmanager
async def get_read_session() -> AsyncIterator[AsyncSession]:
    """Async context manager yielding a read (replica) DB session (TR-010)."""
    async with _ReadSession() as session:
        yield session
