"""Async database engine/session lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_async_engine(database_url: str) -> None:
    """Initialize global async engine/session factory for API runtime."""
    global _engine, _session_factory
    _engine = create_async_engine(database_url, future=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    # Keep SQLite foreign keys consistent with schema design.
    @event.listens_for(_engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


async def dispose_async_engine() -> None:
    """Dispose the async engine on application shutdown."""
    if _engine is not None:
        await _engine.dispose()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Async session factory is not initialized.")
    return _session_factory


def get_async_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Async engine is not initialized.")
    return _engine


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for async SQLAlchemy session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
