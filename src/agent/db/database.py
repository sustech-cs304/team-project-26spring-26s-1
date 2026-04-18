from __future__ import annotations

import asyncio

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()

_DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./agent.db"
_default_engine: AsyncEngine | None = None
_default_session_factory: async_sessionmaker | None = None
_schema_ready = False
_schema_lock = asyncio.Lock()


def create_sqlite_engine(database_url: str = _DEFAULT_DATABASE_URL) -> AsyncEngine:
    engine = create_async_engine(database_url, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


def get_default_async_engine() -> AsyncEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = create_sqlite_engine()
    return _default_engine


def get_default_session_factory() -> async_sessionmaker:
    global _default_session_factory
    if _default_session_factory is None:
        _default_session_factory = create_session_factory(get_default_async_engine())
    return _default_session_factory


async def ensure_default_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    async with _schema_lock:
        if _schema_ready:
            return
        async with get_default_async_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _schema_ready = True


async def dispose_default_async_engine() -> None:
    global _default_engine, _default_session_factory, _schema_ready
    if _default_engine is not None:
        await _default_engine.dispose()
    _default_engine = None
    _default_session_factory = None
    _schema_ready = False
