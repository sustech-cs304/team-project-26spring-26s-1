import aiohttp

from agent.services.cas_client import HEADERS, SSL_CONTEXT, cas_login

BB_LOGIN_URL = "https://cas.sustech.edu.cn/cas/login?service=https://bb.sustech.edu.cn/webapps/bb-sso-BBLEARN/index.jsp"
BB_CALENDAR_URL = "https://bb.sustech.edu.cn/webapps/calendar/calendarData/selectedCalendarEvents"
BB_REFERER = "https://bb.sustech.edu.cn/webapps/calendar/viewMyBb?globalNavigation=false"


async def login_bb(user_name: str, pwd: str) -> dict:
    return await cas_login(BB_LOGIN_URL, user_name, pwd)


async def get_calendar_events(
    session: aiohttp.ClientSession,
    *,
    start_ms: int,
    end_ms: int,
    course_id: str = "",
    mode: str = "personal",
) -> dict:
    try:
        async with session.get(
            BB_CALENDAR_URL,
            params={
                "start": str(int(start_ms)),
                "end": str(int(end_ms)),
                "course_id": course_id,
                "mode": mode,
            },
            headers={**HEADERS, "Referer": BB_REFERER},
            ssl=SSL_CONTEXT,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            return {"success": True, "data": data}
    except Exception as exc:
        return {"success": False, "message": "Calendar request failed", "error": str(exc)}
