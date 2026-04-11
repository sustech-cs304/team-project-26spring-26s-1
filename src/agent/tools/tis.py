import warnings
from json import loads
from re import findall, search

import requests
from langchain.tools import tool

from agent.tools.school_env import (
    missing_cas_message,
    missing_semester_message,
    resolve_tis_credentials,
    resolve_tis_semester,
)

warnings.filterwarnings("ignore")

head = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15",
    "x-requested-with": "XMLHttpRequest",
}


def cas_login(user_name: str, pwd: str) -> dict:
    login_url = "https://cas.sustech.edu.cn/cas/login?service=https%3A%2F%2Ftis.sustech.edu.cn%2Fcas"
    try:
        req = requests.get(login_url, headers=head, verify=False)
        assert req.status_code == 200
    except Exception:
        return {"success": False, "message": "Cannot reach CAS; check network."}

    m = search(r'name="execution" value="([^"]+)"', req.text)
    if not m:
        return {"success": False, "message": "Failed to parse execution from CAS login page."}
    execution = m.group(1)
    data = {
        "username": user_name,
        "password": pwd,
        "execution": execution,
        "_eventId": "submit",
    }
    req = requests.post(login_url, data=data, allow_redirects=False, headers=head, verify=False)
    if "Location" not in req.headers:
        return {"success": False, "message": "Invalid username or password."}

    req = requests.get(req.headers["Location"], allow_redirects=False, headers=head, verify=False)
    route_ = findall(r"route=(.+?);", req.headers["Set-Cookie"])[0]
    jsessionid = findall(r"JSESSIONID=(.+?);", req.headers["Set-Cookie"])[0]
    return {"success": True, "route": route_, "jsessionid": jsessionid}


def _query_available_courses_impl(
    semester_data: dict,
    target_names: list | None = None,
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
            req = requests.post(
                "https://tis.sustech.edu.cn/Xsxk/queryKxrw",
                data=data,
                headers=head,
                verify=False,
            )
            raw_class_data = loads(req.text)
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


def query_xszykbzong(semester_data: dict) -> dict:
    try:
        data = {
            "xn": semester_data.get("p_xn", ""),
            "xq": semester_data.get("p_xq", ""),
        }
        req = requests.post(
            "https://tis.sustech.edu.cn/xszykb/queryxszykbzong",
            data=data,
            headers=head,
            verify=False,
        )
        req.raise_for_status()
        return {"success": True, "data": loads(req.text)}
    except Exception as e:
        return {"success": False, "message": "queryxszykbzong failed", "error": str(e)}


@tool
def get_schedule(user_name: str | None = None, pwd: str | None = None) -> dict:
    """TIS full timetable for the current term. Keys include xq (weekday) and jc (period).

    Credentials optional: Global Settings (``PUT /api/settings/tis/credentials`` or shared CAS with BB) or ``TIS_*`` / ``SUSTECH_*``.
    """
    u, p = resolve_tis_credentials(user_name, pwd)
    if not u or not p:
        return missing_cas_message()
    login_result = cas_login(u, p)
    if not login_result["success"]:
        return login_result
    head["cookie"] = f'route={login_result["route"]}; JSESSIONID={login_result["jsessionid"]};'
    semester_resp = requests.post(
        "https://tis.sustech.edu.cn/Xsxk/queryXkdqXnxq",
        data={"mxpylx": 1},
        headers=head,
        verify=False,
    )
    semester_info = loads(semester_resp.text)
    return query_xszykbzong(semester_info)


@tool
def query_available_courses(
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
    return _query_available_courses_impl(
        semester_data, target_names=target_names, type_codes=type_codes
    )
