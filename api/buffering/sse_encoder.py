"""SSE encoding utility."""

from __future__ import annotations

import json


def encode_sse(event: str, data: dict) -> bytes:
    payload = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    return payload.encode("utf-8")
