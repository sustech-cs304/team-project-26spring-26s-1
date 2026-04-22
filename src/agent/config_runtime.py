from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol

from agent.config import AppConfig, build_patched_config, get_config, save_config, set_config


@dataclass(frozen=True, slots=True)
class SchoolCasConfigChange:
    action: Literal["patch"]
    configured: bool
    student_id: str | None = None
    password_updated: bool = False
    storage: str | None = None


class AppConfigSubscriber(Protocol):
    async def apply_config(self, old_config: AppConfig, new_config: AppConfig) -> None:
        ...


class SchoolCasConfigSubscriber(Protocol):
    async def apply_school_cas_config(self, change: SchoolCasConfigChange) -> None:
        ...


class ConfigManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._subscribers: list[object] = []

    def subscribe(self, subscriber: AppConfigSubscriber | SchoolCasConfigSubscriber):
        self._subscribers.append(subscriber)

    async def patch(self, delta: Mapping[str, object]) -> AppConfig:
        async with self._lock:
            old_config = get_config()
            new_config = build_patched_config(delta, base_config=old_config)

            await self._notify("apply_config", old_config, new_config)

            set_config(new_config)
            save_config(new_config)
            return new_config

    async def notify_school_cas_config_changed(self, change: SchoolCasConfigChange) -> None:
        async with self._lock:
            await self._notify("apply_school_cas_config", change)

    async def _notify(self, method_name: str, *args: object) -> None:
        for subscriber in self._subscribers:
            handler = getattr(subscriber, method_name, None)
            if handler is None:
                continue
            await handler(*args)
