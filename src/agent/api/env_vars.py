"""Global environment variable vault — stored in cron/env_vars.json.

GET returns an array of objects with **keys only**; POST create/update returns a single item; secret values never appear in responses.
"""
import json
import re
import pydantic
from fastapi import APIRouter, HTTPException, status
from pydantic import field_validator
from pathlib import Path

router = APIRouter(tags=["env-vars"])

CRON_DIR = Path("./cron")
ENV_VARS_FILE = Path("./cron/env_vars.json")

MAX_ENV_KEY_LEN = 1024
_ENV_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _read_vault() -> dict[str, str]:
    if not ENV_VARS_FILE.is_file():
        return {}
    try:
        return json.loads(ENV_VARS_FILE.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_vault(vault: dict[str, str]) -> None:
    CRON_DIR.mkdir(exist_ok=True)
    ENV_VARS_FILE.write_text(json.dumps(vault, ensure_ascii=False, indent=2), "utf-8")


def validate_env_var_key(key: str) -> str:
    """Validate env var name: length ≤1024, alphanumeric and underscore only. Routes map errors to 400."""
    s = key.strip()
    if not s:
        raise ValueError("empty_key")
    if len(s) > MAX_ENV_KEY_LEN:
        raise ValueError("too_long")
    if not _ENV_KEY_RE.match(s):
        raise ValueError("bad_chars")
    return s


def _raise_from_key_validation(exc: ValueError) -> None:
    code = exc.args[0] if exc.args else ""
    if code == "too_long":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"message": "Parameter too long"},
        )
    if code in ("empty_key", "bad_chars"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"message": "Env var name must be alphanumeric and underscore only, length at most 1024"},
        )
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"message": str(exc)})


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class EnvVarKeyItem(pydantic.BaseModel):
    """Global env list / create response: ``key`` only (no ``secret_ref``)."""

    model_config = pydantic.ConfigDict(
        extra="forbid",
        json_schema_extra={"title": "EnvVarKeyItem"},
    )

    key: str = pydantic.Field(..., description="Variable name")


class EnvVarUpsertRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    key: str = pydantic.Field(..., min_length=1)
    value: str

    @field_validator("key")
    @classmethod
    def strip_key(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("key must not be empty or whitespace-only")
        return s


class EnvVarDeleteResponse(pydantic.BaseModel):
    """Successful delete response **200**, matches frontend ``Response``."""

    model_config = pydantic.ConfigDict(
        extra="allow",
        json_schema_extra={"title": "Response"},
    )

    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/env-vars",
    response_model=list[EnvVarKeyItem],
    summary="List global env vars",
    description=(
        "Returns a **JSON array** of ``{ \"key\": \"...\" }`` objects (keys only, no secret_ref)."
    ),
)
async def list_global_env_vars() -> list[EnvVarKeyItem]:
    vault = _read_vault()
    keys = sorted(vault.keys())
    return [EnvVarKeyItem(key=k) for k in keys]


@router.post(
    "/env-vars",
    response_model=EnvVarKeyItem,
    status_code=status.HTTP_200_OK,
    summary="Create or update a global env var",
    description="Create or update a global env var. **200** returns ``{ key }`` only (no plaintext value).",
)
async def upsert_global_env_var(body: EnvVarUpsertRequest) -> EnvVarKeyItem:
    try:
        k = validate_env_var_key(body.key)
    except ValueError as e:
        _raise_from_key_validation(e)
    vault = _read_vault()
    vault[k] = body.value
    _write_vault(vault)
    return EnvVarKeyItem(key=k)


@router.delete(
    "/env-vars/{key}",
    response_model=EnvVarDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a global env var",
    description="On success returns **200** with body ``{ message }``.",
)
async def delete_global_env_var(key: str) -> EnvVarDeleteResponse:
    try:
        k = validate_env_var_key(key)
    except ValueError as e:
        _raise_from_key_validation(e)
    vault = _read_vault()
    if k not in vault:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Env var key not found")
    del vault[k]
    _write_vault(vault)
    return EnvVarDeleteResponse(message="Deleted.")
