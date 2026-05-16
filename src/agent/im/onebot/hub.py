import asyncio
from dataclasses import dataclass
import logging
from contextlib import suppress
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import async_sessionmaker

from agent.api.conversation_models import CompletionResponseToolCall
from agent.api.conversation_runner import ConversationRunner
from agent.config import get_config, get_config_path
from agent.im.message_utils import (
    TOOL_FORWARD_THRESHOLD,
    extract_paragraphs,
    render_tool_message,
)
from agent.im.session_controller import IMSessionController
from agent.im.types import IMChatTarget

from .connection import OneBotApiError, OneBotConnection

log = logging.getLogger(__name__)


@dataclass(slots=True)
class _OneBotAssistantBuffer:
    text: str = ""


class OneBotHub(IMSessionController):
    def __init__(self, session_factory: async_sessionmaker, graph, runner: ConversationRunner):
        super().__init__(
            session_factory,
            graph,
            runner,
            platform_key="onebot",
            platform_label="OneBot",
        )
        self._connections: dict[tuple[str, str], OneBotConnection] = {}
        self._connection_lock = asyncio.Lock()
        self._assistant_buffers: dict[tuple[str, str, str, str, str], _OneBotAssistantBuffer] = {}

    @property
    def access_token(self) -> str:
        return get_config_path(get_config(), "onebot.access_token")

    @property
    def superuser_ids(self) -> set[str]:
        return {
            str(user_id).strip()
            for user_id in get_config_path(get_config(), "onebot.superuser_ids")
            if str(user_id).strip()
        }

    @property
    def command_trigger(self) -> str:
        return get_config_path(get_config(), "onebot.command_trigger")

    @property
    def message_trigger(self) -> str:
        return get_config_path(get_config(), "onebot.message_trigger")

    async def serve(self, websocket: WebSocket):
        self_id = websocket.headers.get("x-self-id")
        role = (websocket.headers.get("x-client-role") or "").strip().lower()

        if not self_id or role not in {"api", "event", "universal"}:
            await websocket.close(code=1008)
            return

        if not self._is_authorized(websocket):
            await websocket.close(code=1008)
            return

        await websocket.accept()
        connection = OneBotConnection(websocket, self_id=str(self_id), role=role)
        previous = await self._register(connection)
        if previous is not None:
            with suppress(Exception):
                await previous.websocket.close(code=1012, reason="replaced")

        try:
            while True:
                payload = await websocket.receive_json()
                if not isinstance(payload, dict):
                    continue
                if connection.handle_response(payload):
                    continue
                if "post_type" in payload:
                    self._start_task(self._handle_event(connection, payload))
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            log.warning(
                "OneBot connection %s/%s failed: %s",
                connection.self_id,
                connection.role,
                exc,
            )
        finally:
            await self._unregister(connection)

    async def call_action(self, account_id: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
        connection = self._connections.get((account_id, "universal")) or self._connections.get((account_id, "api"))
        if connection is None:
            raise OneBotApiError(f"No OneBot API connection available for account {account_id}")
        return await connection.call_action(action, params)

    async def _register(self, connection: OneBotConnection) -> OneBotConnection | None:
        key = (connection.self_id, connection.role)
        async with self._connection_lock:
            previous = self._connections.get(key)
            self._connections[key] = connection
            return previous

    async def _unregister(self, connection: OneBotConnection):
        key = (connection.self_id, connection.role)
        async with self._connection_lock:
            if self._connections.get(key) is connection:
                self._connections.pop(key, None)
        connection.fail_pending(ConnectionError("OneBot connection closed"))

    def _is_authorized(self, websocket: WebSocket) -> bool:
        access_token = self.access_token
        if not access_token:
            return True
        authorization = websocket.headers.get("authorization") or ""
        return authorization == f"Bearer {access_token}"

    async def _handle_event(self, connection: OneBotConnection, payload: dict[str, Any]):
        if str(payload.get("post_type", "")).lower() != "message":
            return

        target = self._extract_chat_target(connection, payload)
        if target is None:
            return

        message_text = self._extract_message_text(payload).strip()
        if not message_text:
            return

        if str(payload.get("user_id", "")) == connection.self_id:
            return

        is_superuser = self.is_superuser(payload.get("user_id"))
        await self.route_message(target, message_text, is_superuser)

    def _extract_chat_target(self, connection: OneBotConnection, payload: dict[str, Any]) -> IMChatTarget | None:
        message_type = str(payload.get("message_type", "")).lower()
        if message_type == "private" and payload.get("user_id") is not None:
            return IMChatTarget(
                platform=self.platform_key,
                account_id=connection.self_id,
                chat_type="private",
                chat_id=str(payload["user_id"]),
            )
        if message_type == "group" and payload.get("group_id") is not None:
            return IMChatTarget(
                platform=self.platform_key,
                account_id=connection.self_id,
                chat_type="group",
                chat_id=str(payload["group_id"]),
            )
        return None

    def _extract_message_text(self, payload: dict[str, Any]) -> str:
        raw_message = payload.get("raw_message")
        if isinstance(raw_message, str):
            return raw_message

        message = payload.get("message")
        if isinstance(message, str):
            return message
        if not isinstance(message, list):
            return ""

        chunks: list[str] = []
        for segment in message:
            if not isinstance(segment, dict):
                continue
            if str(segment.get("type", "")).lower() != "text":
                continue
            data = segment.get("data", {})
            if isinstance(data, dict):
                text = data.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "".join(chunks)

    async def send_tool_message(self, target: IMChatTarget, tool_call: CompletionResponseToolCall):
        tool_message = render_tool_message(tool_call)
        if len(tool_message) <= TOOL_FORWARD_THRESHOLD:
            await self.send_text(target, tool_message)
            return

        await self._send_forward_message(target, tool_message)

    async def append_assistant_delta(self, target: IMChatTarget, message_uuid: str, delta: str):
        buffer = self._assistant_buffers.get(self._assistant_buffer_key(target, message_uuid))
        if buffer is None:
            buffer = _OneBotAssistantBuffer()
            self._assistant_buffers[self._assistant_buffer_key(target, message_uuid)] = buffer

        buffer.text += delta
        paragraphs, buffer.text = extract_paragraphs(buffer.text)
        for paragraph in paragraphs:
            await self.send_text(target, paragraph, message_uuid=message_uuid)

    async def finish_assistant_message(self, target: IMChatTarget, message_uuid: str):
        key = self._assistant_buffer_key(target, message_uuid)
        buffer = self._assistant_buffers.pop(key, None)
        if buffer is None:
            return

        paragraphs, _ = extract_paragraphs(buffer.text, flush=True)
        for paragraph in paragraphs:
            await self.send_text(target, paragraph, message_uuid=message_uuid)

    def cancel_assistant_message(self, target: IMChatTarget, message_uuid: str):
        self._assistant_buffers.pop(self._assistant_buffer_key(target, message_uuid), None)

    async def send_text(self, target: IMChatTarget, text: str, message_uuid: str | None = None):
        message = text.strip()
        if not message:
            return

        await self._send_message(target, message, auto_escape=True)

    def _assistant_buffer_key(self, target: IMChatTarget, message_uuid: str) -> tuple[str, str, str, str, str]:
        return (*target.session_key(), message_uuid)

    async def _send_forward_message(self, target: IMChatTarget, text: str):
        message = text.strip()
        if not message:
            return

        await self._send_message(
            target,
            [
                {
                    "type": "node",
                    "data": {
                        "user_id": target.account_id,
                        "nickname": self.platform_label,
                        "content": message,
                    },
                }
            ],
        )

    async def _send_message(self, target: IMChatTarget, message: Any, auto_escape: bool = False):
        params: dict[str, Any] = {
            "message_type": target.chat_type,
            "message": message,
        }
        if isinstance(message, str):
            params["auto_escape"] = auto_escape
        if target.chat_type == "private":
            params["user_id"] = int(target.chat_id)
        else:
            params["group_id"] = int(target.chat_id)

        await self.call_action(target.account_id, "send_msg", params)
