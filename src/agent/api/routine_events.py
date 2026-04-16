"""Schedule / routine HTTP API — color and source behavior aligned with ``Downloads/routine.py``.

- Event color is stored in ``routine.color``; response ``data[].color`` is the event color (not the source color).
- Default calendar source title is ``user`` (``DEFAULT_SOURCE_TITLE``); creates/updates attach to that source.
- On startup, ``ensure_routine_calendar_schema`` adds ``color`` if missing, ensures default source, backfills ``source_id``.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from typing import List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from icalendar import Calendar
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent.db.models import RoutineEvent, RoutineSource
from agent.services.bb_client import (
    get_calendar_events as fetch_bb_calendar_events,
    login_bb,
)
from agent.services.calendar_time import local_ymdhms_to_bb_ms, local_ymdhms_to_unix_sec
from agent.services.school_credentials import (
    missing_cas_message,
    resolve_bb_credentials,
    resolve_tis_credentials,
)
from agent.services.tis_client import (
    get_schedule_with_semester as fetch_tis_schedule_with_semester,
    login_tis,
)

router = APIRouter(tags=["routine-events"])

# Matches Downloads/routine.py
DEFAULT_SOURCE_TITLE = "user"
DEFAULT_SOURCE_COLOR = "#808080"
DEFAULT_EVENT_COLOR = "#3b82f6"
BB_SOURCE_TITLE = "bb"
TIS_SOURCE_TITLE = "tis"
BB_SOURCE_COLOR = "#2563eb"
TIS_SOURCE_COLOR = "#10b981"
_THREE_MONTH_DAYS = 92
_TIS_SEMESTER_WEEKS = 16
_MANAGED_SOURCE_COLORS = {
    BB_SOURCE_TITLE: BB_SOURCE_COLOR,
    TIS_SOURCE_TITLE: TIS_SOURCE_COLOR,
}
_TIS_PERIOD_WINDOWS: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {
    1: ((8, 0), (9, 50)),
    2: ((8, 0), (9, 50)),
    3: ((10, 20), (12, 10)),
    4: ((10, 20), (12, 10)),
    5: ((14, 0), (15, 50)),
    6: ((14, 0), (15, 50)),
    7: ((16, 20), (18, 10)),
    8: ((16, 20), (18, 10)),
    9: ((19, 0), (20, 50)),
    10: ((19, 0), (20, 50)),
    11: ((21, 0), (21, 50)),
}

_HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
_COLOR_INVALID_MSG = (
    "Invalid color: must be hex with a leading # (#RGB, #RRGGBB, or #RRGGBBAA)"
)


def _validate_optional_hex_color(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError(_COLOR_INVALID_MSG)
    s = v.strip()
    if not _HEX_COLOR_PATTERN.match(s):
        raise ValueError(_COLOR_INVALID_MSG)
    return s


def _normalize_color_value(s: str) -> str:
    if not s:
        return DEFAULT_EVENT_COLOR
    s = s.strip()
    if _HEX_COLOR_PATTERN.match(s):
        return s
    return DEFAULT_EVENT_COLOR


def _local_now() -> datetime:
    return datetime.now()


def _three_month_window() -> tuple[datetime, datetime]:
    now = _local_now()
    start = (now - timedelta(days=_THREE_MONTH_DAYS)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    end = (now + timedelta(days=_THREE_MONTH_DAYS)).replace(
        hour=23,
        minute=59,
        second=59,
        microsecond=0,
    )
    return start, end


def _window_contains(ts: int, start: datetime, end: datetime) -> bool:
    return int(start.timestamp()) <= int(ts) <= int(end.timestamp())


InformType = Literal[
    "none",
    "at_start",
    "5_minutes_before",
    "10_minutes_before",
    "30_minutes_before",
    "1_hour_before",
]


class RoutineCreateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    location: Optional[str] = None
    link: Optional[str] = None
    color: Optional[str] = None
    inform_type: Optional[InformType] = None

    @field_validator("color")
    @classmethod
    def _color_ok(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_hex_color(v)


class RoutineUpdateRequest(BaseModel):
    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    location: Optional[str] = None
    link: Optional[str] = None
    color: Optional[str] = None
    inform_type: Optional[InformType] = None

    @field_validator("color")
    @classmethod
    def _color_ok(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_hex_color(v)


class RoutineQueryRequest(BaseModel):
    id: Optional[int] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    key_word: Optional[str] = None
    source: Optional[str] = None


class Sources(BaseModel):
    color: str = "#808080"
    id: int = 0
    is_visible: bool = True
    title: str = "routine"


class RoutineDatum(BaseModel):
    id: int
    start_time: int
    end_time: int
    title: str
    description: str
    location: str = ""
    link: str = ""
    color: str = "#3b82f6"
    inform_type: InformType = "none"
    source: Sources = Sources()


class RoutineQueryResponse(BaseModel):
    message: str = "OK"
    data: List[RoutineDatum] = []


def _merge_query_int(a: Optional[int], b: Optional[int]) -> Optional[int]:
    """Merge snake_case and camelCase query parameters."""
    return a if a is not None else b


def _merge_query_str(a: Optional[str], b: Optional[str]) -> Optional[str]:
    if a is not None and str(a).strip():
        return a
    if b is not None and str(b).strip():
        return b
    return None


def _inform_type_to_way(inform_type: Optional[InformType]) -> tuple:
    if not inform_type or inform_type == "none":
        return False, 0
    m: dict[str, int] = {
        "at_start": 1,
        "5_minutes_before": 2,
        "10_minutes_before": 3,
        "30_minutes_before": 4,
        "1_hour_before": 5,
    }
    return True, m.get(inform_type, 0)


def _inform_way_to_type(need_inform: bool, inform_way: int) -> InformType:
    if not need_inform:
        return "none"
    m: dict[int, InformType] = {
        0: "none",
        1: "at_start",
        2: "5_minutes_before",
        3: "10_minutes_before",
        4: "30_minutes_before",
        5: "1_hour_before",
    }
    return m.get(inform_way, "none")


def _routine_to_datum(r: RoutineEvent) -> RoutineDatum:
    if r.source:
        src = Sources(
            id=r.source.id,
            title=r.source.title,
            color=_normalize_color_value(r.source.color),
            is_visible=r.source.is_visible,
        )
    else:
        src = Sources()
    return RoutineDatum(
        id=r.id,
        start_time=r.time_,
        end_time=r.end_time_,
        title=r.event_name,
        description=r.detail,
        location="",
        link="",
        color=_normalize_color_value(r.color),
        inform_type=_inform_way_to_type(r.need_inform, r.inform_way),
        source=src,
    )


async def _ensure_default_source(db: AsyncSession) -> int:
    stmt = select(RoutineSource).where(func.lower(RoutineSource.title) == DEFAULT_SOURCE_TITLE).limit(1)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if source:
        return source.id

    source = RoutineSource(
        title=DEFAULT_SOURCE_TITLE,
        color=DEFAULT_SOURCE_COLOR,
        is_visible=True,
    )
    db.add(source)
    await db.flush()
    return source.id


async def _ensure_named_source(
    db: AsyncSession,
    title: str,
    *,
    color: str = DEFAULT_SOURCE_COLOR,
) -> RoutineSource:
    stmt = select(RoutineSource).where(func.lower(RoutineSource.title) == title.lower()).limit(1)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if source is not None:
        if not source.color:
            source.color = color
        return source

    source = RoutineSource(
        title=title,
        color=color,
        is_visible=True,
    )
    db.add(source)
    await db.flush()
    return source


async def _backfill_null_source_id(db: AsyncSession, source_id: int) -> None:
    stmt = (
        update(RoutineEvent)
        .where(RoutineEvent.source_id.is_(None))
        .values(source_id=source_id)
    )
    await db.execute(stmt)


async def _ensure_routine_color_column(db: AsyncSession) -> None:
    result = await db.execute(text("PRAGMA table_info(routine)"))
    columns = {row[1] for row in result.fetchall()}
    if "color" not in columns:
        await db.execute(
            text(
                f"ALTER TABLE routine ADD COLUMN color VARCHAR NOT NULL DEFAULT '{DEFAULT_EVENT_COLOR}'"
            )
        )
    await db.execute(
        update(RoutineEvent)
        .where(or_(RoutineEvent.color.is_(None), RoutineEvent.color == ""))
        .values(color=DEFAULT_EVENT_COLOR)
    )


async def _ensure_routine_end_time_column(db: AsyncSession) -> None:
    result = await db.execute(text("PRAGMA table_info(routine)"))
    columns = {row[1] for row in result.fetchall()}
    if "end_time_" not in columns:
        await db.execute(
            text(
                "ALTER TABLE routine ADD COLUMN end_time_ INTEGER NOT NULL DEFAULT 0"
            )
        )
    await db.execute(
        text(
            "UPDATE routine SET end_time_ = time_ WHERE end_time_ IS NULL OR end_time_ = 0"
        )
    )


async def ensure_routine_calendar_schema(db: AsyncSession) -> None:
    """Called on app startup: column migration, default source, backfill ``source_id`` (Downloads ``routine.py`` lifespan)."""
    await _ensure_routine_color_column(db)
    await _ensure_routine_end_time_column(db)
    source_id = await _ensure_default_source(db)
    await _backfill_null_source_id(db, source_id)


async def get_db(request: Request):
    factory = request.app.state.async_session
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def _create_one(body: RoutineCreateRequest, db: AsyncSession) -> RoutineEvent:
    need_inform, inform_way = _inform_type_to_way(body.inform_type)
    source_id = await _ensure_default_source(db)
    routine = RoutineEvent(
        time_=body.start_time if body.start_time is not None else 0,
        end_time_=body.end_time if body.end_time is not None else (body.start_time if body.start_time is not None else 0),
        event_name=body.title or "",
        detail=body.description or "",
        color=_normalize_color_value(body.color or DEFAULT_EVENT_COLOR),
        need_inform=need_inform,
        inform_way=inform_way,
        source_id=source_id,
    )
    db.add(routine)
    return routine


async def _apply_update(routine: RoutineEvent, body: RoutineUpdateRequest, db: AsyncSession) -> None:
    update_data = body.model_dump(exclude_none=True)
    update_data.pop("id", None)
    if "start_time" in update_data:
        routine.time_ = update_data["start_time"]
        if "end_time" not in update_data:
            routine.end_time_ = update_data["start_time"]
    if "end_time" in update_data:
        routine.end_time_ = update_data["end_time"]
    if "title" in update_data:
        routine.event_name = update_data["title"] or ""
    if "description" in update_data:
        routine.detail = update_data["description"] or ""
    if "color" in update_data:
        routine.color = _normalize_color_value(update_data["color"] or DEFAULT_EVENT_COLOR)
    if "inform_type" in update_data:
        need_inform, inform_way = _inform_type_to_way(update_data["inform_type"])
        routine.need_inform = need_inform
        routine.inform_way = inform_way
    if routine.source_id is None:
        routine.source_id = await _ensure_default_source(db)


@router.post("/events/create")
async def create_routine(body: List[RoutineCreateRequest], db: AsyncSession = Depends(get_db)):
    try:
        for item in body:
            if item.start_time is not None and item.end_time is not None and item.start_time > item.end_time:
                raise HTTPException(status_code=400, detail="start_time must be <= end_time")
        ids: list[int] = []
        for item in body:
            r = await _create_one(item, db)
            await db.flush()
            ids.append(r.id)
        return {"message": "Routine created", "ids": ids}
    except HTTPException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)


@router.put("/events/modify")
async def update_routine(body: List[RoutineUpdateRequest], db: AsyncSession = Depends(get_db)):
    try:
        for item in body:
            if item.start_time is not None and item.end_time is not None and item.start_time > item.end_time:
                raise HTTPException(status_code=400, detail="start_time must be <= end_time")
        ids: list[int] = []
        for item in body:
            stmt = select(RoutineEvent).outerjoin(RoutineSource).where(RoutineEvent.id == item.id)
            result = await db.execute(stmt)
            routine = result.scalar_one_or_none()
            if not routine:
                raise HTTPException(status_code=404, detail="Routine not found")
            source_title = (routine.source.title if routine.source else DEFAULT_SOURCE_TITLE).strip().lower()
            if source_title != DEFAULT_SOURCE_TITLE:
                raise HTTPException(status_code=400, detail="Invalid request parameters")
            await _apply_update(routine, item, db)
            ids.append(routine.id)
        await db.flush()
        return {"message": "Routine updated", "ids": ids}
    except HTTPException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)


@router.get(
    "/events",
    summary="Query events (query string only; no path parameters)",
)
async def query_routines(
    id: Optional[int] = Query(
        None,
        description="If set, return exactly one row by id; mutually exclusive with start_time/end_time range",
    ),
    start_time: Optional[int] = Query(
        None,
        description="Range query: start Unix seconds (use with end_time)",
    ),
    startTime: Optional[int] = Query(
        None,
        description="Alias for start_time (camelCase)",
    ),
    end_time: Optional[int] = Query(
        None,
        description="Range query: end Unix seconds",
    ),
    endTime: Optional[int] = Query(
        None,
        description="Alias for end_time (camelCase)",
    ),
    key_word: Optional[str] = Query(
        None,
        description="Case-insensitive substring match on title and description (event_name, detail)",
    ),
    keyWord: Optional[str] = Query(
        None,
        description="Alias for key_word (camelCase)",
    ),
    source: Optional[str] = Query(
        None,
        description="Exact match on calendar source title",
    ),
    db: AsyncSession = Depends(get_db),
):
    st = _merge_query_int(start_time, startTime)
    et = _merge_query_int(end_time, endTime)
    kw = _merge_query_str(key_word, keyWord)
    body = RoutineQueryRequest(
        id=id,
        start_time=st,
        end_time=et,
        key_word=kw,
        source=source,
    )
    try:
        if body.id is not None:
            stmt = select(RoutineEvent).outerjoin(RoutineSource).where(RoutineEvent.id == body.id)
            result = await db.execute(stmt)
            routine = result.scalar_one_or_none()
            if not routine:
                raise HTTPException(status_code=400, detail="Routine not found")
            return RoutineQueryResponse(message="OK", data=[_routine_to_datum(routine)])

        if body.start_time is None or body.end_time is None:
            raise HTTPException(
                status_code=400,
                detail="start_time and end_time are required when id is not provided",
            )
        if body.start_time > body.end_time:
            raise HTTPException(status_code=400, detail="start_time must be <= end_time")
        conditions = [
            RoutineEvent.end_time_ >= body.start_time,
            RoutineEvent.time_ <= body.end_time,
        ]
        if body.key_word and body.key_word.strip():
            kw = body.key_word.strip()
            pattern = f"%{kw.lower()}%"
            conditions.append(
                or_(
                    func.lower(RoutineEvent.event_name).like(pattern),
                    func.lower(RoutineEvent.detail).like(pattern),
                )
            )
        if body.source is not None and body.source.strip():
            conditions.append(RoutineSource.title == body.source.strip())
        stmt = (
            select(RoutineEvent)
            .outerjoin(RoutineSource)
            .where(and_(*conditions))
            .order_by(RoutineEvent.time_.asc())
        )
        result = await db.execute(stmt)
        routines = result.scalars().all()
        data = [_routine_to_datum(r) for r in routines]
    except HTTPException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)
    return RoutineQueryResponse(message="OK", data=data)


@router.delete("/events/delete")
async def delete_routines(body: List[int], db: AsyncSession = Depends(get_db)):
    if not body:
        return {"message": "Routine deleted", "ids": []}
    try:
        result = await db.execute(
            select(RoutineEvent)
            .outerjoin(RoutineSource)
            .where(RoutineEvent.id.in_(body))
        )
        routines = result.scalars().all()
        existing = {row.id for row in routines}
        missing = [i for i in body if i not in existing]
        if missing:
            raise HTTPException(status_code=404, detail=f"Routine not found: {missing}")
        for routine in routines:
            source_title = (routine.source.title if routine.source else DEFAULT_SOURCE_TITLE).strip().lower()
            if source_title != DEFAULT_SOURCE_TITLE:
                raise HTTPException(status_code=400, detail="Invalid request parameters")
        stmt = delete(RoutineEvent).where(RoutineEvent.id.in_(body))
        await db.execute(stmt)
        await db.flush()
    except HTTPException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)
    return {"message": "Routine deleted", "ids": body}


class SourceUpdateRequest(BaseModel):
    color: Optional[str] = None
    is_visible: Optional[bool] = None

    @field_validator("color")
    @classmethod
    def _color_ok(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_hex_color(v)


def _source_to_dict(s: RoutineSource) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "color": _normalize_color_value(s.color),
        "is_visible": s.is_visible,
    }


def _get_ical_url_for_source(source_id: int) -> str:
    key = f"ICAL_URL_{source_id}"
    url = os.environ.get(key, "").strip()
    if not url:
        raise HTTPException(status_code=400, detail=f"ICAL url not configured for source {source_id}")
    return url


async def _replace_source_routines(
    source: RoutineSource,
    events: list[dict[str, object]],
    db: AsyncSession,
) -> List[int]:
    await db.execute(delete(RoutineEvent).where(RoutineEvent.source_id == source.id))
    ids: List[int] = []

    for item in events:
        time_ = int(item.get("time_", 0))
        end_time_ = int(item.get("end_time_", time_))
        routine = RoutineEvent(
            time_=time_,
            end_time_=end_time_,
            event_name=str(item.get("event_name") or ""),
            detail=str(item.get("detail") or ""),
            color=_normalize_color_value(str(item.get("color") or DEFAULT_EVENT_COLOR)),
            need_inform=False,
            inform_way=0,
            source_id=source.id,
        )
        db.add(routine)
        await db.flush()
        ids.append(routine.id)

    return ids


async def _replace_routines_from_ical(source: RoutineSource, ics_text: str, db: AsyncSession) -> List[int]:
    try:
        cal = Calendar.from_ical(ics_text)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid iCal data")

    events: list[dict[str, object]] = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        dtstart = component.get("DTSTART")
        if not dtstart:
            continue
        dt = dtstart.dt
        if isinstance(dt, datetime):
            ts = int(dt.timestamp())
        else:
            continue
        dtend = component.get("DTEND")
        end_ts = ts
        if dtend and isinstance(dtend.dt, datetime):
            end_ts = int(dtend.dt.timestamp())
        summary = component.get("SUMMARY")
        description = component.get("DESCRIPTION")
        events.append(
            {
                "time_": ts,
                "end_time_": end_ts,
                "event_name": str(summary) if summary is not None else "",
                "detail": str(description) if description is not None else "",
                "color": DEFAULT_EVENT_COLOR,
            }
        )
    return await _replace_source_routines(source, events, db)


def _extract_list_payload(payload: object, *keys: str) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_list_payload(
                value,
                "list",
                "items",
                "events",
                "kbList",
                "xszykbList",
                "rows",
                "records",
                "result",
                "data",
            )
            if nested:
                return nested
    return []


def _parse_date_only(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parse_time_text(value: object) -> tuple[int, int, int] | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.hour, value.minute, value.second
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)


def _parse_ts_from_value(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return local_ymdhms_to_unix_sec(
            value.year, value.month, value.day, value.hour, value.minute, value.second
        )
    if isinstance(value, (int, float)):
        raw = int(value)
        return raw // 1000 if abs(raw) >= 10**12 else raw

    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"-?\d+", text):
        raw = int(text)
        return raw // 1000 if abs(raw) >= 10**12 else raw
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return local_ymdhms_to_unix_sec(
        parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second
    )


def _join_detail_lines(parts: list[str]) -> str:
    return "\n".join(part for part in parts if part)


def _build_bb_event_detail(item: dict) -> str:
    detail_parts: list[str] = []
    description = item.get("description") or item.get("body") or item.get("details")
    location = item.get("location") or item.get("where")
    course = item.get("courseName") or item.get("course_name")
    if description:
        detail_parts.append(str(description))
    if course:
        detail_parts.append(f"Course: {course}")
    if location:
        detail_parts.append(f"Location: {location}")
    return _join_detail_lines(detail_parts)


def _bb_payload_to_events(payload: object, start: datetime, end: datetime) -> list[dict[str, object]]:
    items = _extract_list_payload(payload, "events", "calendarEvents", "data", "items", "results")
    events: list[dict[str, object]] = []
    for item in items:
        ts = None
        for key in ("startDate", "start", "eventDate", "calendarDate", "startTime", "timestamp"):
            ts = _parse_ts_from_value(item.get(key))
            if ts is not None:
                break
        if ts is None or not _window_contains(ts, start, end):
            continue
        end_ts = ts
        for key in ("endDate", "end", "eventEndDate", "endTime"):
            parsed_end = _parse_ts_from_value(item.get(key))
            if parsed_end is not None:
                end_ts = parsed_end
                break
        title = (
            item.get("title")
            or item.get("eventName")
            or item.get("name")
            or item.get("subject")
            or ""
        )
        color = (
            item.get("borderColor")
            or item.get("color")
            or item.get("backgroundColor")
            or BB_SOURCE_COLOR
        )
        events.append(
            {
                "time_": ts,
                "end_time_": end_ts,
                "event_name": str(title),
                "detail": _build_bb_event_detail(item),
                "color": str(color),
            }
        )
    return events


def _parse_weekday(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 7 else None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        num = int(text)
        return num if 1 <= num <= 7 else None
    mapping = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "日": 7,
        "天": 7,
        "周一": 1,
        "周二": 2,
        "周三": 3,
        "周四": 4,
        "周五": 5,
        "周六": 6,
        "周日": 7,
        "周天": 7,
        "星期一": 1,
        "星期二": 2,
        "星期三": 3,
        "星期四": 4,
        "星期五": 5,
        "星期六": 6,
        "星期日": 7,
        "星期天": 7,
    }
    return mapping.get(text)


def _parse_period_numbers(value: object) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value] if value > 0 else []
    if isinstance(value, list):
        out: list[int] = []
        for item in value:
            if isinstance(item, int) and int(item) > 0:
                out.append(int(item))
                continue
            if isinstance(item, str):
                out.extend(int(n) for n in re.findall(r"\d+", item) if int(n) > 0)
        return sorted(set(out))
    text = str(value).strip()
    if not text:
        return []
    nums = [int(n) for n in re.findall(r"\d+", text)]
    return sorted(num for num in nums if num > 0)


def _extract_tis_semester_start(semester_info: dict, items: list[dict]) -> date | None:
    sample_rwh = ""
    for item in items:
        sample_rwh = str(item.get("RWH") or "").strip()
        if sample_rwh:
            break

    years = [int(part) for part in re.findall(r"\d{4}", sample_rwh)]
    term_match = re.search(r"\d{4}-\d{4}-(\d+)-", sample_rwh) if sample_rwh else None
    term = term_match.group(1) if term_match is not None else str(semester_info.get("p_xq") or "").strip()

    if years and term == "1":
        anchor_year = years[0]
    elif years:
        anchor_year = years[-1] if len(years) > 1 else years[0]
    else:
        anchor_year = _local_now().year

    feb22 = date(anchor_year, 2, 22)
    return feb22 - timedelta(days=feb22.weekday())


def _resolve_tis_period_window(item: dict) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    for key in ("kssj", "startTime", "sksj", "courseStartTime"):
        parsed = _parse_time_text(item.get(key))
        if parsed is not None:
            end_parsed = None
            for end_key in ("jssj", "endTime", "courseEndTime"):
                end_parsed = _parse_time_text(item.get(end_key))
                if end_parsed is not None:
                    break
            if end_parsed is not None:
                return parsed, end_parsed
            return parsed, parsed
    period_numbers: list[int] = []
    for key in ("jcs", "jc", "jcdm2", "skjc", "sksj"):
        period_numbers = _parse_period_numbers(item.get(key))
        if period_numbers:
            break
    if not period_numbers:
        ksjc = item.get("KSJC")
        jsjc = item.get("JSJC")
        if isinstance(ksjc, int) and isinstance(jsjc, int) and ksjc > 0 and jsjc > 0:
            period_numbers = [int(ksjc), int(jsjc)]
    if not period_numbers:
        return (8, 0, 0), (8, 0, 0)
    start_period, end_period = period_numbers[0], period_numbers[-1]
    start_window = _TIS_PERIOD_WINDOWS.get(start_period)
    end_window = _TIS_PERIOD_WINDOWS.get(end_period)
    if start_window is not None and end_window is not None:
        return (
            start_window[0][0],
            start_window[0][1],
            0,
        ), (
            end_window[1][0],
            end_window[1][1],
            0,
        )
    return (8, 0, 0), (8, 0, 0)


def _tis_weekday_from_key(item: dict) -> int | None:
    key = str(item.get("KEY") or "").strip().lower()
    match = re.search(r"xq(\d+)", key)
    if match:
        weekday = int(match.group(1))
        if 1 <= weekday <= 7:
            return weekday
    for key_name in ("xqj", "xqjmc", "weekday", "dayOfWeek", "xq", "weekDay"):
        weekday = _parse_weekday(item.get(key_name))
        if weekday is not None:
            return weekday
    return None


def _parse_tis_week_bitmap(value: object) -> list[int]:
    text = str(value or "").strip()
    if not text:
        return []
    if re.fullmatch(r"[01]+", text):
        weeks: list[int] = []
        has_padding = len(text) > 1 and text[0] == "0"
        for idx, char in enumerate(text):
            if char != "1":
                continue
            if has_padding:
                if idx == 0:
                    continue
                weeks.append(idx)
            else:
                weeks.append(idx + 1)
        return weeks
    return []


def _parse_tis_sksj_text(raw: object) -> dict[str, str]:
    text = str(raw or "").strip()
    if not text:
        return {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    out: dict[str, str] = {}
    if lines:
        out["title"] = lines[0]
    if len(lines) >= 2:
        out["teacher"] = lines[1].strip("[]")
    if len(lines) >= 4:
        groups = re.findall(r"\[([^\]]*)\]", lines[3])
        if len(groups) >= 1:
            out["weeks_text"] = groups[0]
        if len(groups) >= 2:
            out["location"] = groups[1]
        if len(groups) >= 3:
            out["periods_text"] = groups[2]
    return out


def _build_tis_detail(item: dict) -> str:
    parsed_text = _parse_tis_sksj_text(item.get("SKSJ") or item.get("SKSJ_EN"))
    parts: list[str] = []
    teacher = (
        parsed_text.get("teacher")
        or item.get("xm")
        or item.get("jsxm")
        or item.get("teacher")
        or item.get("jsmc")
        or item.get("skls")
    )
    location = (
        parsed_text.get("location")
        or item.get("cdmc")
        or item.get("location")
        or item.get("jxcdmc")
        or item.get("jsmc")
        or item.get("room")
    )
    weeks_text = parsed_text.get("weeks_text")
    periods = (
        parsed_text.get("periods_text")
        or item.get("jcs")
        or item.get("jc")
        or item.get("jcdm2")
        or item.get("skjc")
        or item.get("sksj")
    )
    if teacher:
        parts.append(f"Teacher: {teacher}")
    if location:
        parts.append(f"Location: {location}")
    if weeks_text:
        parts.append(f"Weeks: {weeks_text}")
    if periods:
        parts.append(f"Periods: {periods}")
    return _join_detail_lines(parts)


def _tis_item_to_events(
    item: dict,
    semester_start: date,
    start: datetime,
    end: datetime,
) -> list[dict[str, object]]:
    parsed_text = _parse_tis_sksj_text(item.get("SKSJ") or item.get("SKSJ_EN"))
    title = (
        parsed_text.get("title")
        or item.get("kcmc")
        or item.get("rwmc")
        or item.get("courseName")
        or item.get("name")
        or item.get("mc")
        or item.get("title")
        or ""
    )
    detail = _build_tis_detail(item)

    explicit_date = None
    for key in ("skrq", "date", "rq", "courseDate", "kcrq", "sjrq"):
        explicit_date = _parse_date_only(item.get(key))
        if explicit_date is not None:
            break

    (start_hour, start_minute, start_second), (end_hour, end_minute, end_second) = _resolve_tis_period_window(item)
    if explicit_date is not None:
        ts = local_ymdhms_to_unix_sec(
            explicit_date.year,
            explicit_date.month,
            explicit_date.day,
            start_hour,
            start_minute,
            start_second,
        )
        end_ts = local_ymdhms_to_unix_sec(
            explicit_date.year,
            explicit_date.month,
            explicit_date.day,
            end_hour,
            end_minute,
            end_second,
        )
        if _window_contains(ts, start, end):
            return [{
                "time_": ts,
                "end_time_": end_ts,
                "event_name": str(title),
                "detail": detail,
                "color": TIS_SOURCE_COLOR,
            }]
        return []

    weekday = _tis_weekday_from_key(item)
    if weekday is None:
        return []

    weeks = _parse_tis_week_bitmap(item.get("ZC"))
    if not weeks:
        return []

    events: list[dict[str, object]] = []
    for week in weeks:
        class_date = semester_start + timedelta(days=(week - 1) * 7 + (weekday - 1))
        ts = local_ymdhms_to_unix_sec(
            class_date.year,
            class_date.month,
            class_date.day,
            start_hour,
            start_minute,
            start_second,
        )
        end_ts = local_ymdhms_to_unix_sec(
            class_date.year,
            class_date.month,
            class_date.day,
            end_hour,
            end_minute,
            end_second,
        )
        if not _window_contains(ts, start, end):
            continue
        events.append(
            {
                "time_": ts,
                "end_time_": end_ts,
                "event_name": str(title),
                "detail": detail,
                "color": TIS_SOURCE_COLOR,
            }
        )
    return events


def _tis_payload_to_events(
    payload: object,
    semester_info: dict,
) -> list[dict[str, object]]:
    items = _extract_list_payload(
        payload,
        "kbList",
        "xszykbList",
        "data",
        "items",
        "list",
        "rows",
        "records",
        "result",
    )
    semester_start = _extract_tis_semester_start(semester_info, items)
    if semester_start is None:
        raise HTTPException(status_code=400, detail="Cannot determine TIS semester start date")
    start = datetime.combine(semester_start, datetime.min.time())
    end = start + timedelta(weeks=_TIS_SEMESTER_WEEKS, seconds=-1)
    events: list[dict[str, object]] = []
    for item in items:
        events.extend(_tis_item_to_events(item, semester_start, start, end))
    return events


async def _replace_routines_from_bb(source: RoutineSource, db: AsyncSession) -> List[int]:
    user_name, pwd = resolve_bb_credentials(None, None)
    if not user_name or not pwd:
        raise HTTPException(status_code=400, detail=missing_cas_message()["message"])

    login_result = await login_bb(user_name, pwd)
    if not login_result["success"]:
        raise HTTPException(status_code=400, detail=login_result["message"])

    start, end = _three_month_window()
    try:
        result = await fetch_bb_calendar_events(
            login_result["session"],
            start_ms=local_ymdhms_to_bb_ms(start.year, start.month, start.day, 0, 0, 0),
            end_ms=local_ymdhms_to_bb_ms(end.year, end.month, end.day, 23, 59, 59),
            mode="personal",
        )
    finally:
        await login_result["session"].close()

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    events = _bb_payload_to_events(result.get("data"), start, end)
    return await _replace_source_routines(source, events, db)


async def _replace_routines_from_tis(source: RoutineSource, db: AsyncSession) -> List[int]:
    user_name, pwd = resolve_tis_credentials(None, None)
    if not user_name or not pwd:
        raise HTTPException(status_code=400, detail=missing_cas_message()["message"])

    login_result = await login_tis(user_name, pwd)
    if not login_result["success"]:
        raise HTTPException(status_code=400, detail=login_result["message"])

    try:
        result = await fetch_tis_schedule_with_semester(login_result["session"])
    finally:
        await login_result["session"].close()

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    events = _tis_payload_to_events(result.get("data"), result.get("semester") or {})
    return await _replace_source_routines(source, events, db)


async def sync_managed_source(source_id: str, db: AsyncSession) -> dict[str, object]:
    normalized = source_id.strip().lower()
    if normalized == BB_SOURCE_TITLE:
        source = await _ensure_named_source(db, BB_SOURCE_TITLE, color=BB_SOURCE_COLOR)
        ids = await _replace_routines_from_bb(source, db)
        return {"message": "Routine updated", "ids": ids, "source": source.title}
    if normalized == TIS_SOURCE_TITLE:
        source = await _ensure_named_source(db, TIS_SOURCE_TITLE, color=TIS_SOURCE_COLOR)
        ids = await _replace_routines_from_tis(source, db)
        return {"message": "Routine updated", "ids": ids, "source": source.title}
    raise HTTPException(status_code=404, detail="Source not found")


async def _update_source_from_ical(source_numeric_id: int, db: AsyncSession) -> dict:
    stmt = select(RoutineSource).where(RoutineSource.id == source_numeric_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    url = _get_ical_url_for_source(source_numeric_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch iCal url")
    ids = await _replace_routines_from_ical(source, resp.text, db)
    return {"message": "Routine updated", "ids": ids, "source": source.title}


@router.get("/events/sources")
async def get_sources(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(RoutineSource).order_by(RoutineSource.id.asc()))
        sources = result.scalars().all()
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)
    return [_source_to_dict(s) for s in sources]


@router.patch("/events/sources/{source_id}")
async def update_source(source_id: int, body: SourceUpdateRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(RoutineSource).where(RoutineSource.id == source_id)
        result = await db.execute(stmt)
        src = result.scalar_one_or_none()
        if not src:
            raise HTTPException(status_code=404, detail="Source not found")
        update_data = body.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(src, field, value)
        await db.flush()
    except HTTPException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)
    return _source_to_dict(src)


@router.patch("/events/update/{source_id}")
async def update_source_events(source_id: str, db: AsyncSession = Depends(get_db)):
    """Replace one calendar source from BB/TIS sync or legacy iCal source id."""
    try:
        normalized = source_id.strip().lower()
        if normalized in _MANAGED_SOURCE_COLORS:
            return await sync_managed_source(normalized, db)
        if normalized.isdigit():
            return await _update_source_from_ical(int(normalized), db)
        raise HTTPException(status_code=404, detail="Source not found")
    except HTTPException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)
