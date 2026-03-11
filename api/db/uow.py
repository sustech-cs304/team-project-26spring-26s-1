"""Unit-of-work scaffold for explicit transaction boundaries."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    """Simple async UoW wrapper for service-layer transaction control."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc is None:
            await self.session.commit()
        else:
            await self.session.rollback()
