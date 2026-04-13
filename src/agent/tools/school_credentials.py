"""Resolve SUSTech BB/TIS credentials and semester defaults."""
from __future__ import annotations

import logging
import os

from agent.api.env_vars import (
    EnvVaultAccessError,
    delete_env_var_value,
    get_env_var_value,
    upsert_env_var_value,
)


_CAS_STUDENT_ID_KEY = "SUSTECH_STUDENT_ID"
_CAS_PASSWORD_KEY = "SUSTECH_CAS_PASSWORD"

log = logging.getLogger(__name__)


def _read_vault_env(key: str) -> str:
    try:
        return get_env_var_value(key) or ""
    except EnvVaultAccessError as exc:
        log.warning("Failed to read env var %s from encrypted vault: %s", key, exc)
        return ""


def _read_any_env(key: str) -> str:
    return _read_vault_env(key) or os.getenv(key) or ""


def _read_shared_cas() -> tuple[str, str]:
    return (
        _read_any_env(_CAS_STUDENT_ID_KEY),
        _read_any_env(_CAS_PASSWORD_KEY),
    )


def resolve_bb_credentials(user_name: str | None, pwd: str | None) -> tuple[str, str]:
    """Tool args first, then shared SUSTECH CAS."""
    shared_u, shared_p = _read_shared_cas()
    u = (
        user_name
        or shared_u
        or ""
    )
    p = (
        pwd
        or shared_p
        or ""
    )
    return u, p


def resolve_tis_credentials(user_name: str | None, pwd: str | None) -> tuple[str, str]:
    """Tool args first, then shared SUSTECH CAS."""
    shared_u, shared_p = _read_shared_cas()
    u = (
        user_name
        or shared_u
        or ""
    )
    p = (
        pwd
        or shared_p
        or ""
    )
    return u, p


def set_school_cas_credentials(student_id: str | None, password: str | None) -> None:
    """Persist shared CAS in the env-var vault for both TIS and BB."""
    sid = (student_id or "").strip()
    pwd = password if password is not None else ""
    if not sid or not pwd:
        clear_school_cas_credentials()
        return
    upsert_env_var_value(_CAS_STUDENT_ID_KEY, sid)
    upsert_env_var_value(_CAS_PASSWORD_KEY, pwd)


def clear_school_cas_credentials() -> None:
    """Clear shared CAS from the env-var vault."""
    for key in (_CAS_STUDENT_ID_KEY, _CAS_PASSWORD_KEY):
        try:
            delete_env_var_value(key)
        except ValueError:
            continue


def get_school_cas_credentials_status() -> dict:
    """Safe snapshot for GET /settings/*/credentials (password never returned)."""
    sid = _read_any_env(_CAS_STUDENT_ID_KEY)
    configured = bool(sid and _read_any_env(_CAS_PASSWORD_KEY))
    return {
        "runtime_configured": configured,
        "student_id": sid or None,
        "password_set": configured,
    }


def resolve_tis_semester(
    p_xn: str | None,
    p_xq: str | None,
    p_xnxq: str | None,
) -> tuple[str, str, str]:
    """Tool args first; missing pieces filled from TIS_DEFAULT_*."""
    xn = p_xn or os.getenv("TIS_DEFAULT_P_XN")
    xq = p_xq or os.getenv("TIS_DEFAULT_P_XQ")
    xnxq = p_xnxq or os.getenv("TIS_DEFAULT_P_XNXQ")
    return xn, xq, xnxq


def missing_cas_message() -> dict:
    return {
        "success": False,
        "message": (
            "Student id or CAS password missing; save shared CAS in Global Settings first "
            "(PUT /api/settings/bb/credentials or /api/settings/tis/credentials), "
            "or set SUSTECH_STUDENT_ID and SUSTECH_CAS_PASSWORD."
        ),
    }


def missing_semester_message() -> dict:
    return {
        "success": False,
        "message": (
            "Semester fields (p_xn, p_xq, p_xnxq) incomplete, "
            "and TIS_DEFAULT_P_XN / TIS_DEFAULT_P_XQ / TIS_DEFAULT_P_XNXQ not set in .env."
        ),
    }
