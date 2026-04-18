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


async def start_calendar_sync(
    session_factory: async_sessionmaker,
    *,
    interval_s: float = _DEFAULT_CALENDAR_SYNC_INTERVAL_SECONDS,
    sources: Iterable[str] = _DEFAULT_CALENDAR_SYNC_SOURCES,
) -> asyncio.Task[None]:
    """Ensure calendar schema, perform one sync pass, and start the periodic sync task."""
    async with session_factory() as session:
        await ensure_routine_calendar_schema(session)
        await session.commit()

    normalized_sources = _normalize_sources(sources)
    await _sync_calendar_sources_once(session_factory, normalized_sources)
    task = asyncio.create_task(
        _run_periodic_calendar_sync(session_factory, interval_s, normalized_sources),
        name="calendar-source-sync",
    )
    log.info("Calendar source sync task started")
    return task
