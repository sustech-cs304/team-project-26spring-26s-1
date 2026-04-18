"""Resolve SUSTech BB/TIS credentials and semester defaults."""
from __future__ import annotations

import datetime as dt
import logging
import os
import sqlite3
from pathlib import Path

from agent.api.env_vars import (
    EnvVaultAccessError,
    decrypt_secret_value,
    encrypt_secret_value,
)

_CAS_STUDENT_ID_KEY = "SUSTECH_STUDENT_ID"
_CAS_PASSWORD_KEY = "SUSTECH_CAS_PASSWORD"
_DB_PATH = Path("./agent.db")
_CREDENTIAL_SCOPE = "shared_sustech_cas"
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS school_credentials (
    scope TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    password_ciphertext TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
)
"""

log = logging.getLogger(__name__)

def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


def _write_db_shared_cas(student_id: str, password: str) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    ciphertext = encrypt_secret_value(password)
    _write_db_shared_cas_ciphertext(student_id, ciphertext, now=now)


def _write_db_shared_cas_ciphertext(
    student_id: str,
    password_ciphertext: str,
    *,
    now: str | None = None,
) -> None:
    ts = now or dt.datetime.now(dt.timezone.utc).isoformat()
    # Validate ciphertext before storing so runtime reads do not fail later.
    decrypt_secret_value(password_ciphertext)
    with _connect_db() as conn:
        conn.execute(
            """
            INSERT INTO school_credentials (scope, student_id, password_ciphertext, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(scope) DO UPDATE SET
                student_id = excluded.student_id,
                password_ciphertext = excluded.password_ciphertext,
                updated_at = excluded.updated_at
            """,
            (_CREDENTIAL_SCOPE, student_id, password_ciphertext, ts, ts),
        )
        conn.commit()


def _read_db_shared_cas_record() -> tuple[str, str] | None:
    try:
        with _connect_db() as conn:
            row = conn.execute(
                """
                SELECT student_id, password_ciphertext
                FROM school_credentials
                WHERE scope = ?
                """,
                (_CREDENTIAL_SCOPE,),
            ).fetchone()
    except sqlite3.Error as exc:
        log.warning("Failed to read shared CAS from database: %s", exc)
        return None

    if row is None:
        return None

    student_id = (row["student_id"] or "").strip()
    password_ciphertext = row["password_ciphertext"] or ""
    if not student_id or not password_ciphertext:
        return None
    return student_id, password_ciphertext


def _read_db_shared_cas() -> tuple[str, str]:
    record = _read_db_shared_cas_record()
    if record is None:
        return "", ""
    student_id, password_ciphertext = record

    try:
        password = decrypt_secret_value(password_ciphertext)
    except EnvVaultAccessError as exc:
        log.warning("Failed to decrypt shared CAS password from database: %s", exc)
        return "", ""
    return student_id, password

def _read_shared_cas() -> tuple[str, str]:
    shared_u, shared_p = _read_db_shared_cas()
    if shared_u and shared_p:
        return shared_u, shared_p

    return (
        os.getenv(_CAS_STUDENT_ID_KEY) or "",
        os.getenv(_CAS_PASSWORD_KEY) or "",
    )


def resolve_bb_credentials(user_name: str | None, pwd: str | None) -> tuple[str, str]:
    """Tool args first, then shared SUSTECH CAS."""
    shared_u, shared_p = _read_shared_cas()
    return user_name or shared_u or "", pwd or shared_p or ""


def resolve_tis_credentials(user_name: str | None, pwd: str | None) -> tuple[str, str]:
    """Tool args first, then shared SUSTECH CAS."""
    shared_u, shared_p = _read_shared_cas()
    return user_name or shared_u or "", pwd or shared_p or ""


def set_school_cas_credentials(student_id: str | None, password: str | None) -> None:
    """Persist shared CAS in the database for both TIS and BB."""
    sid = (student_id or "").strip()
    pwd = password if password is not None else ""
    if not sid or not pwd:
        clear_school_cas_credentials()
        return
    _write_db_shared_cas(sid, pwd)


def clear_school_cas_credentials() -> None:
    """Clear shared CAS from the database."""
    try:
        with _connect_db() as conn:
            conn.execute(
                "DELETE FROM school_credentials WHERE scope = ?",
                (_CREDENTIAL_SCOPE,),
            )
            conn.commit()
    except sqlite3.Error as exc:
        log.warning("Failed to clear shared CAS from database: %s", exc)


def get_school_cas_config() -> dict[str, str] | None:
    record = _read_db_shared_cas_record()
    if record is None:
        return None
    student_id, password_ciphertext = record
    return {
        "id": student_id,
        "password_encrypted": password_ciphertext,
    }


def patch_school_cas_config(
    student_id: str | None = None,
    password: str | None = None,
) -> None:
    current = get_school_cas_config() or {}
    next_id = current.get("id", "")
    next_password_ciphertext = current.get("password_encrypted", "")

    if student_id is not None:
        next_id = student_id.strip()
    if password is not None:
        next_password_ciphertext = encrypt_secret_value(password)

    if not next_id or not next_password_ciphertext:
        raise ValueError("Both id and password are required after patch merge")

    _write_db_shared_cas_ciphertext(next_id, next_password_ciphertext)


def get_school_cas_credentials_status() -> dict:
    """Safe snapshot for GET /settings/*/credentials (password never returned)."""
    sid, pwd = _read_shared_cas()
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
