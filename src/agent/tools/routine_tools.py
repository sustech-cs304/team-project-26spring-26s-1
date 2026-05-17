"""Agent tools: local routine DB (shared ``agent.db`` with ``/api/events``)."""
from __future__ import annotations

import time

from langchain.tools import tool
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from agent.db.models import RoutineEvent, RoutineSource
from agent.services.calendar_time import (
    format_local_hms,
    format_local_ymd,
    local_ymdhms_to_unix_sec,
)

AGENT_ROUTINE_SOURCE_TITLE = "agent"

_SYNC_DB_URL = f"sqlite:///{"./agent.db"}"

_engine = create_engine(_SYNC_DB_URL, echo=False, future=True)
_SessionLocal = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False, autoflush=False)


def _session() -> Session:
    return _SessionLocal()

def _ensure_agent_source(session: Session) -> RoutineSource:
    row = session.execute(
        select(RoutineSource).where(RoutineSource.title == AGENT_ROUTINE_SOURCE_TITLE)
    ).scalar_one_or_none()
    if row is not None:
        return row
    row = RoutineSource(
        title=AGENT_ROUTINE_SOURCE_TITLE,
        color="#6366f1",
        is_visible=True,
    )
    session.add(row)
    session.flush()
    return row


def _ymd_all_or_none(y: int | None, m: int | None, d: int | None) -> bool:
    t = (y is not None, m is not None, d is not None)
    return not any(t) or all(t)


@tool
def get_my_routine_events(
    start_year: int | None = None,
    start_month: int | None = None,
    start_day: int | None = None,
    end_year: int | None = None,
    end_month: int | None = None,
    end_day: int | None = None,
    start_hour: int = 0,
    start_minute: int = 0,
    start_second: int = 0,
    end_hour: int = 23,
    end_minute: int = 59,
    end_second: int = 59,
    source: str | None = None,
) -> dict:
    """Query events from the local routine DB (same source as the frontend calendar).

    Use **calendar date** and optional **time-of-day** (local wall clock); do not convert to Unix yourself
    — rules match Blackboard tools (see ``calendar_time``).

    For timetable/course/class queries, query the synced calendar instead of BB/TIS directly:
    set ``source`` to ``bb``, ``tis``, or ``bb,tis`` as appropriate.

    - If **all six** date fields are omitted: default window is **14 days** from **now**.
    - If a range is set: provide both ``start_year/month/day`` and ``end_year/month/day``; ``start_hour`` etc. default to 00:00:00 that day, ``end_hour`` etc. default to 23:59:59.
    - ``source`` is optional and filters by calendar source title. It accepts a single source such as ``tis`` or a comma-separated list such as ``bb,tis``.
    - Each row includes id, time (Unix seconds), date (YYYY-MM-DD), local_time (HH:MM:SS), title, description, source title.
    """
    if not _ymd_all_or_none(start_year, start_month, start_day):
        return {
            "success": False,
            "message": "Provide start_year, start_month, start_day together, or omit all three",
            "events": [],
        }
    if not _ymd_all_or_none(end_year, end_month, end_day):
        return {
            "success": False,
            "message": "Provide end_year, end_month, end_day together, or omit all three",
            "events": [],
        }

    start_set = start_year is not None
    end_set = end_year is not None
    if start_set != end_set:
        return {
            "success": False,
            "message": "Start and end dates must both be set, or both omitted for the default 14-day window",
            "events": [],
        }

    now = int(time.time())
    if not start_set:
        st, et = now, now + 14 * 86400
    else:
        assert start_year is not None and start_month is not None and start_day is not None
        assert end_year is not None and end_month is not None and end_day is not None
        try:
            st = local_ymdhms_to_unix_sec(
                int(start_year),
                int(start_month),
                int(start_day),
                int(start_hour),
                int(start_minute),
                int(start_second),
            )
            et = local_ymdhms_to_unix_sec(
                int(end_year),
                int(end_month),
                int(end_day),
                int(end_hour),
                int(end_minute),
                int(end_second),
            )
        except (TypeError, ValueError) as e:
            return {"success": False, "message": f"Invalid date/time: {e}", "events": []}

    if st > et:
        return {"success": False, "message": "Start time must be <= end time", "events": []}

    source_titles = list(dict.fromkeys(
        part.strip().lower()
        for part in (source or "").split(",")
        if part.strip()
    ))

    try:
        with _session() as session:
            stmt = (
                select(RoutineEvent)
                .outerjoin(RoutineSource)
                .where(RoutineEvent.time_ >= st, RoutineEvent.time_ <= et)
                .order_by(RoutineEvent.time_.asc())
            )
            if source_titles:
                stmt = stmt.where(func.lower(RoutineSource.title).in_(source_titles))
            rows = session.scalars(stmt).all()
            events = []
            for r in rows:
                src_title = r.source.title if r.source else ""
                t = int(r.time_)
                events.append(
                    {
                        "id": r.id,
                        "time": t,
                        "date": format_local_ymd(t),
                        "local_time": format_local_hms(t),
                        "title": r.event_name,
                        "description": r.detail,
                        "source": src_title,
                    }
                )
            return {"success": True, "events": events, "count": len(events)}
    except Exception as e:
        return {"success": False, "message": str(e), "events": []}


