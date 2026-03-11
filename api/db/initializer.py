"""Database initialization via ORM metadata only (no raw SQL)."""

from __future__ import annotations

from api.db.base import Base
from api.db.session import get_async_engine


async def initialize_database() -> None:
    """Create all tables/indexes defined by ORM models.

    This function intentionally relies only on SQLAlchemy ORM metadata.
    """
    # Ensure model modules are imported so metadata is fully populated.
    import api.models.orm  # noqa: F401

    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
