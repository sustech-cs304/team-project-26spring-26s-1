"""Local wall-clock conversion aligned with repo-root ``bb.py`` ``standardize_time``.

Blackboard calendar APIs use **milliseconds**; local routine ``routine.time_`` uses **Unix seconds**.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

# Match bb.py: ms anchor relative to 2026-01-01 + calendar-day deltas
_BB_REF = datetime(2026, 1, 1)
_BB_MS_ORIGIN = 1767196800000


def standardize_time(year: int, month: int, day: int) -> int:
    """Milliseconds at 00:00 for the given date (same as ``bb.py`` ``standardize_time``)."""
    input_dt = datetime(year, month, day)
    return _BB_MS_ORIGIN + (input_dt - _BB_REF).days * 86400000


def local_ymdhms_to_bb_ms(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> int:
    """year/month/day/hour/minute/second -> Blackboard **milliseconds** (local wall clock)."""
    base_ms = standardize_time(year, month, day)
    return base_ms + hour * 3600000 + minute * 60000 + second * 1000


def local_ymdhms_to_unix_sec(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> int:
    """year/month/day/hour/minute/second -> Unix **seconds** (for ``routine.time_``)."""
    return local_ymdhms_to_bb_ms(year, month, day, hour, minute, second) // 1000


def unix_sec_to_local_ymdhms(ts: int) -> dict[str, int]:
    """Inverse of ``local_ymdhms_to_unix_sec``: ``routine.time_`` -> local wall-clock parts."""
    ms = int(ts) * 1000 - _BB_MS_ORIGIN
    days = int(math.floor(ms / 86400000.0))
    rem = ms - days * 86400000
    d = _BB_REF + timedelta(days=days)
    h = rem // 3600000
    rem2 = rem % 3600000
    mi = rem2 // 60000
    se = rem2 % 60000 // 1000
    return {
        "year": d.year,
        "month": d.month,
        "day": d.day,
        "hour": int(h),
        "minute": int(mi),
        "second": int(se),
    }


def format_local_ymd(ts: int) -> str:
    """``routine.time_`` (unix sec) -> ``YYYY-MM-DD`` for agent-facing payloads."""
    p = unix_sec_to_local_ymdhms(ts)
    return f"{p['year']:04d}-{p['month']:02d}-{p['day']:02d}"


def format_local_hms(ts: int) -> str:
    """``routine.time_`` -> ``HH:MM:SS`` (same local model as ``format_local_ymd``)."""
    p = unix_sec_to_local_ymdhms(ts)
    return f"{p['hour']:02d}:{p['minute']:02d}:{p['second']:02d}"
