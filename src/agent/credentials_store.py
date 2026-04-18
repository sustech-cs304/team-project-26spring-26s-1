"""Shared encrypted credential storage backed by ``agent.db``."""
from __future__ import annotations

import base64
import datetime as dt
import getpass
import hashlib
import json
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Iterable

import keyring
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from keyring.errors import KeyringError

DB_PATH = Path("./agent.db")

_KEYRING_SERVICE_ENV = "AGENT_ENV_VAULT_KEYRING_SERVICE"
_KEYCHAIN_SERVICE_ENV = "AGENT_ENV_VAULT_KEYCHAIN_SERVICE"
_MASTER_KEY_ENV = "AGENT_ENV_VAULT_MASTER_KEY"
_VAULT_FORMAT = "encrypted-v2"
_VAULT_AAD = b"agent-credentials:encrypted-v2"
_AES_GCM_NONCE_BYTES = 12
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS credentials (
    type TEXT NOT NULL,
    key TEXT NOT NULL,
    value_ciphertext TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (type, key)
)
"""


class EnvVaultAccessError(RuntimeError):
    """Raised when the encrypted credential store cannot be safely accessed."""


def _keyring_service_name() -> str:
    explicit = os.getenv(_KEYRING_SERVICE_ENV) or os.getenv(_KEYCHAIN_SERVICE_ENV)
    if explicit:
        return explicit
    fingerprint = hashlib.sha256(str(DB_PATH.resolve()).encode("utf-8")).hexdigest()[:16]
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


def encrypt_secret_value(plaintext: str) -> str:
    """Encrypt one secret value into a JSON payload string."""
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


def _decrypt_payload_v2(payload: dict[str, object]) -> str:
    nonce_b64 = payload.get("nonce")
    ciphertext_b64 = payload.get("ciphertext")
    if not isinstance(nonce_b64, str) or not isinstance(ciphertext_b64, str):
        raise EnvVaultAccessError("Encrypted secret is missing AES-GCM fields")
    try:
        nonce = base64.b64decode(nonce_b64)
        ciphertext = base64.b64decode(ciphertext_b64)
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
    raise EnvVaultAccessError("Encrypted secret payload format is unsupported")


def _connect_db() -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    except sqlite3.Error as exc:
        raise EnvVaultAccessError(f"Failed to open credential store {DB_PATH}: {exc}") from exc
    return conn


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def list_credential_keys(credential_type: str) -> list[str]:
    try:
        with _connect_db() as conn:
            rows = conn.execute(
                """
                SELECT key
                FROM credentials
                WHERE type = ?
                ORDER BY key
                """,
                (credential_type,),
            ).fetchall()
    except sqlite3.Error as exc:
        raise EnvVaultAccessError(f"Failed to list credentials from {DB_PATH}: {exc}") from exc
    return [row["key"] for row in rows]


def get_credential_ciphertext(credential_type: str, key: str) -> str | None:
    try:
        with _connect_db() as conn:
            row = conn.execute(
                """
                SELECT value_ciphertext
                FROM credentials
                WHERE type = ? AND key = ?
                """,
                (credential_type, key),
            ).fetchone()
    except sqlite3.Error as exc:
        raise EnvVaultAccessError(f"Failed to read credential {credential_type}/{key}: {exc}") from exc
    if row is None:
        return None
    value_ciphertext = row["value_ciphertext"]
    return value_ciphertext if isinstance(value_ciphertext, str) else None


def get_credential_value(credential_type: str, key: str) -> str | None:
    value_ciphertext = get_credential_ciphertext(credential_type, key)
    if value_ciphertext is None:
        return None
    return decrypt_secret_value(value_ciphertext)


def read_credential_values(credential_type: str) -> dict[str, str]:
    try:
        with _connect_db() as conn:
            rows = conn.execute(
                """
                SELECT key, value_ciphertext
                FROM credentials
                WHERE type = ?
                ORDER BY key
                """,
                (credential_type,),
            ).fetchall()
    except sqlite3.Error as exc:
        raise EnvVaultAccessError(f"Failed to read credentials from {DB_PATH}: {exc}") from exc

    values: dict[str, str] = {}
    for row in rows:
        key = row["key"]
        value_ciphertext = row["value_ciphertext"]
        if not isinstance(key, str) or not isinstance(value_ciphertext, str):
            continue
        values[key] = decrypt_secret_value(value_ciphertext)
    return values


def upsert_credential_value(credential_type: str, key: str, value: str) -> None:
    upsert_credential_values(credential_type, {key: value})


def upsert_credential_values(credential_type: str, values: dict[str, str]) -> None:
    if not values:
        return

    ts = _now_iso()
    rows = [
        (credential_type, key, encrypt_secret_value(value), ts, ts)
        for key, value in values.items()
    ]

    try:
        with _connect_db() as conn:
            conn.executemany(
                """
                INSERT INTO credentials (type, key, value_ciphertext, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(type, key) DO UPDATE SET
                    value_ciphertext = excluded.value_ciphertext,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
            conn.commit()
    except sqlite3.Error as exc:
        raise EnvVaultAccessError(f"Failed to write credentials to {DB_PATH}: {exc}") from exc


def delete_credential(credential_type: str, key: str) -> bool:
    return delete_credentials(credential_type, [key]) > 0


def delete_credentials(credential_type: str, keys: Iterable[str]) -> int:
    key_list = [key for key in keys]
    if not key_list:
        return 0

    placeholders = ", ".join("?" for _ in key_list)
    params = [credential_type, *key_list]
    try:
        with _connect_db() as conn:
            cur = conn.execute(
                f"""
                DELETE FROM credentials
                WHERE type = ? AND key IN ({placeholders})
                """,
                params,
            )
            conn.commit()
            return cur.rowcount
    except sqlite3.Error as exc:
        raise EnvVaultAccessError(f"Failed to delete credentials from {DB_PATH}: {exc}") from exc
