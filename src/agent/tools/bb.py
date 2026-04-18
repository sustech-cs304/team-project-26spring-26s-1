from langchain.tools import tool

from agent.services.bb_client import (
    get_calendar_events as fetch_calendar_events,
    login_bb,
)
from agent.services.calendar_time import local_ymdhms_to_bb_ms
from agent.services.school_credentials import missing_cas_message, resolve_bb_credentials


@tool
async def get_calendar_events(
    user_name: str | None = None,
    pwd: str | None = None,
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
    course_id: str = "",
    mode: str = "personal",
) -> dict:
    """Log into Blackboard (CAS) and fetch calendar events for a wall-clock range.

    Use **calendar date** and optional **time-of-day**; milliseconds are derived server-side with the same
    ``standardize_time`` rules as repo-root ``bb.py`` — do not pass Unix timestamps.

    Credentials are optional: use shared CAS in Global Settings
    (``PUT /api/settings/bb/credentials``),
    or ``SUSTECH_STUDENT_ID`` / ``SUSTECH_CAS_PASSWORD``.
    """
    if not (
        start_year is not None
        and start_month is not None
        and start_day is not None
        and end_year is not None
        and end_month is not None
        and end_day is not None
    ):
        return {
            "success": False,
            "message": "Provide start_year/start_month/start_day and end_year/end_month/end_day together.",
        }
    try:
        start_ms = local_ymdhms_to_bb_ms(
            int(start_year),
            int(start_month),
            int(start_day),
            int(start_hour),
            int(start_minute),
            int(start_second),
        )
        end_ms = local_ymdhms_to_bb_ms(
            int(end_year),
            int(end_month),
            int(end_day),
            int(end_hour),
            int(end_minute),
            int(end_second),
        )
    except (TypeError, ValueError) as e:
        return {"success": False, "message": f"Invalid date/time: {e}"}
    if start_ms > end_ms:
        return {"success": False, "message": "Start time must be <= end time"}
    u, p = await resolve_bb_credentials(user_name, pwd)
    if not u or not p:
        return missing_cas_message()
    login_result = await login_bb(u, p)
    if not login_result["success"]:
        return login_result
    try:
        return await fetch_calendar_events(
            login_result["session"],
            start_ms=start_ms,
            end_ms=end_ms,
            course_id=course_id,
            mode=mode,
        )
    finally:
        await login_result["session"].close()
