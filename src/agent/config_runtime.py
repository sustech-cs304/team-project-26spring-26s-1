from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Protocol

from agent.config import AppConfig, build_patched_config, get_config, save_config, set_config


class ConfigSubscriber(Protocol):
    async def apply_config(self, old_config: AppConfig, new_config: AppConfig) -> None:
        ...


class ConfigManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._subscribers: list[ConfigSubscriber] = []

    def subscribe(self, subscriber: ConfigSubscriber):
        self._subscribers.append(subscriber)

    async def patch(self, delta: Mapping[str, object]) -> AppConfig:
        async with self._lock:
            old_config = get_config()
            new_config = build_patched_config(delta, base_config=old_config)

            for subscriber in self._subscribers:
                await subscriber.apply_config(old_config, new_config)

            set_config(new_config)
            save_config(new_config)
            return new_config
