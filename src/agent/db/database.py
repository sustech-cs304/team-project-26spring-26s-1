from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def create_sqlite_engine(database_url: str = "sqlite+aiosqlite:///./agent.db") -> AsyncEngine:
	return create_async_engine(database_url, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
	return async_sessionmaker(engine, expire_on_commit=False)
