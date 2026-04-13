"""HTTP API for shared school CAS credentials in Global Settings.

``PUT`` calls ``school_credentials.set_school_cas_credentials`` and stores a shared CAS
username/password pair in the global env-var vault for both BB and TIS.

``/settings/bb/credentials`` and ``/settings/tis/credentials`` behave the same.
"""
import os

import pydantic
from fastapi import APIRouter, Header, HTTPException

from agent.services import school_credentials

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
    message: str = "Shared CAS credentials updated in the env-var vault."


class TisCredentialsGetResponse(pydantic.BaseModel):
    runtime_configured: bool
    student_id: str | None
    password_set: bool


class TisCredentialsDeleteResponse(pydantic.BaseModel):
    ok: bool = True
    message: str = "Shared CAS credentials cleared."


@router.get("/tis/credentials", response_model=TisCredentialsGetResponse)
async def get_tis_credentials_status(
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Return whether shared CAS credentials are set (password is never returned)."""
    _require_secret(x_school_settings_secret)
    data = school_credentials.get_school_cas_credentials_status()
    return TisCredentialsGetResponse(**data)


@router.put("/tis/credentials", response_model=TisCredentialsPutResponse)
async def put_tis_credentials(
    body: TisCredentialsBody,
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Store shared CAS in the env-var vault for BB/TIS tool resolution."""
    _require_secret(x_school_settings_secret)
    school_credentials.set_school_cas_credentials(body.student_id, body.password)
    return TisCredentialsPutResponse(student_id=body.student_id.strip())


@router.delete("/tis/credentials", response_model=TisCredentialsDeleteResponse)
async def delete_tis_credentials(
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Clear shared CAS from the env-var vault; tools fall back to process env only."""
    _require_secret(x_school_settings_secret)
    school_credentials.clear_school_cas_credentials()
    return TisCredentialsDeleteResponse()


# --- BB: shares ``set_school_cas_credentials`` with TIS so the UI can save BB-only CAS ---


class BbCredentialsPutResponse(pydantic.BaseModel):
    ok: bool = True
    student_id: str
    message: str = (
        "Shared SUSTech CAS saved in the env-var vault for both BB and TIS."
    )


@router.get("/bb/credentials", response_model=TisCredentialsGetResponse)
async def get_bb_credentials_status(
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Same as ``GET /settings/tis/credentials``: shared CAS status (password never returned)."""
    _require_secret(x_school_settings_secret)
    data = school_credentials.get_school_cas_credentials_status()
    return TisCredentialsGetResponse(**data)


@router.put("/bb/credentials", response_model=BbCredentialsPutResponse)
async def put_bb_credentials(
    body: TisCredentialsBody,
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Save shared SUSTech CAS in Global Settings; BB and TIS tools read the same pair."""
    _require_secret(x_school_settings_secret)
    school_credentials.set_school_cas_credentials(body.student_id, body.password)
    return BbCredentialsPutResponse(student_id=body.student_id.strip())


@router.delete("/bb/credentials", response_model=TisCredentialsDeleteResponse)
async def delete_bb_credentials(
    x_school_settings_secret: str | None = Header(None, alias="X-School-Settings-Secret"),
):
    """Clear shared CAS credentials (same as ``DELETE .../tis/credentials``)."""
    _require_secret(x_school_settings_secret)
    school_credentials.clear_school_cas_credentials()
    return TisCredentialsDeleteResponse()