@tool
def add_routine_event(
    title: str,
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    description: str = "",
) -> dict:
    """Insert one event into the local routine DB; source is fixed to ``agent`` (created if missing).

    Pass **year/month/day** and optional **hour/minute** (default 0); do not use Unix timestamps —
    same conversion as ``bb.py`` / ``calendar_time``.
    """
    title = (title or "").strip()
    if not title:
        return {"success": False, "message": "title must not be empty"}
    try:
        ts = local_ymdhms_to_unix_sec(
            int(year), int(month), int(day), int(hour), int(minute), int(second)
        )
    except (TypeError, ValueError) as e:
        return {"success": False, "message": f"Invalid date/time: {e}"}
    try:
        with _session() as session:
            src = _ensure_agent_source(session)
            ev = RoutineEvent(
                time_=ts,
                end_time_=ts,
                event_name=title,
                detail=(description or "").strip(),
                color=None,
                need_inform=False,
                inform_way=0,
                source_id=src.id,
            )
            session.add(ev)
            session.commit()
            session.refresh(ev)
            return {
                "success": True,
                "id": ev.id,
                "source": AGENT_ROUTINE_SOURCE_TITLE,
                "message": "Saved to routine DB",
            }
    except Exception as e:
        return {"success": False, "message": str(e)}


@tool
def update_routine_event(
    event_id: int,
    title: str | None = None,
    description: str | None = None,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> dict:
    """Update one event by id in the local routine DB (same table as ``PUT /api/events/modify``).

    Provide at least one of ``title``, ``description``, or a **full** ``year``/``month``/``day``. To change time,
    supply ``year``, ``month``, and ``day`` together, and ``hour``/``minute``/``second`` (default 0).
    """
    try:
        eid = int(event_id)
    except (TypeError, ValueError):
        return {"success": False, "message": "Invalid event_id"}

    ymd_partial = (year is not None) + (month is not None) + (day is not None)
    if ymd_partial in (1, 2):
        return {"success": False, "message": "When changing time, provide year, month, and day together"}

    if title is None and description is None and year is None:
        return {"success": False, "message": "Provide at least title, description, or year/month/day"}

    try:
        with _session() as session:
            ev = session.execute(
                select(RoutineEvent).where(RoutineEvent.id == eid)
            ).scalar_one_or_none()
            if ev is None:
                return {"success": False, "message": f"No event with id={eid}"}
            if title is not None:
                ev.event_name = (title or "").strip()
            if year is not None:
                try:
                    ev.time_ = local_ymdhms_to_unix_sec(
                        int(year), int(month), int(day), int(hour), int(minute), int(second)
                    )
                except (TypeError, ValueError) as e:
                    return {"success": False, "message": f"Invalid date/time: {e}"}
            if description is not None:
                ev.detail = (description or "").strip()
            session.commit()
            t = int(ev.time_)
            return {
                "success": True,
                "id": ev.id,
                "time": t,
                "date": format_local_ymd(t),
                "local_time": format_local_hms(t),
                "title": ev.event_name,
                "description": ev.detail,
                "message": "Updated",
            }
    except Exception as e:
        return {"success": False, "message": str(e)}


@tool
def delete_routine_events(event_ids: list[int]) -> dict:
    """Delete events by id list from the local routine DB (same as ``DELETE /api/events/delete``).

    ``event_ids`` is a list of integer ids; multiple rows may be removed in one call.
    """
    if not event_ids:
        return {"success": False, "message": "event_ids must not be empty", "deleted_ids": []}
    try:
        ids = [int(x) for x in event_ids]
    except (TypeError, ValueError):
        return {"success": False, "message": "event_ids must be a list of integers", "deleted_ids": []}
    try:
        with _session() as session:
            existing = session.scalars(
                select(RoutineEvent.id).where(RoutineEvent.id.in_(ids))
            ).all()
            existing_set = set(existing)
            missing = [i for i in ids if i not in existing_set]
            if missing:
                return {
                    "success": False,
                    "message": f"Unknown ids: {missing}",
                    "deleted_ids": [],
                }
            session.execute(delete(RoutineEvent).where(RoutineEvent.id.in_(ids)))
            session.commit()
            return {
                "success": True,
                "deleted_ids": ids,
                "count": len(ids),
                "message": "Deleted",
            }
    except Exception as e:
        return {"success": False, "message": str(e), "deleted_ids": []}
