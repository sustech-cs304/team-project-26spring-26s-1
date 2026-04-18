"""Global environment variable storage backed by ``agent.db``."""
from __future__ import annotations

import re
from typing import Any

import pydantic
from fastapi import APIRouter, HTTPException, status
from pydantic import field_validator

from agent.credentials_store import (
    EnvVaultAccessError,
    delete_credential,
    decrypt_secret_value,
    encrypt_secret_value,
    get_credential_value,
    list_credential_keys,
    read_credential_values,
    upsert_credential_value,
)

router = APIRouter(tags=["env-vars"])

__all__ = [
    "EnvVaultAccessError",
    "encrypt_secret_value",
    "decrypt_secret_value",
    "list_env_var_keys",
    "read_env_values",
    "get_env_var_entry",
    "get_env_var_value",
    "upsert_env_var_value",
    "delete_env_var_value",
    "validate_env_var_key",
    "router",
]

MAX_ENV_KEY_LEN = 1024
_ENV_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_ENV_VAR_CREDENTIAL_TYPE = "env_var"


def list_env_var_keys() -> list[str]:
    return list_credential_keys(_ENV_VAR_CREDENTIAL_TYPE)


def read_env_values() -> dict[str, str]:
    return read_credential_values(_ENV_VAR_CREDENTIAL_TYPE)


def get_env_var_entry(key: str) -> dict[str, Any] | None:
    try:
        k = validate_env_var_key(key)
    except ValueError:
        return None

    value = get_credential_value(_ENV_VAR_CREDENTIAL_TYPE, k)
    if value is None:
        return None
    return {"value": value}


def get_env_var_value(key: str) -> str | None:
    entry = get_env_var_entry(key)
    if entry is None:
        return None
    value = entry.get("value")
    return value if isinstance(value, str) else None


def upsert_env_var_value(key: str, value: str) -> dict[str, Any]:
    k = validate_env_var_key(key)
    upsert_credential_value(_ENV_VAR_CREDENTIAL_TYPE, k, value)
    return {"key": k}


def delete_env_var_value(key: str) -> bool:
    k = validate_env_var_key(key)
    return delete_credential(_ENV_VAR_CREDENTIAL_TYPE, k)


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


def _raise_from_vault_access_error(exc: EnvVaultAccessError) -> None:
    raise HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"message": str(exc)},
    )


class EnvVarKeyItem(pydantic.BaseModel):
    """Global env list / create response without the secret value."""

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


@router.get(
    "/env-vars",
    response_model=list[EnvVarKeyItem],
    summary="List global env vars",
    description=(
        "Returns a **JSON array** of ``{ \"key\": \"...\" }`` objects."
    ),
)
async def list_global_env_vars() -> list[EnvVarKeyItem]:
    try:
        return [EnvVarKeyItem(key=key) for key in list_env_var_keys()]
    except EnvVaultAccessError as e:
        _raise_from_vault_access_error(e)


@router.post(
    "/env-vars",
    response_model=EnvVarKeyItem,
    status_code=status.HTTP_200_OK,
    summary="Create or update a global env var",
    description=(
        "Create or update a global env var. "
        "**200** returns ``{ key }`` only; plaintext values are never returned."
    ),
)
async def upsert_global_env_var(body: EnvVarUpsertRequest) -> EnvVarKeyItem:
    try:
        item = upsert_env_var_value(body.key, body.value)
    except ValueError as e:
        _raise_from_key_validation(e)
    except EnvVaultAccessError as e:
        _raise_from_vault_access_error(e)
    return EnvVarKeyItem(**item)


@router.delete(
    "/env-vars/{key}",
    response_model=EnvVarDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a global env var",
    description="On success returns **200** with body ``{ message }``.",
)
async def delete_global_env_var(key: str) -> EnvVarDeleteResponse:
    try:
        ok = delete_env_var_value(key)
    except ValueError as e:
        _raise_from_key_validation(e)
    except EnvVaultAccessError as e:
        _raise_from_vault_access_error(e)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Env var key not found")
    return EnvVarDeleteResponse(message="Deleted.")
