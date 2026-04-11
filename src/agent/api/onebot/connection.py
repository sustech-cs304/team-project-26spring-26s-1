import asyncio
from typing import Any
from uuid import uuid4

from fastapi import WebSocket


class OneBotApiError(Exception):
    pass


class OneBotConnection:
    def __init__(self, websocket: WebSocket, self_id: str, role: str):
        self.websocket = websocket
        self.self_id = self_id
        self.role = role
        self._send_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}

    async def call_action(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        echo = str(uuid4())
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[echo] = future

        try:
            async with self._send_lock:
                await self.websocket.send_json(
                    {
                        "action": action,
                        "params": params,
                        "echo": echo,
                    }
                )

            response = await asyncio.wait_for(future, timeout=30)
            status = str(response.get("status", "")).lower()
            if status not in {"ok", "async"}:
                raise OneBotApiError(
                    f"OneBot action {action} failed: status={response.get('status')} retcode={response.get('retcode')}"
                )
            return response
        finally:
            self._pending.pop(echo, None)

    def handle_response(self, payload: dict[str, Any]) -> bool:
        echo = payload.get("echo")
        if not isinstance(echo, str):
            return False

        future = self._pending.get(echo)
        if future is None or future.done():
            return False

        future.set_result(payload)
        return True

    def fail_pending(self, exc: Exception):
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)
        self._pending.clear()

