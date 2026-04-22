"""Calendar sync bootstrap and background loop management."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker

from agent.api.routine_events import (
    BB_SOURCE_TITLE,
    TIS_SOURCE_TITLE,
    ensure_routine_calendar_schema,
    sync_managed_source,
)
from agent.config_runtime import SchoolCasConfigChange
from agent.services.school_credentials import missing_cas_message

log = logging.getLogger("calendar.init")

_DEFAULT_CALENDAR_SYNC_INTERVAL_SECONDS = 15 * 60
_DEFAULT_CALENDAR_SYNC_SOURCES = (BB_SOURCE_TITLE, TIS_SOURCE_TITLE)
_MISSING_CREDENTIALS_MESSAGE = missing_cas_message()["message"]


def _normalize_sources(sources: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for source_id in sources:
        value = str(source_id).strip().lower()
        if not value:
            continue
        normalized.append(value)
    return tuple(normalized)


def _is_missing_credentials_error(exc: Exception) -> bool:
    return (
        isinstance(exc, HTTPException)
        and exc.status_code == 400
        and str(exc.detail) == _MISSING_CREDENTIALS_MESSAGE
    )


async def _sync_calendar_source_once(
    session_factory: async_sessionmaker,
    source_id: str,
) -> None:
    async with session_factory() as session:
        try:
            result = await sync_managed_source(source_id, session)
            await session.commit()
            log.info(
                "Calendar source sync completed",
                extra={"source_id": source_id, "event_count": len(result.get("ids", []))},
            )
        except asyncio.CancelledError:
            await session.rollback()
            raise
        except Exception as exc:
            await session.rollback()
            if _is_missing_credentials_error(exc):
                log.info(
                    "Calendar source sync skipped because credentials are not configured",
                    extra={"source_id": source_id},
                )
                return
            log.exception("Calendar source sync failed", extra={"source_id": source_id})


async def _sync_calendar_sources_once(
    session_factory: async_sessionmaker,
    sources: tuple[str, ...],
) -> None:
    await asyncio.gather(
        *(_sync_calendar_source_once(session_factory, source_id) for source_id in sources)
    )


async def _run_periodic_calendar_sync(
    session_factory: async_sessionmaker,
    interval_s: float,
    sources: tuple[str, ...],
) -> None:
    try:
        while True:
            await asyncio.sleep(interval_s)
            await _sync_calendar_sources_once(session_factory, sources)
    except asyncio.CancelledError:
        log.info("Calendar sync background task stopped")
        raise


class CalendarSyncRuntime:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        interval_s: float = _DEFAULT_CALENDAR_SYNC_INTERVAL_SECONDS,
        sources: Iterable[str] = _DEFAULT_CALENDAR_SYNC_SOURCES,
    ):
        self._session_factory = session_factory
        self._interval_s = interval_s
        self._sources = _normalize_sources(sources)
        self._sync_lock = asyncio.Lock()
        self._periodic_task: asyncio.Task[None] | None = None
        self._requested_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        async with self._session_factory() as session:
            await ensure_routine_calendar_schema(session)
            await session.commit()

        self._periodic_task = asyncio.create_task(
            self._run_periodic_sync(),
            name="calendar-source-sync",
        )
        self.request_sync(reason="startup")
        log.info("Calendar source sync task started")

    async def stop(self) -> None:
        tasks = [task for task in (self._periodic_task, self._requested_task) if task is not None]
        self._periodic_task = None
        self._requested_task = None

        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def apply_school_cas_config(self, change: SchoolCasConfigChange) -> None:
        if not change.configured:
            return
        self.request_sync(reason=f"school-cas-{change.action}")

    def request_sync(self, *, reason: str = "manual") -> asyncio.Task[None]:
        if self._requested_task is not None and not self._requested_task.done():
            log.info(
                "Calendar source sync request skipped because one is already pending",
                extra={"reason": reason},
            )
            return self._requested_task

        self._requested_task = asyncio.create_task(
            self._run_requested_sync(reason),
            name="calendar-source-sync-request",
        )
        return self._requested_task

    async def _run_requested_sync(self, reason: str) -> None:
        try:
            await self._sync_once(reason=reason)
        finally:
            if self._requested_task is asyncio.current_task():
                self._requested_task = None

    async def _run_periodic_sync(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._interval_s)
                await self._sync_once(reason="periodic")
        except asyncio.CancelledError:
            log.info("Calendar sync background task stopped")
            raise

    async def _sync_once(self, *, reason: str) -> None:
        async with self._sync_lock:
            log.info("Calendar source sync requested", extra={"reason": reason})
            await _sync_calendar_sources_once(self._session_factory, self._sources)


async def start_calendar_sync(
    session_factory: async_sessionmaker,
    *,
    interval_s: float = _DEFAULT_CALENDAR_SYNC_INTERVAL_SECONDS,
    sources: Iterable[str] = _DEFAULT_CALENDAR_SYNC_SOURCES,
) -> asyncio.Task[None]:
    """Ensure calendar schema and start calendar sync tasks."""
    runtime = CalendarSyncRuntime(session_factory, interval_s=interval_s, sources=sources)
    await runtime.start()
    if runtime._periodic_task is None:
        raise RuntimeError("Calendar source sync task failed to start")
    return runtime._periodic_task
