"""Async database engine, session factory, and FastAPI dependency."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .db_models import Base

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

# Default to a local SQLite file inside the project's data/ directory.
# Override via the DATABASE_URL environment variable.
_DEFAULT_DB_PATH = Path.cwd() / "data" / "agent.db"
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{_DEFAULT_DB_PATH}",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # Required for SQLite so that FK constraints are enforced.
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
async_session = async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Lifecycle helpers (called from the FastAPI app)
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Create tables that don't exist yet (development convenience)."""
    # Ensure the parent directory exists for SQLite file-based databases.
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.split("///", 1)[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        # Enable FK enforcement for SQLite (off by default).
        if DATABASE_URL.startswith("sqlite"):
            await conn.execute(text("PRAGMA foreign_keys = ON"))
        await conn.run_sync(Base.metadata.create_all)

        # Create bookkeeping triggers for SQLite (not expressible in SQLAlchemy ORM).
        # These keep conversations.last_message_id / last_message_at / updated_at in sync
        # at the DB level, providing a safety net when Python-side updates are skipped.
        if DATABASE_URL.startswith("sqlite"):
            await conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_messages_after_insert
                AFTER INSERT ON messages
                BEGIN
                  UPDATE conversations
                  SET updated_at      = NEW.updated_at,
                      last_message_id = NEW.message_id,
                      last_message_at = NEW.created_at
                  WHERE conversation_id = NEW.conversation_id;
                END
            """))
            await conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_messages_after_update
                AFTER UPDATE ON messages
                BEGIN
                  UPDATE conversations
                  SET updated_at      = NEW.updated_at,
                      last_message_id = (SELECT message_id FROM messages
                                         WHERE conversation_id = NEW.conversation_id
                                         ORDER BY seq DESC LIMIT 1),
                      last_message_at = (SELECT created_at FROM messages
                                         WHERE conversation_id = NEW.conversation_id
                                         ORDER BY seq DESC LIMIT 1)
                  WHERE conversation_id = NEW.conversation_id;
                END
            """))


async def close_db() -> None:
    """Dispose of the connection pool."""
    await engine.dispose()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` that is automatically closed after the request."""
    async with async_session() as session:
        yield session
