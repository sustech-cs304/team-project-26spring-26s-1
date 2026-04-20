from __future__ import annotations

import logging
from contextlib import suppress

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters

from agent.api.conversation_runner import ConversationRunner
from agent.config import get_config
from agent.im.message_utils import split_text_chunks
from agent.im.session_controller import IMSessionController
from agent.im.types import IMChatTarget

log = logging.getLogger(__name__)

_TELEGRAM_TEXT_LIMIT = 4000


class TelegramBot(IMSessionController):
    def __init__(self, session_factory, graph, runner: ConversationRunner):
        super().__init__(
            session_factory,
            graph,
            runner,
            platform_key="telegram",
            platform_label="Telegram",
        )
        self._application: Application | None = None
        self._account_id: str | None = None

    @property
    def token(self) -> str:
        return get_config().telegram.token.strip()

    @property
    def superuser_ids(self) -> set[str]:
        return {
            str(user_id).strip()
            for user_id in get_config().telegram.superuser_ids
            if str(user_id).strip()
        }

    @property
    def command_trigger(self) -> str:
        return get_config().telegram.command_trigger

    @property
    def message_trigger(self) -> str:
        return get_config().telegram.message_trigger

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

    async def send_text(self, target: IMChatTarget, text: str):
        application = self._require_application()
        for chunk in split_text_chunks(text, _TELEGRAM_TEXT_LIMIT):
            await application.bot.send_message(chat_id=int(target.chat_id), text=chunk)

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
