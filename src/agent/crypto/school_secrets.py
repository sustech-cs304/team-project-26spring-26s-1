"""Fernet encrypt/decrypt for BB/TIS ``password_enc`` in ``config.yaml``.

Put the same url-safe base64 key in ``school.fernet_key`` as used when encrypting passwords.

Generate a new key::

    uv run python -c "from agent.crypto.school_secrets import fernet_key_generate; print(fernet_key_generate())"

Encrypt a password (paste key into ``school.fernet_key`` and ciphertext into ``password_enc``)::

    uv run python -c "from agent.crypto.school_secrets import encrypt_school_secret; k='YOUR_KEY'; print(encrypt_school_secret('plain', k))"
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


def fernet_key_generate() -> str:
    """Return a new url-safe base64 Fernet key for ``school.fernet_key`` in ``config.yaml``."""
    return Fernet.generate_key().decode()


def encrypt_school_secret(plaintext: str, key: str) -> str:
    """Encrypt ``plaintext`` with the given Fernet ``key``."""
    k = (key or "").strip()
    if not k:
        raise ValueError("Missing Fernet key: pass key= or set school.fernet_key in config.yaml")
    return Fernet(k.encode()).encrypt(plaintext.encode()).decode()


def decrypt_school_secret(ciphertext: str, key: str | None) -> str | None:
    """Decrypt Fernet ``ciphertext`` using ``key``. Returns ``None`` if key missing or token invalid."""
    if not ciphertext or not ciphertext.strip():
        return None
    k = (key or "").strip()
    if not k:
        return None
    try:
        raw = Fernet(k.encode()).decrypt(ciphertext.strip().encode())
        return raw.decode()
    except (InvalidToken, ValueError, TypeError):
        return None
