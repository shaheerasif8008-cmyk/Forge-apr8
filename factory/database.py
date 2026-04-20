"""Async SQLAlchemy engine and session factory for the Forge factory."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from factory.config import get_settings
from factory.models.orm import Base

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> None:
    """Create the async engine (call once at startup)."""
    global _engine, _session_factory
    settings = get_settings()
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.environment == "development",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


def get_engine():
    """Return the shared async engine."""
    if _engine is None:
        raise RuntimeError("Database engine not initialised — call init_engine() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared async sessionmaker."""
    if _session_factory is None:
        raise RuntimeError("Database engine not initialised — call init_engine() first.")
    return _session_factory


async def init_db_schema() -> None:
    """Create all tables for development bootstrap when AUTO_INIT_DB=true."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def close_engine() -> None:
    """Dispose the engine (call at shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session; roll back on error, close always."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
