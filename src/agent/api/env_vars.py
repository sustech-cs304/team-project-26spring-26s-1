"""Global environment variable vault — stored encrypted in cron/env_vars.json.

Plaintext values are encrypted locally before they are written to disk. The
master key comes from ``AGENT_ENV_VAULT_MASTER_KEY`` or the system keyring.
API responses still expose only variable names.
"""
import base64
import getpass
import hashlib
import json
import logging
import os
import re
import secrets
import subprocess
import pydantic
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, HTTPException, status
import keyring
from pydantic import field_validator
from pathlib import Path
from typing import Any
from keyring.errors import KeyringError

router = APIRouter(tags=["env-vars"])

CRON_DIR = Path("./cron")
ENV_VARS_FILE = Path("./cron/env_vars.json")

MAX_ENV_KEY_LEN = 1024
_ENV_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_KEYRING_SERVICE_ENV = "AGENT_ENV_VAULT_KEYRING_SERVICE"
_KEYCHAIN_SERVICE_ENV = "AGENT_ENV_VAULT_KEYCHAIN_SERVICE"
_MASTER_KEY_ENV = "AGENT_ENV_VAULT_MASTER_KEY"
_VAULT_FORMAT = "encrypted-v2"
_VAULT_FORMAT_LEGACY = "encrypted-v1"
_VAULT_AAD = b"agent-env-vault:encrypted-v2"
_AES_GCM_NONCE_BYTES = 12
_OPENSSL_CIPHER = "aes-256-cbc"
_OPENSSL_ITERATIONS = "200000"
_SUBPROCESS_TIMEOUT_S = 5

log = logging.getLogger(__name__)


class EnvVaultAccessError(RuntimeError):
    """Raised when the encrypted env vault cannot be safely accessed."""


def _keyring_service_name() -> str:
    explicit = os.getenv(_KEYRING_SERVICE_ENV) or os.getenv(_KEYCHAIN_SERVICE_ENV)
    if explicit:
        return explicit
    fingerprint = hashlib.sha256(
        str(ENV_VARS_FILE.resolve()).encode("utf-8")
    ).hexdigest()[:16]
    return f"agent-env-vault:{fingerprint}"


def _run_command(
    args: list[str],
    *,
    input_bytes: bytes | None = None,
    passphrase: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    extra_kwargs: dict[str, Any] = {
        "capture_output": True,
        "check": True,
        "timeout": _SUBPROCESS_TIMEOUT_S,
    }
    if input_bytes is not None:
        extra_kwargs["input"] = input_bytes
    read_fd = -1
    if passphrase is not None:
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, passphrase.encode("utf-8"))
        finally:
            os.close(write_fd)
        args = [*args, "-pass", f"fd:{read_fd}"]
        extra_kwargs["pass_fds"] = (read_fd,)
    try:
        return subprocess.run(args, **extra_kwargs)
    finally:
        if read_fd >= 0:
            os.close(read_fd)


def _master_key_bytes(master_key: str) -> bytes:
    try:
        raw = bytes.fromhex(master_key)
        if len(raw) == 32:
            return raw
    except ValueError:
        pass
    try:
        raw = base64.urlsafe_b64decode(master_key.encode("utf-8"))
        if len(raw) == 32:
            return raw
    except Exception:
        pass
    return hashlib.sha256(master_key.encode("utf-8")).digest()


def _load_or_create_master_key() -> str:
    env_key = os.getenv(_MASTER_KEY_ENV)
    if env_key:
        return env_key

    service = _keyring_service_name()
    account = getpass.getuser()
    try:
        stored = keyring.get_password(service, account)
    except KeyringError as exc:
        raise EnvVaultAccessError(
            "Failed to access system keyring for env vault. "
            f"Set {_MASTER_KEY_ENV} or configure a supported keyring backend."
        ) from exc
    if stored:
        return stored

    master_key = secrets.token_hex(32)
    try:
        keyring.set_password(service, account, master_key)
    except KeyringError as exc:
        raise EnvVaultAccessError(
            "Failed to store env-vault master key in system keyring. "
            f"Set {_MASTER_KEY_ENV} or configure a supported keyring backend."
        ) from exc
    return master_key


def _encrypt_payload(plaintext: str) -> str:
    master_key = _master_key_bytes(_load_or_create_master_key())
    nonce = secrets.token_bytes(_AES_GCM_NONCE_BYTES)
    ciphertext = AESGCM(master_key).encrypt(nonce, plaintext.encode("utf-8"), _VAULT_AAD)
    return json.dumps(
        {
            "format": _VAULT_FORMAT,
            "cipher": "aes-256-gcm",
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        },
        ensure_ascii=False,
    )


def _decrypt_payload(ciphertext: str) -> str:
    master_key = _load_or_create_master_key()
    proc = _run_command(
        [
            "openssl",
            "enc",
            f"-{_OPENSSL_CIPHER}",
            "-d",
            "-pbkdf2",
            "-iter",
            _OPENSSL_ITERATIONS,
            "-a",
            "-A",
        ],
        input_bytes=ciphertext.encode("utf-8"),
        passphrase=master_key,
    )
    return proc.stdout.decode("utf-8")


