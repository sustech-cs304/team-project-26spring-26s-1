"""Shared encrypted credential storage backed by ORM models in ``agent.db``."""
from __future__ import annotations

import base64
import datetime as dt
import getpass
import hashlib
import json
import os
import secrets
from typing import Iterable

import keyring
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from keyring.errors import KeyringError
from sqlalchemy import delete, select

from agent.db.database import ensure_default_schema, get_default_session_factory
from agent.db.models import Credential

_KEYRING_SERVICE_ENV = "AGENT_ENV_VAULT_KEYRING_SERVICE"
_KEYCHAIN_SERVICE_ENV = "AGENT_ENV_VAULT_KEYCHAIN_SERVICE"
_MASTER_KEY_ENV = "AGENT_ENV_VAULT_MASTER_KEY"
_VAULT_FORMAT = "encrypted-v2"
_VAULT_AAD = b"agent-credentials:encrypted-v2"
_AES_GCM_NONCE_BYTES = 12


class EnvVaultAccessError(RuntimeError):
    """Raised when the encrypted credential store cannot be safely accessed."""


def _now_dt() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _keyring_service_name() -> str:
    explicit = os.getenv(_KEYRING_SERVICE_ENV) or os.getenv(_KEYCHAIN_SERVICE_ENV)
    if explicit:
        return explicit
    fingerprint = hashlib.sha256(str(os.path.abspath("./agent.db")).encode("utf-8")).hexdigest()[:16]
    return f"agent-credentials:{fingerprint}"


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
            "Failed to access system keyring for the credential store. "
            f"Set {_MASTER_KEY_ENV} or configure a supported keyring backend."
        ) from exc
    if stored:
        return stored

    master_key = secrets.token_hex(32)
    try:
        keyring.set_password(service, account, master_key)
    except KeyringError as exc:
        raise EnvVaultAccessError(
            "Failed to store the credential master key in the system keyring. "
            f"Set {_MASTER_KEY_ENV} or configure a supported keyring backend."
        ) from exc
    return master_key


async def encrypt_secret_value(plaintext: str) -> str:
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


async def decrypt_secret_value(payload_text: str) -> str:
    try:
        parsed = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise EnvVaultAccessError(f"Encrypted secret is not valid JSON: {exc}") from exc

    if not (
        isinstance(parsed, dict)
        and parsed.get("format") == _VAULT_FORMAT
        and isinstance(parsed.get("nonce"), str)
        and isinstance(parsed.get("ciphertext"), str)
    ):
        raise EnvVaultAccessError("Encrypted secret payload format is unsupported")

    try:
        nonce = base64.b64decode(parsed["nonce"])
        ciphertext = base64.b64decode(parsed["ciphertext"])
    except Exception as exc:
        raise EnvVaultAccessError(f"Encrypted secret has invalid base64 data: {exc}") from exc

    try:
        plaintext = AESGCM(_master_key_bytes(_load_or_create_master_key())).decrypt(
            nonce,
            ciphertext,
            _VAULT_AAD,
        )
    except InvalidTag as exc:
        raise EnvVaultAccessError("Encrypted secret failed authentication; data or key is invalid") from exc
    return plaintext.decode("utf-8")


async def list_credential_keys(credential_type: str) -> list[str]:
    await ensure_default_schema()
    session_factory = get_default_session_factory()
    async with session_factory() as session:
        stmt = (
            select(Credential.credential_key)
            .where(Credential.credential_type == credential_type)
            .order_by(Credential.credential_key.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_credential_ciphertext(credential_type: str, key: str) -> str | None:
    await ensure_default_schema()
    session_factory = get_default_session_factory()
    async with session_factory() as session:
        stmt = select(Credential).where(
            Credential.credential_type == credential_type,
            Credential.credential_key == key,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return row.value_ciphertext


async def get_credential_value(credential_type: str, key: str) -> str | None:
    value_ciphertext = await get_credential_ciphertext(credential_type, key)
    if value_ciphertext is None:
        return None
    return await decrypt_secret_value(value_ciphertext)


async def read_credential_values(credential_type: str) -> dict[str, str]:
    await ensure_default_schema()
    session_factory = get_default_session_factory()
    async with session_factory() as session:
        stmt = (
            select(Credential)
            .where(Credential.credential_type == credential_type)
            .order_by(Credential.credential_key.asc())
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

    values: dict[str, str] = {}
    for row in rows:
        values[row.credential_key] = await decrypt_secret_value(row.value_ciphertext)
    return values


async def upsert_credential_value(credential_type: str, key: str, value: str) -> None:
    await upsert_credential_values(credential_type, {key: value})


async def upsert_credential_values(credential_type: str, values: dict[str, str]) -> None:
    if not values:
        return

    await ensure_default_schema()
    session_factory = get_default_session_factory()
    now = _now_dt()
    async with session_factory() as session:
        for key, value in values.items():
            stmt = select(Credential).where(
                Credential.credential_type == credential_type,
                Credential.credential_key == key,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            ciphertext = await encrypt_secret_value(value)
            if row is None:
                row = Credential(
                    credential_type=credential_type,
                    credential_key=key,
                    value_ciphertext=ciphertext,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.value_ciphertext = ciphertext
                row.updated_at = now
        await session.commit()


async def delete_credential(credential_type: str, key: str) -> bool:
    return await delete_credentials(credential_type, [key]) > 0


async def delete_credentials(credential_type: str, keys: Iterable[str]) -> int:
    key_list = [key for key in keys]
    if not key_list:
        return 0

    await ensure_default_schema()
    session_factory = get_default_session_factory()
    async with session_factory() as session:
        stmt = delete(Credential).where(
            Credential.credential_type == credential_type,
            Credential.credential_key.in_(key_list),
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount or 0
