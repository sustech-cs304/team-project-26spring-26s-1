from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import logging
from contextlib import suppress
import time
from typing import Any, Literal

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters

from agent.api.conversation_models import CompletionResponseToolCall
from agent.api.conversation_runner import ConversationRunner
from agent.config import TelegramConfig
from agent.im.message_utils import render_tool_message, split_text_chunks
from agent.im.session_controller import IMSessionController
from agent.im.types import IMChatTarget

log = logging.getLogger(__name__)

_TELEGRAM_TEXT_LIMIT = 4000
_SESSION_HISTORY_LIMIT = 100
_TELEGRAM_STREAM_EDIT_INTERVAL_SECONDS = 0.5


@dataclass(slots=True)
class _TelegramMessageRecord:
    telegram_message_id: int
    kind: Literal["user", "assistant", "tool"]


@dataclass(slots=True)
class _TelegramSessionHistory:
    order: deque[str] = field(default_factory=deque)
    by_uuid: dict[str, _TelegramMessageRecord] = field(default_factory=dict)


@dataclass(slots=True)
class _TelegramAssistantDraft:
    full_text: str = ""
    rendered_chunks: list[str] = field(default_factory=list)
    telegram_message_ids: list[int] = field(default_factory=list)
    dirty: bool = False
    closed: bool = False
    force_flush: bool = False
    wake_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[Any] | None = None
    last_send_completed_at: float = 0.0


