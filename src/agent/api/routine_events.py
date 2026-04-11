"""Schedule / routine HTTP API — color and source behavior aligned with ``Downloads/routine.py``.

- Event color is stored in ``routine.color``; response ``data[].color`` is the event color (not the source color).
- Default calendar source title is ``user`` (``DEFAULT_SOURCE_TITLE``); creates/updates attach to that source.
- On startup, ``ensure_routine_calendar_schema`` adds ``color`` if missing, ensures default source, backfills ``source_id``.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from icalendar import Calendar
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent.db.models import RoutineEvent, RoutineSource

router = APIRouter(tags=["routine-events"])

# Matches Downloads/routine.py
DEFAULT_SOURCE_TITLE = "user"
DEFAULT_SOURCE_COLOR = "#808080"
DEFAULT_EVENT_COLOR = "#3b82f6"

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
        end_time=r.time_,
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


async def ensure_routine_calendar_schema(db: AsyncSession) -> None:
    """Called on app startup: column migration, default source, backfill ``source_id`` (Downloads ``routine.py`` lifespan)."""
    await _ensure_routine_color_column(db)
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
            stmt = select(RoutineEvent).where(RoutineEvent.id == item.id)
            result = await db.execute(stmt)
            routine = result.scalar_one_or_none()
            if not routine:
                raise HTTPException(status_code=404, detail="Routine not found")
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
            RoutineEvent.time_ >= body.start_time,
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
        result = await db.execute(select(RoutineEvent.id).where(RoutineEvent.id.in_(body)))
        existing = {row[0] for row in result.all()}
        missing = [i for i in body if i not in existing]
        if missing:
            raise HTTPException(status_code=404, detail=f"Routine not found: {missing}")
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


async def _replace_routines_from_ical(source: RoutineSource, ics_text: str, db: AsyncSession) -> List[int]:
    try:
        cal = Calendar.from_ical(ics_text)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid iCal data")

    await db.execute(delete(RoutineEvent).where(RoutineEvent.source_id == source.id))
    ids: List[int] = []

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
        summary = component.get("SUMMARY")
        description = component.get("DESCRIPTION")
        routine = RoutineEvent(
            time_=ts,
            event_name=str(summary) if summary is not None else "",
            detail=str(description) if description is not None else "",
            need_inform=False,
            inform_way=0,
            source_id=source.id,
        )
        db.add(routine)
        await db.flush()
        ids.append(routine.id)

    return ids


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


@router.patch("/events/update/{event_id}")
async def update_event_from_ical(event_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch iCal from ``ICAL_URL_{event_id}`` and replace events for that calendar source."""
    try:
        stmt = select(RoutineSource).where(RoutineSource.id == event_id)
        result = await db.execute(stmt)
        source = result.scalar_one_or_none()
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        url = _get_ical_url_for_source(event_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch iCal url")
        ids = await _replace_routines_from_ical(source, resp.text, db)
        return {"message": "Routine updated", "ids": ids}
    except HTTPException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)
