import asyncio
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import async_sessionmaker

from agent.api.conversation_models import CompletionResponseDelta, CompletionResponseToolCall
from agent.api.conversation_runner import ConversationRunner
from agent.api.conversation_service import (
    delete_conversation,
    get_im_permission,
    get_im_session_conversation_id,
    get_or_create_im_session_conversation,
    set_im_permission,
)
from agent.config import OneBotConfig


router = APIRouter()

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")


class OneBotApiError(Exception):
    pass


@dataclass(slots=True)
class OneBotChatTarget:
    account_id: str
    chat_type: str
    chat_id: str


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


class OneBotHub:
    def __init__(self, session_factory: async_sessionmaker, graph, runner: ConversationRunner, config: OneBotConfig):
        self.session_factory = session_factory
        self.graph = graph
        self.runner = runner
        self.access_token = config.access_token
        self.superuser_id = str(config.superuser_id).strip()
        command_name = config.command_name.strip()
        command_name = command_name.lstrip("#").strip()
        command_name = command_name.split(maxsplit=1)[0] if command_name else ""
        self.command_name = command_name or "agent"
        self._connections: dict[tuple[str, str], OneBotConnection] = {}
        self._connection_lock = asyncio.Lock()
        self._session_locks: dict[tuple[str, str, str], asyncio.Lock] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()

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
            print(f"OneBot connection {connection.self_id}/{connection.role} failed: {exc}")
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
        if not self.access_token:
            return True
        authorization = websocket.headers.get("authorization") or ""
        return authorization == f"Bearer {self.access_token}"

    def _start_task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self._background_tasks.add(task)

        def _cleanup(done_task: asyncio.Task[Any]):
            self._background_tasks.discard(done_task)
            with suppress(asyncio.CancelledError):
                exception = done_task.exception()
                if exception is not None:
                    print(f"OneBot background task failed: {exception}")

        task.add_done_callback(_cleanup)

    def _get_session_lock(self, target: OneBotChatTarget) -> asyncio.Lock:
        key = (target.account_id, target.chat_type, target.chat_id)
        lock = self._session_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._session_locks[key] = lock
        return lock

    def _command_prefix(self) -> str:
        return f"#{self.command_name}"

    def _command_usage(self, command: str) -> str:
        return f"{self._command_prefix()} {command}".strip()

    def _is_superuser(self, payload: dict[str, Any]) -> bool:
        sender_id = payload.get("user_id")
        return bool(self.superuser_id) and sender_id is not None and str(sender_id) == self.superuser_id

    def _parse_agent_command(self, message_text: str) -> tuple[str, list[str]] | None:
        parts = message_text.split()
        if not parts or parts[0].lower() != self.command_name.lower():
            return None
        if len(parts) == 1:
            return "help", []
        return parts[1].lower(), parts[2:]

    async def _handle_event(self, connection: OneBotConnection, payload: dict[str, Any]):
        if str(payload.get("post_type", "")).lower() != "message":
            return

        target = self._extract_chat_target(connection, payload)
        if target is None:
            return

        message_text = self._extract_message_text(payload).strip()
        if not message_text:
            return
        if not message_text.startswith("#"):
            return

        message_text = message_text[1:].lstrip()
        if not message_text:
            return

        if str(payload.get("user_id", "")) == connection.self_id:
            return

        is_superuser = self._is_superuser(payload)

        async with self._get_session_lock(target):
            permission = await get_im_permission(
                self.session_factory,
                account_id=target.account_id,
                chat_type=target.chat_type,
                chat_id=target.chat_id,
            )

            command = self._parse_agent_command(message_text)
            if command is not None:
                await self._handle_command(target, command[0], command[1], is_superuser, permission)
                return

            if permission is not True:
                return

            conversation_id = await get_or_create_im_session_conversation(
                self.session_factory,
                account_id=target.account_id,
                chat_type=target.chat_type,
                chat_id=target.chat_id,
                title=f"OneBot {target.chat_type} {target.chat_id}",
            )
            if self.runner.is_running(conversation_id):
                await self._send_text(
                    target,
                    f"This session is busy. Send {self._command_usage('cancel')} to stop the current response or {self._command_usage('drop')} to reset the session.",
                )
                return

            self._start_task(self._run_conversation(target, conversation_id, message_text))

    def _extract_chat_target(self, connection: OneBotConnection, payload: dict[str, Any]) -> OneBotChatTarget | None:
        message_type = str(payload.get("message_type", "")).lower()
        if message_type == "private" and payload.get("user_id") is not None:
            return OneBotChatTarget(
                account_id=connection.self_id,
                chat_type="private",
                chat_id=str(payload["user_id"]),
            )
        if message_type == "group" and payload.get("group_id") is not None:
            return OneBotChatTarget(
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

    async def _handle_command(
        self,
        target: OneBotChatTarget,
        name: str,
        args: list[str],
        is_superuser: bool,
        permission: bool | None,
    ):
        if name in {"allow", "deny"}:
            if not is_superuser:
                if permission is True:
                    await self._send_text(target, "Only the superuser can change permissions.")
                return
            await self._handle_permission_command(target, name == "allow", args)
            return

        if permission is not True and not is_superuser:
            return

        if name == "cancel":
            await self._cancel_session(target)
            return
        if name in {"drop", "reset"}:
            await self._drop_session(target)
            return
        if name == "help":
            await self._send_text(target, self._help_text(is_superuser))
            return

        await self._send_text(target, f"Unknown command.\n{self._help_text(is_superuser)}")

    async def _handle_permission_command(self, target: OneBotChatTarget, is_allowed: bool, args: list[str]):
        permission_target = self._resolve_permission_target(target, args)
        if permission_target is None:
            action = "allow" if is_allowed else "deny"
            await self._send_text(
                target,
                (
                    f"Usage:\n"
                    f"{self._command_usage(f'{action} user <id>')}\n"
                    f"{self._command_usage(f'{action} group <id>')}\n"
                    f"{self._command_usage(action)} in a group"
                ),
            )
            return

        await set_im_permission(
            self.session_factory,
            account_id=permission_target.account_id,
            chat_type=permission_target.chat_type,
            chat_id=permission_target.chat_id,
            is_allowed=is_allowed,
        )
        status = "allowed" if is_allowed else "denied"
        await self._send_text(
            target,
            f"Permission {status} for {permission_target.chat_type} {permission_target.chat_id}.",
        )

    def _resolve_permission_target(self, target: OneBotChatTarget, args: list[str]) -> OneBotChatTarget | None:
        if not args:
            if target.chat_type == "group":
                return target
            return None

        if len(args) != 2:
            return None

        target_type = args[0].lower()
        target_id = args[1].strip()
        if not target_id:
            return None

        if target_type == "user":
            return OneBotChatTarget(
                account_id=target.account_id,
                chat_type="private",
                chat_id=target_id,
            )
        if target_type == "group":
            return OneBotChatTarget(
                account_id=target.account_id,
                chat_type="group",
                chat_id=target_id,
            )
        return None

    def _help_text(self, is_superuser: bool) -> str:
        lines = [
            "Commands:",
            f"{self._command_usage('cancel')} stops the current response.",
            f"{self._command_usage('drop')} resets this IM session.",
        ]
        if is_superuser:
            lines.extend(
                [
                    f"{self._command_usage('allow user <id>')} grants permission to a private chat.",
                    f"{self._command_usage('allow group <id>')} grants permission to a group chat.",
                    f"{self._command_usage('deny user <id>')} revokes permission from a private chat.",
                    f"{self._command_usage('deny group <id>')} revokes permission from a group chat.",
                    f"{self._command_usage('allow')} or {self._command_usage('deny')} in a group targets the current group.",
                ]
            )
        return "\n".join(lines)

    async def _cancel_session(self, target: OneBotChatTarget):
        conversation_id = await get_im_session_conversation_id(
            self.session_factory,
            account_id=target.account_id,
            chat_type=target.chat_type,
            chat_id=target.chat_id,
        )
        if conversation_id is None or not self.runner.is_running(conversation_id):
            await self._send_text(target, "No running completion in this session.")
            return

        await self.runner.cancel(conversation_id)
        await self._send_text(target, "Current completion cancelled.")

    async def _drop_session(self, target: OneBotChatTarget):
        conversation_id = await get_im_session_conversation_id(
            self.session_factory,
            account_id=target.account_id,
            chat_type=target.chat_type,
            chat_id=target.chat_id,
        )
        if conversation_id is None:
            await self._send_text(target, "No session to drop.")
            return

        if self.runner.is_running(conversation_id):
            await self.runner.cancel(conversation_id)

        deleted = await delete_conversation(self.session_factory, self.graph, conversation_id)
        if deleted:
            await self._send_text(target, "Current session dropped. Your next message will start a new session.")
            return

        await self._send_text(target, "Current session was already gone.")

    async def _run_conversation(self, target: OneBotChatTarget, conversation_id: str, message_text: str):
        text_buffer = ""

        try:
            job = await self.runner.run(conversation_id, message_text)
            if job is None:
                return

            async for event in self.runner.stream(conversation_id, need_history=False, job=job):
                if isinstance(event, CompletionResponseDelta):
                    if event.is_thinking:
                        continue
                    text_buffer += event.delta
                    paragraphs, text_buffer = _extract_paragraphs(text_buffer)
                    for paragraph in paragraphs:
                        await self._send_text(target, paragraph)
                    continue

                if isinstance(event, CompletionResponseToolCall):
                    paragraphs, text_buffer = _extract_paragraphs(text_buffer, flush=True)
                    for paragraph in paragraphs:
                        await self._send_text(target, paragraph)

                    tool_paragraph = self._format_tool_paragraph(event)
                    if tool_paragraph:
                        await self._send_text(target, tool_paragraph)

            paragraphs, _ = _extract_paragraphs(text_buffer, flush=True)
            for paragraph in paragraphs:
                await self._send_text(target, paragraph)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"OneBot conversation failed for {conversation_id}: {exc}")
            await self._send_text(target, f"Request failed: {exc}")

    def _format_tool_paragraph(self, tool_call: CompletionResponseToolCall) -> str:
        lines = [f"Tool: {tool_call.tool_name}"]

        if tool_call.tool_arguments:
            arguments = "; ".join(
                f"{argument.argument_name}={argument.argument}"
                for argument in tool_call.tool_arguments
            )
            lines.append(f"Arguments: {arguments}")

        if tool_call.status == "pending":
            lines.append("Status: pending")
            if tool_call.pending_reason.strip():
                lines.append(tool_call.pending_reason.strip())
            return "\n".join(lines)

        if tool_call.status == "rejected":
            lines.append("Status: rejected")
            if tool_call.pending_reason.strip():
                lines.append(tool_call.pending_reason.strip())
            return "\n".join(lines)

        if tool_call.tool_response.strip():
            lines.append("Status: completed")
            lines.append(tool_call.tool_response.strip())
            return "\n".join(lines)

        lines.append("Status: running")
        return "\n".join(lines)

    async def _send_text(self, target: OneBotChatTarget, text: str):
        message = text.strip()
        if not message:
            return

        params: dict[str, Any] = {
            "message_type": target.chat_type,
            "message": message,
            "auto_escape": True,
        }
        if target.chat_type == "private":
            params["user_id"] = int(target.chat_id)
        else:
            params["group_id"] = int(target.chat_id)

        await self.call_action(target.account_id, "send_msg", params)


def _extract_paragraphs(text: str, flush: bool = False) -> tuple[list[str], str]:
    normalized = text.replace("\r\n", "\n")
    parts = _PARAGRAPH_SPLIT_RE.split(normalized)
    if len(parts) == 1:
        if flush:
            stripped = normalized.strip()
            return ([stripped] if stripped else []), ""
        return [], normalized

    if flush:
        paragraphs = [part.strip() for part in parts if part.strip()]
        return paragraphs, ""

    paragraphs = [part.strip() for part in parts[:-1] if part.strip()]
    remainder = parts[-1]
    return paragraphs, remainder


@router.websocket("/onebot/ws")
async def onebot_reverse_websocket(websocket: WebSocket):
    hub: OneBotHub = websocket.app.state.OneBotHub
    await hub.serve(websocket)
