"""Resolve SUSTech BB/TIS credentials and semester defaults.

Priority for IDs/passwords:
  1. Tool call arguments
  2. In-memory overrides from **Global Settings** (FastAPI):
     ``PUT /api/settings/bb/credentials`` or ``PUT /api/settings/tis/credentials``
     — same SUSTech CAS; saving writes project-root ``.env`` (SUSTECH_/BB_/TIS_ student id and password) and updates the current process environment
  3. ``config.yaml`` ``school.bb`` / ``school.tis`` (``student_id`` and ``password`` or Fernet ``password_enc``; key in ``school.fernet_key``)
  4. Environment variables (TIS_* / BB_* / SUSTECH_* / TIS_DEFAULT_*)

See `.env.example` in the project root for env variable names.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

from dotenv import get_key, set_key, unset_key


_lock = threading.Lock()
# Runtime overrides (mirrored to .env when set via Global Settings API).
_tis_student_id: Optional[str] = None
_tis_password: Optional[str] = None

log = logging.getLogger(__name__)

_DOTENV_PATH = "./.env"


def _school_fernet_key() -> str:
    try:
        from agent.config import get_config

        return (get_config().school.fernet_key or "").strip()
    except Exception:
        return ""


def _school_cfg_bb() -> tuple[str, str]:
    """``student_id`` and decrypted password from ``config.yaml`` ``school.bb``."""
    try:
        from agent.config import get_config

        s = get_config().school.bb
    except Exception:
        return "", ""
    pwd = ""
    fk = _school_fernet_key()
    if s.password and str(s.password).strip():
        pwd = str(s.password).strip()
    elif s.password_enc and str(s.password_enc).strip():
        from agent.crypto.school_secrets import decrypt_school_secret

        d = decrypt_school_secret(s.password_enc, fk)
        if d is None:
            log.warning(
                "school.bb.password_enc could not be decrypted "
                "(set school.fernet_key in config.yaml or fix ciphertext); "
                "or use school.bb.password for local plaintext",
            )
        else:
            pwd = d
    return (s.student_id or ""), pwd


def _school_cfg_tis() -> tuple[str, str]:
    """``student_id`` and decrypted password from ``config.yaml`` ``school.tis``."""
    try:
        from agent.config import get_config

        s = get_config().school.tis
    except Exception:
        return "", ""
    pwd = ""
    fk = _school_fernet_key()
    if s.password and str(s.password).strip():
        pwd = str(s.password).strip()
    elif s.password_enc and str(s.password_enc).strip():
        from agent.crypto.school_secrets import decrypt_school_secret

        d = decrypt_school_secret(s.password_enc, fk)
        if d is None:
            log.warning(
                "school.tis.password_enc could not be decrypted "
                "(set school.fernet_key in config.yaml or fix ciphertext); "
                "or use school.tis.password for local plaintext",
            )
        else:
            pwd = d
    return (s.student_id or ""), pwd


def _sync_cas_to_dotenv_and_environ(student_id: str | None, password: str | None) -> None:
    """Sync CAS from Global Settings to project-root ``.env`` and ``os.environ``."""
    sid = student_id or None
    pwd = password or None
    path = str(_DOTENV_PATH)
    try:
        if sid and pwd:
            set_key(path, "SUSTECH_STUDENT_ID", sid, quote_mode="auto")
            set_key(path, "SUSTECH_CAS_PASSWORD", pwd, quote_mode="auto")
            os.environ["SUSTECH_STUDENT_ID"] = sid
            os.environ["SUSTECH_CAS_PASSWORD"] = pwd
        else:
            if _DOTENV_PATH.is_file():
                if get_key(path, "SUSTECH_STUDENT_ID") is not None:
                    unset_key(path, "SUSTECH_STUDENT_ID")
                if get_key(path, "SUSTECH_CAS_PASSWORD") is not None:
                    unset_key(path, "SUSTECH_CAS_PASSWORD")
            os.environ.pop("SUSTECH_STUDENT_ID", None)
            os.environ.pop("SUSTECH_CAS_PASSWORD", None)
    except OSError as e:
        log.warning("Could not sync school CAS to .env: %s", e)


def resolve_bb_credentials(user_name: str | None, pwd: str | None) -> tuple[str, str]:
    """Tool args first, then Global Settings runtime CAS, then config ``school.bb``, then BB_* / SUSTECH_*."""
    ru, rp = _get_tis_runtime_pair()
    cu, cp = _school_cfg_bb()
    u = user_name or ru or cu or os.getenv("BB_STUDENT_ID") or os.getenv("SUSTECH_STUDENT_ID")
    p = pwd or rp or cp or os.getenv("BB_CAS_PASSWORD") or os.getenv("SUSTECH_CAS_PASSWORD")
    return u, p


def resolve_tis_credentials(user_name: str | None, pwd: str | None) -> tuple[str, str]:
    """Tool args first, then API runtime override, then config ``school.tis``, then TIS_* / SUSTECH_*."""
    ru, rp = _get_tis_runtime_pair()
    cu, cp = _school_cfg_tis()
    u = user_name or ru or cu or os.getenv("TIS_STUDENT_ID") or os.getenv("SUSTECH_STUDENT_ID")
    p = pwd or rp or cp or os.getenv("TIS_CAS_PASSWORD") or os.getenv("SUSTECH_CAS_PASSWORD")
    return u, p


def _get_tis_runtime_pair() -> tuple[str, str]:
    with _lock:
        sid = _tis_student_id or ""
        pwd = _tis_password or ""
    return sid, pwd


def set_tis_runtime_credentials(student_id: str | None, password: str | None) -> None:
    """Persist SUSTech CAS from Global Settings and mirror to ``.env`` and ``os.environ``."""
    global _tis_student_id, _tis_password
    with _lock:
        _tis_student_id = student_id or None
        _tis_password = password or None
        sid, pwd = _tis_student_id, _tis_password
    _sync_cas_to_dotenv_and_environ(sid, pwd)


def clear_tis_runtime_credentials() -> None:
    """Clear in-memory CAS and remove mirrored keys from ``.env`` / the environment."""
    global _tis_student_id, _tis_password
    with _lock:
        _tis_student_id = None
        _tis_password = None
    _sync_cas_to_dotenv_and_environ(None, None)


def get_tis_credentials_status() -> dict:
    """Safe snapshot for GET /settings/tis/credentials (no password returned)."""
    with _lock:
        configured = bool(_tis_student_id and _tis_password)
        sid = _tis_student_id
    return {
        "runtime_configured": configured,
        "student_id": sid,
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
            "Student id or CAS password missing; save in Global Settings first ("
            "PUT /api/settings/bb/credentials or /api/settings/tis/credentials), "
            "or set school.fernet_key and school.bb / school.tis in config.yaml, "
            "or SUSTECH_STUDENT_ID / SUSTECH_CAS_PASSWORD or BB_*/TIS_* in the environment."
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
