"""Small crypto helpers (e.g. Fernet for school credentials in ``config.yaml``)."""

from agent.crypto.school_secrets import (
    decrypt_school_secret,
    encrypt_school_secret,
    fernet_key_generate,
)

__all__ = [
    "decrypt_school_secret",
    "encrypt_school_secret",
    "fernet_key_generate",
]
