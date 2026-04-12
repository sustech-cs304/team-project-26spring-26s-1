from __future__ import annotations

import base64
from pathlib import Path

DEFAULT_NOTIFICATION_ICON_RELATIVE_PATH = Path("assets/opencrab.png")

_DEFAULT_NOTIFICATION_ICON_PNG_BASE64 = (
    "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"
    "hkYp8H+DD1NloSY5sgAAAABJRU5ErkJggg=="
)


def ensure_default_notification_icon() -> Path:
    icon_path = DEFAULT_NOTIFICATION_ICON_RELATIVE_PATH.resolve()
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    content = base64.b64decode(_DEFAULT_NOTIFICATION_ICON_PNG_BASE64)
    try:
        current = icon_path.read_bytes()
    except OSError:
        current = None
    if current != content:
        icon_path.write_bytes(content)
    return icon_path