class TelegramBot(IMSessionController):
    def __init__(
        self,
        session_factory,
        graph,
        runner: ConversationRunner,
        *,
        telegram_config: TelegramConfig,
    ):
        super().__init__(
            session_factory,
            graph,
            runner,
            platform_key="telegram",
            platform_label="Telegram",
        )
        self._config = telegram_config.model_copy(deep=True)
        self._application: Application | None = None
        self._account_id: str | None = None
        self._session_history: dict[tuple[str, str, str, str], _TelegramSessionHistory] = {}
        self._assistant_drafts: dict[tuple[str, str, str, str, str], _TelegramAssistantDraft] = {}

    @property
    def token(self) -> str:
        return self._config.token.strip()

    @property
    def superuser_ids(self) -> set[str]:
        return {
            str(user_id).strip()
            for user_id in self._config.superuser_ids
            if str(user_id).strip()
        }

    @property
    def command_trigger(self) -> str:
        return self._config.command_trigger

    @property
    def message_trigger(self) -> str:
        return ""

    def extract_message_text(self, message_text: str) -> str | None:
        message = message_text.strip()
        return message or None

    def update_config(self, telegram_config: TelegramConfig):
        self._config = telegram_config.model_copy(deep=True)

    async def start(self):
        if not self.token or self._application is not None:
            return

        application = ApplicationBuilder().token(self.token).build()
        application.add_handler(MessageHandler(filters.TEXT, self._handle_text_message))
        application.add_error_handler(self._handle_error)

        try:
            await application.initialize()
            bot_user = await application.bot.get_me()
            self._account_id = str(bot_user.id)

            updater = application.updater
            if updater is None:
                raise RuntimeError("Telegram polling requires an updater.")

            await updater.start_polling()
            await application.start()
        except Exception:
            updater = application.updater
            if updater is not None:
                with suppress(Exception):
                    await updater.stop()
            with suppress(Exception):
                await application.stop()
            with suppress(Exception):
                await application.shutdown()
            raise

        self._application = application
        log.info("Telegram bot started for account %s", self._account_id)

    async def stop(self):
        application = self._application
        drafts = list(self._assistant_drafts.values())
        for draft in drafts:
            draft.closed = True
            task = draft.task
            if task is not None:
                task.cancel()
        for draft in drafts:
            task = draft.task
            if task is None:
                continue
            with suppress(asyncio.CancelledError, Exception):
                await task
        self._assistant_drafts.clear()
        self._application = None
        self._account_id = None
        if application is None:
            return

        updater = application.updater
        if updater is not None:
            with suppress(Exception):
                await updater.stop()
        with suppress(Exception):
            await application.stop()
        with suppress(Exception):
            await application.shutdown()

    async def send_text(self, target: IMChatTarget, text: str, message_uuid: str | None = None):
        application = self._require_application()
        last_message_id: int | None = None
        for chunk in split_text_chunks(text, _TELEGRAM_TEXT_LIMIT):
            sent_message = await application.bot.send_message(chat_id=int(target.chat_id), text=chunk)
            last_message_id = sent_message.message_id

        if message_uuid is not None and last_message_id is not None:
            self._remember_message(target, message_uuid, last_message_id, kind="assistant")

    async def send_tool_message(self, target: IMChatTarget, tool_call: CompletionResponseToolCall):
        application = self._require_application()
        text = render_tool_message(tool_call, truncate_limit=_TELEGRAM_TEXT_LIMIT)
        record = self._get_message_record(target, tool_call.message_id)

        if record is not None and record.kind == "tool":
            try:
                edited_message = await application.bot.edit_message_text(
                    chat_id=int(target.chat_id),
                    message_id=record.telegram_message_id,
                    text=text,
                )
                edited_message_id = getattr(edited_message, "message_id", record.telegram_message_id)
                self._remember_message(target, tool_call.message_id, edited_message_id, kind="tool")
                return
            except Exception as exc:
                log.debug(
                    "Failed to edit Telegram tool message in place: chat_id=%s message_uuid=%s error=%s",
                    target.chat_id,
                    tool_call.message_id,
                    exc,
                )

        sent_message = await application.bot.send_message(chat_id=int(target.chat_id), text=text)
        self._remember_message(target, tool_call.message_id, sent_message.message_id, kind="tool")

    async def append_assistant_delta(self, target: IMChatTarget, message_uuid: str, delta: str):
        key = self._assistant_draft_key(target, message_uuid)
        draft = self._assistant_drafts.get(key)
        if draft is None:
            draft = _TelegramAssistantDraft()
            self._assistant_drafts[key] = draft

        draft.full_text += delta
        draft.dirty = True
        draft.wake_event.set()
        if draft.task is None or draft.task.done():
            draft.task = self._start_task(self._run_assistant_draft(target, message_uuid, draft))

    async def finish_assistant_message(self, target: IMChatTarget, message_uuid: str):
        draft = self._assistant_drafts.get(self._assistant_draft_key(target, message_uuid))
        if draft is None:
            return

        draft.closed = True
        draft.force_flush = True
        draft.wake_event.set()
        if draft.task is not None:
            await asyncio.shield(draft.task)

    def cancel_assistant_message(self, target: IMChatTarget, message_uuid: str):
        key = self._assistant_draft_key(target, message_uuid)
        draft = self._assistant_drafts.pop(key, None)
        if draft is None:
            return
        draft.closed = True
        if draft.task is not None:
            draft.task.cancel()

    async def register_user_message(
        self,
        target: IMChatTarget,
        message_uuid: str,
        source_message_ref: Any | None,
    ):
        if not isinstance(source_message_ref, int):
            return
        self._remember_message(target, message_uuid, source_message_ref, kind="user")

    async def _handle_text_message(self, update: Update, _context):        
        if update.effective_user is not None and update.effective_user.is_bot:
            return

        target = self._extract_target(update)
        message = update.effective_message
        if target is None or message is None or not message.text:
            return

        await self.route_message(
            target,
            message.text,
            self.is_superuser(update.effective_user.id if update.effective_user else None),
            source_message_ref=message.message_id,
        )

    async def _handle_error(self, update: object, context):
        log.error("Telegram update handling failed for %s: %s", update, context.error)

    def _extract_target(self, update: Update) -> IMChatTarget | None:
        chat = update.effective_chat
        if chat is None or self._account_id is None:
            return None

        if chat.type == "private":
            chat_type = "private"
        elif chat.type in {"group", "supergroup"}:
            chat_type = "group"
        else:
            return None

        return IMChatTarget(
            platform=self.platform_key,
            account_id=self._account_id,
            chat_type=chat_type,
            chat_id=str(chat.id),
        )

    def _require_application(self) -> Application:
        if self._application is None:
            raise RuntimeError("Telegram bot is not running.")
        return self._application

    def _assistant_draft_key(self, target: IMChatTarget, message_uuid: str) -> tuple[str, str, str, str, str]:
        return (*target.session_key(), message_uuid)

    def _get_session_history(self, target: IMChatTarget) -> _TelegramSessionHistory:
        key = target.session_key()
        history = self._session_history.get(key)
        if history is None:
            history = _TelegramSessionHistory()
            self._session_history[key] = history
        return history

    async def _run_assistant_draft(
        self,
        target: IMChatTarget,
        message_uuid: str,
        draft: _TelegramAssistantDraft,
    ):
        try:
            while True:
                await draft.wake_event.wait()
                draft.wake_event.clear()

                while True:
                    if not draft.dirty:
                        if draft.closed:
                            return
                        break

                    if draft.telegram_message_ids and not draft.force_flush:
                        delay = _TELEGRAM_STREAM_EDIT_INTERVAL_SECONDS - (
                            time.monotonic() - draft.last_send_completed_at
                        )
                        if delay > 0:
                            try:
                                await asyncio.wait_for(draft.wake_event.wait(), timeout=delay)
                            except asyncio.TimeoutError:
                                pass
                            else:
                                draft.wake_event.clear()
                                continue

                    draft.force_flush = False
                    draft.dirty = False
                    await self._flush_assistant_draft(target, message_uuid, draft)
                    draft.last_send_completed_at = time.monotonic()

                    if draft.closed and not draft.dirty:
                        return
        finally:
            key = self._assistant_draft_key(target, message_uuid)
            if self._assistant_drafts.get(key) is draft:
                self._assistant_drafts.pop(key, None)

    async def _flush_assistant_draft(
        self,
        target: IMChatTarget,
        message_uuid: str,
        draft: _TelegramAssistantDraft,
    ):
        chat_id = int(target.chat_id)
        chunks = split_text_chunks(draft.full_text, _TELEGRAM_TEXT_LIMIT)
        common = min(len(chunks), len(draft.telegram_message_ids))

        for index in range(common):
            if draft.rendered_chunks[index] == chunks[index]:
                continue
            allow_fallback = index == len(draft.telegram_message_ids) - 1
            draft.telegram_message_ids[index] = await self._update_assistant_chunk(
                chat_id,
                draft.telegram_message_ids[index],
                chunks[index],
                allow_fallback=allow_fallback,
            )

        if len(draft.telegram_message_ids) > common:
            draft.telegram_message_ids = draft.telegram_message_ids[:common]

        application = self._require_application()
        for index in range(common, len(chunks)):
            sent_message = await application.bot.send_message(chat_id=chat_id, text=chunks[index])
            draft.telegram_message_ids.append(sent_message.message_id)

        draft.rendered_chunks = chunks
        if draft.telegram_message_ids:
            self._remember_message(
                target,
                message_uuid,
                draft.telegram_message_ids[-1],
                kind="assistant",
            )

    async def _update_assistant_chunk(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        allow_fallback: bool,
    ) -> int:
        application = self._require_application()
        try:
            edited_message = await application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
            )
        except BadRequest as exc:
            error_text = str(exc).lower()
            if "message is not modified" in error_text:
                return message_id
            if not allow_fallback or (
                "message to edit not found" not in error_text
                and "message can't be edited" not in error_text
            ):
                raise

            sent_message = await application.bot.send_message(chat_id=chat_id, text=text)
            return sent_message.message_id

        return getattr(edited_message, "message_id", message_id)

    def _get_message_record(self, target: IMChatTarget, message_uuid: str) -> _TelegramMessageRecord | None:
        return self._get_session_history(target).by_uuid.get(message_uuid)

    def _remember_message(
        self,
        target: IMChatTarget,
        message_uuid: str,
        telegram_message_id: int,
        *,
        kind: Literal["user", "assistant", "tool"],
    ):
        history = self._get_session_history(target)
        existing = history.by_uuid.get(message_uuid)
        history.by_uuid[message_uuid] = _TelegramMessageRecord(
            telegram_message_id=telegram_message_id,
            kind=kind,
        )
        if existing is not None:
            return

        history.order.append(message_uuid)
        while len(history.order) > _SESSION_HISTORY_LIMIT:
            expired_uuid = history.order.popleft()
            history.by_uuid.pop(expired_uuid, None)
