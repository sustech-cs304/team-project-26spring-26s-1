from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class SkillsAuthSnapshot:
    access_token: str | None
    user: dict[str, Any] | None
    updated_at: str | None


class SkillsAuthState:
    """In-memory login state for Skills Hub cloud token."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._access_token: str | None = None
        self._user: dict[str, Any] | None = None
        self._updated_at: str | None = None

    async def set_token(self, access_token: str, user: dict[str, Any] | None = None) -> None:
        async with self._lock:
            self._access_token = access_token
            self._user = user
            self._updated_at = datetime.now(timezone.utc).isoformat()

    async def set_user(self, user: dict[str, Any]) -> None:
        async with self._lock:
            self._user = user
            self._updated_at = datetime.now(timezone.utc).isoformat()

    async def clear(self) -> None:
        async with self._lock:
            self._access_token = None
            self._user = None
            self._updated_at = datetime.now(timezone.utc).isoformat()

    async def get_access_token(self) -> str | None:
        async with self._lock:
            return self._access_token

    async def get_snapshot(self) -> SkillsAuthSnapshot:
        async with self._lock:
            return SkillsAuthSnapshot(
                access_token=self._access_token,
                user=self._user,
                updated_at=self._updated_at,
            )
