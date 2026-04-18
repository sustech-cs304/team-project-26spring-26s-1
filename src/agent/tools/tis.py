from langchain.tools import tool

from agent.services.school_credentials import (
    missing_cas_message,
    missing_semester_message,
    resolve_tis_credentials,
    resolve_tis_semester,
)
from agent.services.tis_client import (
    get_schedule as fetch_tis_schedule,
    login_tis,
    query_available_courses as fetch_available_courses,
)


@tool
async def get_schedule(user_name: str | None = None, pwd: str | None = None) -> dict:
    """TIS full timetable for the current term. Keys include xq (weekday) and jc (period).

    Credentials optional: shared CAS in Global Settings
    (``PUT /api/settings/tis/credentials``),
    or ``SUSTECH_STUDENT_ID`` / ``SUSTECH_CAS_PASSWORD``.
    """
    u, p = await resolve_tis_credentials(user_name, pwd)
    if not u or not p:
        return missing_cas_message()
    login_result = await login_tis(u, p)
    if not login_result["success"]:
        return login_result
    try:
        return await fetch_tis_schedule(login_result["session"])
    finally:
        await login_result["session"].close()


@tool
async def query_available_courses(
    p_xn: str | None = None,
    p_xq: str | None = None,
    p_xnxq: str | None = None,
    target_names: list[str] | None = None,
    type_codes: list[str] | None = None,
) -> dict:
    """Selectable courses for a term. Semester may come from TIS_DEFAULT_* in `.env`.

    Optional filters: target_names, type_codes (bxxk, xxxk, kzyxk, zynknjxk, jhnxk).
    """
    xn, xq, xnxq = resolve_tis_semester(p_xn, p_xq, p_xnxq)
    if not xn or not xq or not xnxq:
        return missing_semester_message()
    semester_data = {"p_xn": xn, "p_xq": xq, "p_xnxq": xnxq}
    return await fetch_available_courses(
        semester_data,
        target_names=target_names,
        type_codes=type_codes,
    )