def _decrypt_payload_v2(payload: dict[str, Any]) -> str:
    nonce_b64 = payload.get("nonce")
    ciphertext_b64 = payload.get("ciphertext")
    if not isinstance(nonce_b64, str) or not isinstance(ciphertext_b64, str):
        raise EnvVaultAccessError("Encrypted env vault is missing AES-GCM fields")
    try:
        nonce = base64.b64decode(nonce_b64)
        ciphertext = base64.b64decode(ciphertext_b64)
    except Exception as exc:
        raise EnvVaultAccessError(f"Encrypted env vault has invalid base64 data: {exc}") from exc
    try:
        plaintext = AESGCM(_master_key_bytes(_load_or_create_master_key())).decrypt(
            nonce,
            ciphertext,
            _VAULT_AAD,
        )
    except InvalidTag as exc:
        raise EnvVaultAccessError("Encrypted env vault failed authentication; data or key is invalid") from exc
    return plaintext.decode("utf-8")


def encrypt_secret_value(plaintext: str) -> str:
    """Encrypt one secret value into a JSON payload string."""
    return _encrypt_payload(plaintext)


def decrypt_secret_value(payload_text: str) -> str:
    """Decrypt a JSON payload string produced by ``encrypt_secret_value``."""
    try:
        parsed = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise EnvVaultAccessError(f"Encrypted secret is not valid JSON: {exc}") from exc
    if (
        isinstance(parsed, dict)
        and parsed.get("format") == _VAULT_FORMAT
        and isinstance(parsed.get("nonce"), str)
        and isinstance(parsed.get("ciphertext"), str)
    ):
        return _decrypt_payload_v2(parsed)
    if (
        isinstance(parsed, dict)
        and parsed.get("format") == _VAULT_FORMAT_LEGACY
        and isinstance(parsed.get("ciphertext"), str)
    ):
        return _decrypt_payload(parsed["ciphertext"])
    raise EnvVaultAccessError("Encrypted secret payload format is unsupported")


def _normalize_entry(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        return {"value": raw}
    if not isinstance(raw, dict):
        return None
    value = raw.get("value")
    if not isinstance(value, str):
        return None
    return {"value": value}


def _normalize_vault(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        entry = _normalize_entry(value)
        if entry is not None:
            out[key] = entry
    return out


def _read_vault() -> dict[str, dict[str, Any]]:
    if not ENV_VARS_FILE.is_file():
        return {}
    try:
        raw_text = ENV_VARS_FILE.read_text("utf-8")
        parsed = json.loads(raw_text)
        if (
            isinstance(parsed, dict)
            and parsed.get("format") == _VAULT_FORMAT
            and isinstance(parsed.get("nonce"), str)
            and isinstance(parsed.get("ciphertext"), str)
        ):
            decrypted = _decrypt_payload_v2(parsed)
            return _normalize_vault(json.loads(decrypted))
        if (
            isinstance(parsed, dict)
            and parsed.get("format") == _VAULT_FORMAT_LEGACY
            and isinstance(parsed.get("ciphertext"), str)
        ):
            decrypted = _decrypt_payload(parsed["ciphertext"])
            normalized = _normalize_vault(json.loads(decrypted))
            _write_vault(normalized)
            return normalized
        if isinstance(parsed, dict) and "format" in parsed:
            raise EnvVaultAccessError(
                f"Unsupported env vault format: {parsed.get('format')!r}"
            )
        if raw_text.strip() and not isinstance(parsed, dict):
            raise EnvVaultAccessError("Env vault file must contain a JSON object")
        normalized = _normalize_vault(parsed)
        if raw_text.strip():
            try:
                _write_vault(normalized)
            except (OSError, EnvVaultAccessError, subprocess.CalledProcessError) as exc:
                log.warning("Failed to migrate plaintext env vault %s: %s", ENV_VARS_FILE, exc)
        return normalized
    except (
        json.JSONDecodeError,
        OSError,
        EnvVaultAccessError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as exc:
        raise EnvVaultAccessError(f"Failed to read env vault {ENV_VARS_FILE}: {exc}") from exc


def _write_vault(vault: dict[str, dict[str, Any]]) -> None:
    CRON_DIR.mkdir(exist_ok=True)
    flat_vault = {
        key: entry["value"]
        for key, entry in vault.items()
        if isinstance(entry.get("value"), str)
    }
    plaintext = json.dumps(flat_vault, ensure_ascii=False, indent=2)
    encrypted = json.loads(_encrypt_payload(plaintext))
    ENV_VARS_FILE.write_text(json.dumps(encrypted, ensure_ascii=False, indent=2), "utf-8")


def list_env_var_keys() -> list[str]:
    return sorted(_read_vault().keys())


def read_env_values() -> dict[str, str]:
    vault = _read_vault()
    out: dict[str, str] = {}
    for key, entry in vault.items():
        value = entry.get("value")
        if isinstance(value, str):
            out[key] = value
    return out


def get_env_var_entry(key: str) -> dict[str, Any] | None:
    try:
        k = validate_env_var_key(key)
    except ValueError:
        return None
    return _read_vault().get(k)


def get_env_var_value(key: str) -> str | None:
    entry = get_env_var_entry(key)
    if entry is None:
        return None
    value = entry.get("value")
    return value if isinstance(value, str) else None


def upsert_env_var_value(key: str, value: str) -> dict[str, Any]:
    k = validate_env_var_key(key)
    vault = _read_vault()
    vault[k] = {"value": value}
    _write_vault(vault)
    return {"key": k}


def delete_env_var_value(key: str) -> bool:
    k = validate_env_var_key(key)
    vault = _read_vault()
    if k not in vault:
        return False
    del vault[k]
    _write_vault(vault)
    return True


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


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

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
