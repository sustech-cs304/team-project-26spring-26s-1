from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import suppress
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from agent.api.conversation_models import (
    CompletionResponseDelta,
    CompletionResponseToolCall,
    CompletionUserMessage,
)
from agent.api.conversation_runner import ConversationRunner
from agent.api.conversation_service import delete_conversation

from .message_utils import render_tool_message
from .session_service import (
    get_im_permission,
    get_im_session_conversation_id,
    get_or_create_im_session_conversation,
    set_im_permission,
)
from .types import IMChatTarget

log = logging.getLogger(__name__)


def normalize_trigger(value: str) -> str:
    return value.strip()


def strip_trigger(message_text: str, trigger: str) -> str | None:
    message = message_text.strip()
    normalized_trigger = normalize_trigger(trigger)
    if not normalized_trigger or not message.startswith(normalized_trigger):
        return None

    remainder = message[len(normalized_trigger):]
    return remainder.lstrip()


class IMSessionController(ABC):
    def __init__(
        self,
        session_factory: async_sessionmaker,
        graph: Any,
        runner: ConversationRunner,
        *,
        platform_key: str,
        platform_label: str,
    ):
        self.session_factory = session_factory
        self.graph = graph
        self.runner = runner
        self.platform_key = platform_key
        self.platform_label = platform_label
        self._session_locks: dict[tuple[str, str, str, str], asyncio.Lock] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()

    @property
    @abstractmethod
    def superuser_ids(self) -> set[str]:
        raise NotImplementedError

    @property
    @abstractmethod
    def command_trigger(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def message_trigger(self) -> str:
        raise NotImplementedError

    def is_superuser(self, sender_id: str | int | None) -> bool:
        if sender_id is None:
            return False
        return str(sender_id).strip() in self.superuser_ids

    def parse_command(self, message_text: str) -> tuple[str, list[str]] | None:
        remainder = strip_trigger(message_text, self.command_trigger)
        if remainder is None:
            return None
        if not remainder:
            return "help", []
        parts = remainder.split()
        return parts[0].lower(), parts[1:]

    def command_usage(self, command: str) -> str:
        trigger = normalize_trigger(self.command_trigger)
        return f"{trigger} {command}".strip()

    def extract_message_text(self, message_text: str) -> str | None:
        remainder = strip_trigger(message_text, self.message_trigger)
        if remainder is None:
            return None
        message = remainder.strip()
        return message or None

    async def route_message(
        self,
        target: IMChatTarget,
        message_text: str,
        is_superuser: bool,
        source_message_ref: Any | None = None,
    ):
        command = self.parse_command(message_text)
        if command is not None:
            await self.process_command(target, command[0], command[1], is_superuser)
            return

        message = self.extract_message_text(message_text)
        if message is not None:
            await self.process_user_message(target, message, is_superuser, source_message_ref)

    def session_title(self, target: IMChatTarget) -> str:
        return f"{self.platform_label} {target.chat_type} {target.chat_id}"

    def _get_session_lock(self, target: IMChatTarget) -> asyncio.Lock:
        key = target.session_key()
        lock = self._session_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._session_locks[key] = lock
        return lock

    def _start_task(self, coroutine) -> asyncio.Task[Any]:
        task = asyncio.create_task(coroutine)
        self._background_tasks.add(task)

        def _cleanup(done_task: asyncio.Task[Any]):
            self._background_tasks.discard(done_task)
            with suppress(asyncio.CancelledError):
                exception = done_task.exception()
                if exception is not None:
                    log.error(
                        "%s background task failed: %s",
                        self.platform_label,
                        exception,
                        exc_info=(type(exception), exception, exception.__traceback__),
                    )

        task.add_done_callback(_cleanup)
        return task

    async def process_command(
        self,
        target: IMChatTarget,
        name: str,
        args: list[str],
        is_superuser: bool,
    ):
        async with self._get_session_lock(target):
            permission = await get_im_permission(
                self.session_factory,
                account_id=target.binding_account_id,
                chat_type=target.chat_type,
                chat_id=target.chat_id,
            )
            await self._handle_command(target, name, args, is_superuser, permission)

    async def process_user_message(
        self,
        target: IMChatTarget,
        message_text: str,
        is_superuser: bool,
        source_message_ref: Any | None = None,
    ):
        message = message_text.strip()
        if not message:
            return

        async with self._get_session_lock(target):
            permission = await get_im_permission(
                self.session_factory,
                account_id=target.binding_account_id,
                chat_type=target.chat_type,
                chat_id=target.chat_id,
            )
            if permission is not True and not is_superuser:
                return

            conversation_id = await get_or_create_im_session_conversation(
                self.session_factory,
                account_id=target.binding_account_id,
                chat_type=target.chat_type,
                chat_id=target.chat_id,
                title=self.session_title(target),
            )
            if self.runner.is_running(conversation_id):
                await self.send_text(
                    target,
                    (
                        "This session is busy. "
                        f"Send {self.command_usage('cancel')} to stop the current response "
                        f"or {self.command_usage('drop')} to reset the session."
                    ),
                )
                return

            self._start_task(self._run_conversation(target, conversation_id, message, source_message_ref))

    async def _handle_command(
        self,
        target: IMChatTarget,
        name: str,
        args: list[str],
        is_superuser: bool,
        permission: bool | None,
    ):
        if name in {"allow", "deny"}:
            if not is_superuser:
                if permission is True:
                    await self.send_text(target, "Only the superuser can change permissions.")
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
            await self.send_text(target, self._help_text(is_superuser))
            return

        await self.send_text(target, f"Unknown command.\n{self._help_text(is_superuser)}")

    async def _handle_permission_command(self, target: IMChatTarget, is_allowed: bool, args: list[str]):
        permission_target = self._resolve_permission_target(target, args)
        if permission_target is None:
            action = "allow" if is_allowed else "deny"
            await self.send_text(
                target,
                (
                    "Usage:\n"
                    f"{self.command_usage(f'{action} user <id>')}\n"
                    f"{self.command_usage(f'{action} group <id>')}\n"
                    f"{self.command_usage(action)} in a group"
                ),
            )
            return

        await set_im_permission(
            self.session_factory,
            account_id=permission_target.binding_account_id,
            chat_type=permission_target.chat_type,
            chat_id=permission_target.chat_id,
            is_allowed=is_allowed,
        )
        status = "allowed" if is_allowed else "denied"
        await self.send_text(
            target,
            f"Permission {status} for {permission_target.chat_type} {permission_target.chat_id}.",
        )

    def _resolve_permission_target(self, target: IMChatTarget, args: list[str]) -> IMChatTarget | None:
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
            return IMChatTarget(
                platform=target.platform,
                account_id=target.account_id,
                chat_type="private",
                chat_id=target_id,
            )
        if target_type == "group":
            return IMChatTarget(
                platform=target.platform,
                account_id=target.account_id,
                chat_type="group",
                chat_id=target_id,
            )
        return None

    def _help_text(self, is_superuser: bool) -> str:
        lines = [
            "Commands:",
            f"{self.command_usage('cancel')} stops the current response.",
            f"{self.command_usage('drop')} resets this IM session.",
        ]
        if is_superuser:
            lines.extend(
                [
                    f"{self.command_usage('allow user <id>')} grants permission to a private chat.",
                    f"{self.command_usage('allow group <id>')} grants permission to a group chat.",
                    f"{self.command_usage('deny user <id>')} revokes permission from a private chat.",
                    f"{self.command_usage('deny group <id>')} revokes permission from a group chat.",
                    f"{self.command_usage('allow')} or {self.command_usage('deny')} in a group targets the current group.",
                ]
            )
        return "\n".join(lines)

    async def _cancel_session(self, target: IMChatTarget):
        conversation_id = await get_im_session_conversation_id(
            self.session_factory,
            account_id=target.binding_account_id,
            chat_type=target.chat_type,
            chat_id=target.chat_id,
        )
        if conversation_id is None or not self.runner.is_running(conversation_id):
            await self.send_text(target, "No running completion in this session.")
            return

        await self.runner.cancel(conversation_id)
        await self.send_text(target, "Current completion cancelled.")

    async def _drop_session(self, target: IMChatTarget):
        conversation_id = await get_im_session_conversation_id(
            self.session_factory,
            account_id=target.binding_account_id,
            chat_type=target.chat_type,
            chat_id=target.chat_id,
        )
        if conversation_id is None:
            await self.send_text(target, "No session to drop.")
            return

        if self.runner.is_running(conversation_id):
            await self.runner.cancel(conversation_id)

        deleted = await delete_conversation(self.session_factory, self.graph, conversation_id)
        if deleted:
            await self.send_text(target, "Current session dropped. Your next message will start a new session.")
            return

        await self.send_text(target, "Current session was already gone.")

    async def _run_conversation(
        self,
        target: IMChatTarget,
        conversation_id: str,
        message_text: str,
        source_message_ref: Any | None = None,
    ):
        current_assistant_message_id: str | None = None

        try:
            job = await self.runner.run(conversation_id, message_text)
            if job is None:
                return

            async for event in self.runner.stream(conversation_id, need_history=False, job=job):
                if isinstance(event, CompletionUserMessage):
                    await self.register_user_message(target, event.message_id, source_message_ref)
                    continue

                if isinstance(event, CompletionResponseDelta):
                    if event.is_thinking:
                        continue
                    if (
                        current_assistant_message_id is not None
                        and event.message_id != current_assistant_message_id
                    ):
                        await self.finish_assistant_message(target, current_assistant_message_id)
                        current_assistant_message_id = None

                    current_assistant_message_id = event.message_id
                    await self.append_assistant_delta(target, event.message_id, event.delta)
                    continue

                if isinstance(event, CompletionResponseToolCall):
                    if current_assistant_message_id is not None:
                        await self.finish_assistant_message(target, current_assistant_message_id)
                        current_assistant_message_id = None

                    await self.send_tool_message(target, event)

            if current_assistant_message_id is not None:
                await self.finish_assistant_message(target, current_assistant_message_id)
                current_assistant_message_id = None
        except asyncio.CancelledError:
            if current_assistant_message_id is not None:
                self.cancel_assistant_message(target, current_assistant_message_id)
            raise
        except Exception as exc:
            if current_assistant_message_id is not None:
                with suppress(Exception):
                    await self.finish_assistant_message(target, current_assistant_message_id)
            log.exception("%s conversation failed for %s: %s", self.platform_label, conversation_id, exc)
            with suppress(Exception):
                await self.send_text(target, f"Request failed: {exc}")

    async def register_user_message(
        self,
        target: IMChatTarget,
        message_uuid: str,
        source_message_ref: Any | None,
    ):
        return None

    async def send_tool_message(self, target: IMChatTarget, tool_call: CompletionResponseToolCall):
        await self.send_text(target, render_tool_message(tool_call), message_uuid=tool_call.message_id)

    @abstractmethod
    async def append_assistant_delta(
        self,
        target: IMChatTarget,
        message_uuid: str,
        delta: str,
    ):
        raise NotImplementedError

    @abstractmethod
    async def finish_assistant_message(
        self,
        target: IMChatTarget,
        message_uuid: str,
    ):
        raise NotImplementedError

    def cancel_assistant_message(
        self,
        target: IMChatTarget,
        message_uuid: str,
    ):
        return None

    @abstractmethod
    async def send_text(self, target: IMChatTarget, text: str, message_uuid: str | None = None):
        raise NotImplementedError
