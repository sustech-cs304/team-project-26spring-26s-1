"""HTTP API for school CAS credentials in Global Settings.

``PUT`` calls ``school_env.set_tis_runtime_credentials`` and syncs project-root ``.env``
``SUSTECH_*`` / ``BB_*`` / ``TIS_*`` student id and password, plus the current process environment.

``/settings/bb/credentials`` and ``/settings/tis/credentials`` behave the same.
"""
import os

import pydantic
from fastapi import APIRouter, Header, HTTPException

from agent.tools import school_env

router = APIRouter(prefix="/settings", tags=["settings"])


def _require_secret(x_secret: str | None) -> None:
    expected = os.getenv("SCHOOL_SETTINGS_SECRET")
    if not expected:
        return
    if not x_secret or x_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-School-Settings-Secret")


class TisCredentialsBody(pydantic.BaseModel):
    student_id: str
    password: str


class TisCredentialsPutResponse(pydantic.BaseModel):
    ok: bool = True
    student_id: str
    message: str = "TIS runtime credentials updated (in-memory until server restart)."


class TisCredentialsGetResponse(pydantic.BaseModel):
    runtime_configured: bool
    student_id: str | None
    password_set: bool


class TisCredentialsDeleteResponse(pydantic.BaseModel):
    ok: bool = True
    message: str = "TIS runtime credentials cleared."


@router.get("/tis/credentials", response_model=TisCredentialsGetResponse)
async def get_tis_credentials_status(
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Return whether runtime TIS credentials are set (password is never returned)."""
    _require_secret(x_school_settings_secret)
    data = school_env.get_tis_credentials_status()
    return TisCredentialsGetResponse(**data)


@router.put("/tis/credentials", response_model=TisCredentialsPutResponse)
async def put_tis_credentials(
    body: TisCredentialsBody,
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Store TIS student ID and CAS password in process memory for tool resolution."""
    _require_secret(x_school_settings_secret)
    school_env.set_tis_runtime_credentials(body.student_id, body.password)
    return TisCredentialsPutResponse(student_id=body.student_id.strip())


@router.delete("/tis/credentials", response_model=TisCredentialsDeleteResponse)
async def delete_tis_credentials(
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Clear runtime TIS overrides; tools fall back to .env only."""
    _require_secret(x_school_settings_secret)
    school_env.clear_tis_runtime_credentials()
    return TisCredentialsDeleteResponse()


# --- BB: shares ``set_tis_runtime_credentials`` with TIS so the UI can save BB-only CAS ---


class BbCredentialsPutResponse(pydantic.BaseModel):
    ok: bool = True
    student_id: str
    message: str = (
        "BB global account saved in process memory (shared SUSTech CAS with TIS; re-save after restart)."
    )


@router.get("/bb/credentials", response_model=TisCredentialsGetResponse)
async def get_bb_credentials_status(
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Same as ``GET /settings/tis/credentials``: whether runtime CAS is configured (password never returned)."""
    _require_secret(x_school_settings_secret)
    data = school_env.get_tis_credentials_status()
    return TisCredentialsGetResponse(**data)


@router.put("/bb/credentials", response_model=BbCredentialsPutResponse)
async def put_bb_credentials(
    body: TisCredentialsBody,
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Save SUSTech CAS for BB in Global Settings; tools such as ``get_calendar_events`` read from here."""
    _require_secret(x_school_settings_secret)
    school_env.set_tis_runtime_credentials(body.student_id, body.password)
    return BbCredentialsPutResponse(student_id=body.student_id.strip())


@router.delete("/bb/credentials", response_model=TisCredentialsDeleteResponse)
async def delete_bb_credentials(
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Clear runtime credentials (same as ``DELETE .../tis/credentials``)."""
    _require_secret(x_school_settings_secret)
    school_env.clear_tis_runtime_credentials()
    return TisCredentialsDeleteResponse()
