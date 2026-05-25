from datetime import date
from json import loads

import aiohttp

from agent.services.cas_client import CLIENT_TIMEOUT, HEADERS, SSL_CONTEXT, cas_login

TIS_LOGIN_URL = "https://cas.sustech.edu.cn/cas/login?service=https%3A%2F%2Ftis.sustech.edu.cn%2Fcas"
TIS_SEMESTER_URL = "https://tis.sustech.edu.cn/Xsxk/queryXkdqXnxq"
TIS_SCHEDULE_URL = "https://tis.sustech.edu.cn/xszykb/queryxszykbzong"
TIS_CLASS_DAY_URL = "https://tis.sustech.edu.cn/component/querygrrclist"
TIS_COURSE_URL = "https://tis.sustech.edu.cn/Xsxk/queryKxrw"
TIS_EXAM_URL = "https://tis.sustech.edu.cn/kscxtj/queryXsksByxhList"


async def login_tis(user_name: str, pwd: str) -> dict:
    return await cas_login(TIS_LOGIN_URL, user_name, pwd)


async def _post_json(
    session: aiohttp.ClientSession,
    url: str,
    data: dict | None = None,
    headers: dict | None = None,
) -> dict:
    async with session.post(url, data=data, headers=headers, ssl=SSL_CONTEXT) as resp:
        resp.raise_for_status()
        text = await resp.text()
    return loads(text)


async def get_current_semester_info(session: aiohttp.ClientSession) -> dict:
    try:
        semester_info = await _post_json(
            session,
            TIS_SEMESTER_URL,
            {"mxpylx": 1},
        )
        return {"success": True, "data": semester_info}
    except Exception as exc:
        return {"success": False, "message": "queryXkdqXnxq failed", "error": str(exc)}


async def get_schedule_with_semester(session: aiohttp.ClientSession) -> dict:
    semester_result = await get_current_semester_info(session)
    if not semester_result["success"]:
        return semester_result
    semester_info = semester_result["data"]

    try:
        payload = await _post_json(
            session,
            TIS_SCHEDULE_URL,
            {
                "xn": semester_info.get("p_xn", ""),
                "xq": semester_info.get("p_xq", ""),
            },
        )
        return {"success": True, "data": payload, "semester": semester_info}
    except Exception as exc:
        return {"success": False, "message": "queryxszykbzong failed", "error": str(exc)}


async def get_schedule(session: aiohttp.ClientSession) -> dict:
    result = await get_schedule_with_semester(session)
    if not result["success"]:
        return result
    return {"success": True, "data": result["data"]}


async def get_class_days(session: aiohttp.ClientSession, query_month: date) -> dict:
    try:
        payload = await _post_json(
            session,
            TIS_CLASS_DAY_URL,
            {"rcrq": f"{query_month.year}-{query_month.month}-01"},
        )
        return {"success": True, "data": payload}
    except Exception as exc:
        return {"success": False, "message": "querygrrclist failed", "error": str(exc)}


async def get_exams(
    session: aiohttp.ClientSession,
    page_size: int = 1000,
    semester_info: dict | None = None,
) -> dict:
    if semester_info is None:
        semester_result = await get_current_semester_info(session)
        if not semester_result["success"]:
            return semester_result
        semester_info = semester_result["data"]

    data_base = {
        "ppylx": 1,
        "pkkyx": "",
        "pxn": semester_info.get("p_xn", ""),
        "pxq": semester_info.get("p_xq", ""),
    }
    headers = {
        "Origin": "https://tis.sustech.edu.cn",
        "Referer": "https://tis.sustech.edu.cn/kscxtj/queryXskscxByXh",
        "RoleCode": "01",
    }

    try:
        first_payload = await _post_json(
            session,
            TIS_EXAM_URL,
            {**data_base, "pageNum": 1, "pageSize": page_size},
            headers=headers,
        )

        items = first_payload.get("list") if isinstance(first_payload, dict) else None
        if not isinstance(items, list):
            return {"success": True, "data": first_payload}

        pages = first_payload.get("pages") if isinstance(first_payload, dict) else 1
        try:
            page_count = max(1, int(pages or 1))
        except (TypeError, ValueError):
            page_count = 1

        all_items = list(items)
        for page_num in range(2, page_count + 1):
            page_payload = await _post_json(
                session,
                TIS_EXAM_URL,
                {**data_base, "pageNum": page_num, "pageSize": page_size},
                headers=headers,
            )
            page_items = page_payload.get("list") if isinstance(page_payload, dict) else None
            if isinstance(page_items, list):
                all_items.extend(page_items)

        payload = dict(first_payload)
        payload["list"] = all_items
        payload["size"] = len(all_items)
        return {"success": True, "data": payload}
    except Exception as exc:
        return {"success": False, "message": "queryXsksByxhList failed", "error": str(exc)}


async def query_available_courses(
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

        async with aiohttp.ClientSession(headers=HEADERS, timeout=CLIENT_TIMEOUT) as session:
            for course_type in type_keys:
                raw_class_data = await _post_json(
                    session,
                    TIS_COURSE_URL,
                    {
                        "p_xn": semester_data["p_xn"],
                        "p_xq": semester_data["p_xq"],
                        "p_xnxq": semester_data["p_xnxq"],
                        "p_pylx": 1,
                        "mxpylx": 1,
                        "p_xkfsdm": course_type,
                        "pageNum": 1,
                        "pageSize": 1000,
                    },
                )
                if not raw_class_data.get("kxrwList"):
                    continue

                for item in raw_class_data["kxrwList"]["list"]:
                    name = item["rwmc"].strip()
                    if name_set is not None and name not in name_set:
                        continue
                    course_list.append([item["id"], course_type, name])

    except Exception as exc:
        return {"success": False, "message": "queryKxrw failed", "error": str(exc)}

    return {"success": True, "courses": course_list, "course_types": course_types}
