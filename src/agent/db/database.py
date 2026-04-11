from __future__ import annotations

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def project_root() -> Path:
    """Repository root directory (directory that contains ``config.yaml``).

    All paths for **agent.db**, ``cron/``, ``runs/``, etc. are derived from here so the
    process working directory does not create multiple database files.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config.yaml").is_file():
            return parent
    return here.parent.parent.parent.parent


def agent_database_path() -> Path:
    """Absolute path to the single app SQLite file: ``<project_root>/agent.db``."""
    return project_root() / "agent.db"


def default_sqlite_database_url() -> str:
    return f"sqlite+aiosqlite:///{agent_database_path().as_posix()}"

def create_sqlite_engine(database_url: str = "sqlite+aiosqlite:///./agent.db") -> AsyncEngine:
	return create_async_engine(database_url, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
	return async_sessionmaker(engine, expire_on_commit=False)
