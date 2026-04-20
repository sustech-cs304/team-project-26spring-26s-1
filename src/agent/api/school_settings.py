"""HTTP API for shared school CAS credentials in Global Settings.

``PUT`` calls ``school_credentials.set_school_cas_credentials`` and stores a shared CAS
username/password pair in the local database for both BB and TIS.

``/settings/bb/credentials`` and ``/settings/tis/credentials`` behave the same.
"""

import pydantic
from fastapi import APIRouter, HTTPException

from agent.services import school_credentials

router = APIRouter(tags=["settings"])


class TisCredentialsBody(pydantic.BaseModel):
    student_id: str
    password: str


class TisCredentialsPutResponse(pydantic.BaseModel):
    ok: bool = True
    student_id: str
    message: str = "Shared CAS credentials updated in the database."


class TisCredentialsGetResponse(pydantic.BaseModel):
    runtime_configured: bool
    student_id: str | None
    password_set: bool


class TisCredentialsDeleteResponse(pydantic.BaseModel):
    ok: bool = True
    message: str = "Shared CAS credentials cleared."


class CasConfigPatchRequest(pydantic.BaseModel):
    id: str | None = None
    password: str | None = None


class MessageResponse(pydantic.BaseModel):
    message: str


@router.get("/settings/tis/credentials", response_model=TisCredentialsGetResponse)
async def get_tis_credentials_status():
    """Return whether shared CAS credentials are set (password is never returned)."""
    data = await school_credentials.get_school_cas_credentials_status()
    return TisCredentialsGetResponse(**data)


@router.patch("/patch_cas", response_model=MessageResponse)
async def patch_cas(
    body: CasConfigPatchRequest,
):
    try:
        storage = await school_credentials.patch_school_cas_config(
            student_id=body.id,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except school_credentials.EnvVaultAccessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if storage == "runtime_fallback":
        return MessageResponse(
            message=(
                "CAS config updated in runtime fallback because the encrypted "
                "credential store is unavailable."
            )
        )
    return MessageResponse(message="CAS config updated successfully.")


@router.put("/settings/tis/credentials", response_model=TisCredentialsPutResponse)
async def put_tis_credentials(body: TisCredentialsBody):
    """Store shared CAS in the database for BB/TIS tool resolution."""
    await school_credentials.set_school_cas_credentials(body.student_id, body.password)
    return TisCredentialsPutResponse(student_id=body.student_id.strip())


@router.delete("/settings/tis/credentials", response_model=TisCredentialsDeleteResponse)
async def delete_tis_credentials():
    """Clear shared CAS from the database; tools fall back to process env only."""
    await school_credentials.clear_school_cas_credentials()
    return TisCredentialsDeleteResponse()


# --- BB: shares ``set_school_cas_credentials`` with TIS so the UI can save BB-only CAS ---


class BbCredentialsPutResponse(pydantic.BaseModel):
    ok: bool = True
    student_id: str
    message: str = (
        "Shared SUSTech CAS saved in the database for both BB and TIS."
    )


@router.get("/settings/bb/credentials", response_model=TisCredentialsGetResponse)
async def get_bb_credentials_status():
    """Same as ``GET /settings/tis/credentials``: shared CAS status (password never returned)."""
    data = await school_credentials.get_school_cas_credentials_status()
    return TisCredentialsGetResponse(**data)


@router.put("/settings/bb/credentials", response_model=BbCredentialsPutResponse)
async def put_bb_credentials(body: TisCredentialsBody):
    """Save shared SUSTech CAS in Global Settings; BB and TIS tools read the same pair."""
    await school_credentials.set_school_cas_credentials(body.student_id, body.password)
    return BbCredentialsPutResponse(student_id=body.student_id.strip())


@router.delete("/settings/bb/credentials", response_model=TisCredentialsDeleteResponse)
async def delete_bb_credentials():
    """Clear shared CAS credentials (same as ``DELETE .../tis/credentials``)."""
    await school_credentials.clear_school_cas_credentials()
    return TisCredentialsDeleteResponse()
