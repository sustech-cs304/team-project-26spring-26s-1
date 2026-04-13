import ssl
import warnings
from re import search

import aiohttp
from langchain.tools import tool

from agent.tools.calendar_time import local_ymdhms_to_bb_ms
from agent.tools.school_credentials import missing_cas_message, resolve_bb_credentials

warnings.filterwarnings("ignore")

_REQUEST_TIMEOUT_S = 15

HEADERS = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15",
    "x-requested-with": "XMLHttpRequest",
}

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE
_client_timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT_S)


async def cas_login(user_name: str, pwd: str) -> dict:
    login_url = "https://cas.sustech.edu.cn/cas/login?service=https://bb.sustech.edu.cn/webapps/bb-sso-BBLEARN/index.jsp"
    jar = aiohttp.CookieJar(unsafe=True)
    session = aiohttp.ClientSession(headers=HEADERS, cookie_jar=jar, timeout=_client_timeout)
    try:
        async with session.get(login_url, ssl=_ssl_ctx) as resp:
            if resp.status != 200:
                await session.close()
                return {"success": False, "message": "Cannot reach CAS; check network."}
            text = await resp.text()

        m = search(r'name="execution" value="([^"]+)"', text)
        if not m:
            await session.close()
            return {"success": False, "message": "Failed to parse execution from CAS login page."}

        async with session.post(
            login_url,
            data={
                "username": user_name,
                "password": pwd,
                "execution": m.group(1),
                "_eventId": "submit",
            },
            ssl=_ssl_ctx,
            allow_redirects=False,
        ) as resp:
            location = resp.headers.get("Location")
            if not location:
                await session.close()
                return {"success": False, "message": "Invalid username or password."}

        async with session.get(location, ssl=_ssl_ctx, allow_redirects=True):
            pass

    except Exception as e:
        await session.close()
        return {"success": False, "message": "CAS login failed", "error": str(e)}

    jsessionid = ""
    for cookie in jar:
        if cookie.key == "JSESSIONID":
            jsessionid = cookie.value or ""
            break
    return {"success": True, "session": session, "jsessionid": jsessionid}


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
    u, p = resolve_bb_credentials(user_name, pwd)
    if not u or not p:
        return missing_cas_message()
    login_result = await cas_login(u, p)
    if not login_result["success"]:
        return login_result
    session: aiohttp.ClientSession = login_result["session"]
    url = "https://bb.sustech.edu.cn/webapps/calendar/calendarData/selectedCalendarEvents"
    params = {
        "start": str(int(start_ms)),
        "end": str(int(end_ms)),
        "course_id": course_id,
        "mode": mode,
    }
    try:
        async with session.get(
            url,
            params=params,
            headers={"Referer": "https://bb.sustech.edu.cn/webapps/calendar/viewMyBb?globalNavigation=false"},
            ssl=_ssl_ctx,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "message": "Calendar request failed", "error": str(e)}
    finally:
        await session.close()
