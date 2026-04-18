"""Resolve SUSTech BB/TIS credentials and semester defaults."""
from __future__ import annotations

import logging
import os

from agent.credentials_store import (
    EnvVaultAccessError,
    delete_credentials,
    get_credential_ciphertext,
    get_credential_value,
    upsert_credential_values,
)

_CAS_STUDENT_ID_KEY = "SUSTECH_STUDENT_ID"
_CAS_PASSWORD_KEY = "SUSTECH_CAS_PASSWORD"
_CREDENTIAL_TYPE = "school_credential"
_CREDENTIAL_SCOPE = "shared_sustech_cas"
_STUDENT_ID_RECORD_KEY = f"{_CREDENTIAL_SCOPE}:student_id"
_PASSWORD_RECORD_KEY = f"{_CREDENTIAL_SCOPE}:password"

log = logging.getLogger(__name__)


async def _write_db_shared_cas(student_id: str, password: str) -> None:
    await upsert_credential_values(
        _CREDENTIAL_TYPE,
        {
            _STUDENT_ID_RECORD_KEY: student_id,
            _PASSWORD_RECORD_KEY: password,
        },
    )


async def _read_db_shared_cas_record() -> tuple[str, str] | None:
    try:
        student_id = await get_credential_value(_CREDENTIAL_TYPE, _STUDENT_ID_RECORD_KEY) or ""
        password_ciphertext = await get_credential_ciphertext(_CREDENTIAL_TYPE, _PASSWORD_RECORD_KEY) or ""
    except EnvVaultAccessError as exc:
        log.warning("Failed to read shared CAS from database: %s", exc)
        return None

    if not student_id or not password_ciphertext:
        return None
    return student_id, password_ciphertext


async def _read_db_shared_cas() -> tuple[str, str]:
    try:
        student_id = await get_credential_value(_CREDENTIAL_TYPE, _STUDENT_ID_RECORD_KEY) or ""
        password = await get_credential_value(_CREDENTIAL_TYPE, _PASSWORD_RECORD_KEY) or ""
    except EnvVaultAccessError as exc:
        log.warning("Failed to decrypt shared CAS from database: %s", exc)
        return "", ""

    if not student_id or not password:
        return "", ""
    return student_id, password


async def _read_shared_cas() -> tuple[str, str]:
    shared_u, shared_p = await _read_db_shared_cas()
    if shared_u and shared_p:
        return shared_u, shared_p
    return (
        os.getenv(_CAS_STUDENT_ID_KEY) or "",
        os.getenv(_CAS_PASSWORD_KEY) or "",
    )


async def resolve_bb_credentials(user_name: str | None, pwd: str | None) -> tuple[str, str]:
    """Tool args first, then shared SUSTECH CAS."""
    shared_u, shared_p = await _read_shared_cas()
    return user_name or shared_u or "", pwd or shared_p or ""


async def resolve_tis_credentials(user_name: str | None, pwd: str | None) -> tuple[str, str]:
    """Tool args first, then shared SUSTECH CAS."""
    shared_u, shared_p = await _read_shared_cas()
    return user_name or shared_u or "", pwd or shared_p or ""


async def set_school_cas_credentials(student_id: str | None, password: str | None) -> None:
    """Persist shared CAS in the database for both TIS and BB."""
    sid = (student_id or "").strip()
    pwd = password if password is not None else ""
    if not sid or not pwd:
        await clear_school_cas_credentials()
        return
    await _write_db_shared_cas(sid, pwd)


async def clear_school_cas_credentials() -> None:
    """Clear shared CAS from the database."""
    try:
        await delete_credentials(
            _CREDENTIAL_TYPE,
            [_STUDENT_ID_RECORD_KEY, _PASSWORD_RECORD_KEY],
        )
    except EnvVaultAccessError as exc:
        log.warning("Failed to clear shared CAS from database: %s", exc)


async def get_school_cas_config() -> dict[str, str] | None:
    record = await _read_db_shared_cas_record()
    if record is None:
        return None
    student_id, password_ciphertext = record
    return {
        "id": student_id,
        "password_encrypted": password_ciphertext,
    }


async def patch_school_cas_config(
    student_id: str | None = None,
    password: str | None = None,
) -> None:
    current_id, current_password = await _read_db_shared_cas()
    next_id = current_id
    next_password = current_password

    if student_id is not None:
        next_id = student_id.strip()
    if password is not None:
        next_password = password

    if not next_id or not next_password:
        raise ValueError("Both id and password are required after patch merge")

    await _write_db_shared_cas(next_id, next_password)


async def get_school_cas_credentials_status() -> dict:
    """Safe snapshot for GET /settings/*/credentials (password never returned)."""
    sid, pwd = await _read_shared_cas()
    configured = bool(sid and pwd)
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
