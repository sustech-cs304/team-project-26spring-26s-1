"""Runtime settings for API scaffold."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class APISettings:
    """Minimal settings needed by the API framework layer."""

    database_url: str = "sqlite+aiosqlite:///./data/conversation.db"
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = True

    @classmethod
    def from_env(cls) -> "APISettings":
        return cls(
            database_url=os.getenv("API_DATABASE_URL", "sqlite+aiosqlite:///./data/conversation.db"),
            host=os.getenv("API_HOST", "127.0.0.1"),
            port=int(os.getenv("API_PORT", "8000")),
            reload=os.getenv("API_RELOAD", "true").lower() == "true",
        )
