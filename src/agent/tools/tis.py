import ssl
import warnings
from json import loads
from re import search

import aiohttp
from langchain.tools import tool

from agent.tools.school_credentials import (
    missing_cas_message,
    missing_semester_message,
    resolve_tis_credentials,
    resolve_tis_semester,
)

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
    login_url = "https://cas.sustech.edu.cn/cas/login?service=https%3A%2F%2Ftis.sustech.edu.cn%2Fcas"
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

    return {"success": True, "session": session}


async def _post_json(
    session: aiohttp.ClientSession,
    url: str,
    data: dict,
) -> dict:
    async with session.post(url, data=data, ssl=_ssl_ctx) as resp:
        resp.raise_for_status()
        text = await resp.text()
    return loads(text)


async def _query_available_courses_impl(
    semester_data: dict,
    target_names: list[str] | None = None,
    type_codes: list[str] | None = None,
) -> dict:
    course_list = []
    course_types = {
        "bxxk": "General education (required)",
        "xxxk": "General education (elective)",
        "kzyxk": "In-curriculum courses",
        "zynknjxk": "Outside-curriculum courses",
        "jhnxk": "Retake courses",
    }

    try:
        if type_codes is None:
            type_keys = list(course_types.keys())
        else:
            type_keys = [code for code in type_codes if code in course_types]
            if not type_keys:
                return {"success": False, "message": "No valid course-type codes."}

        name_set = None
        if target_names is not None:
            name_set = {name.strip() for name in target_names}

        async with aiohttp.ClientSession(headers=HEADERS, timeout=_client_timeout) as session:
            for course_type in type_keys:
                data = {
                    "p_xn": semester_data["p_xn"],
                    "p_xq": semester_data["p_xq"],
                    "p_xnxq": semester_data["p_xnxq"],
                    "p_pylx": 1,
                    "mxpylx": 1,
                    "p_xkfsdm": course_type,
                    "pageNum": 1,
                    "pageSize": 1000,
                }
                raw_class_data = await _post_json(
                    session,
                    "https://tis.sustech.edu.cn/Xsxk/queryKxrw",
                    data,
                )
                if not raw_class_data.get("kxrwList"):
                    continue

                for item in raw_class_data["kxrwList"]["list"]:
                    name = item["rwmc"].strip()
                    if name_set is not None and name not in name_set:
                        continue
                    course_list.append([item["id"], course_type, name])

    except Exception as e:
        return {"success": False, "message": "queryKxrw failed", "error": str(e)}

    return {"success": True, "courses": course_list, "course_types": course_types}


async def query_xszykbzong(session: aiohttp.ClientSession, semester_data: dict) -> dict:
    try:
        data = {
            "xn": semester_data.get("p_xn", ""),
            "xq": semester_data.get("p_xq", ""),
        }
        payload = await _post_json(
            session,
            "https://tis.sustech.edu.cn/xszykb/queryxszykbzong",
            data,
        )
        return {"success": True, "data": payload}
    except Exception as e:
        return {"success": False, "message": "queryxszykbzong failed", "error": str(e)}


@tool
async def get_schedule(user_name: str | None = None, pwd: str | None = None) -> dict:
    """TIS full timetable for the current term. Keys include xq (weekday) and jc (period).

    Credentials optional: shared CAS in Global Settings
    (``PUT /api/settings/tis/credentials``),
    or ``SUSTECH_STUDENT_ID`` / ``SUSTECH_CAS_PASSWORD``.
    """
    u, p = resolve_tis_credentials(user_name, pwd)
    if not u or not p:
        return missing_cas_message()
    login_result = await cas_login(u, p)
    if not login_result["success"]:
        return login_result
    session: aiohttp.ClientSession = login_result["session"]
    try:
        semester_info = await _post_json(
            session,
            "https://tis.sustech.edu.cn/Xsxk/queryXkdqXnxq",
            {"mxpylx": 1},
        )
        return await query_xszykbzong(session, semester_info)
    except Exception as e:
        return {"success": False, "message": "queryXkdqXnxq failed", "error": str(e)}
    finally:
        await session.close()


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
    return await _query_available_courses_impl(
        semester_data,
        target_names=target_names,
        type_codes=type_codes,
    )
