from __future__ import annotations

from contextlib import suppress

from agent.config import AppConfig, TelegramConfig, get_config_path

from .bot import TelegramBot


class TelegramRuntime:
    def __init__(self, session_factory, graph, runner):
        self._session_factory = session_factory
        self._graph = graph
        self._runner = runner
        self._config = TelegramConfig()
        self._bot: TelegramBot | None = None

    @property
    def bot(self) -> TelegramBot | None:
        return self._bot

    async def start(self, config: AppConfig):
        await self._apply_telegram_config(get_config_path(config, "telegram"))

    async def stop(self):
        bot = self._bot
        if bot is None:
            return
        await bot.stop()
        self._bot = None

    async def apply_config(self, _old_config: AppConfig, new_config: AppConfig):
        await self._apply_telegram_config(get_config_path(new_config, "telegram"))

    async def _apply_telegram_config(self, next_config: TelegramConfig):
        next_config = next_config.model_copy(deep=True)
        current_bot = self._bot

        if current_bot is None:
            if next_config.token.strip():
                bot = TelegramBot(
                    self._session_factory,
                    self._graph,
                    self._runner,
                    telegram_config=next_config,
                )
                await bot.start()
                self._bot = bot
            self._config = next_config
            return

        if self._config.token.strip() == next_config.token.strip():
            current_bot.update_config(next_config)
            self._config = next_config
            return

        replacement_bot: TelegramBot | None = None
        if next_config.token.strip():
            replacement_bot = TelegramBot(
                self._session_factory,
                self._graph,
                self._runner,
                telegram_config=next_config,
            )
            await replacement_bot.start()

        try:
            await current_bot.stop()
        except Exception:
            if replacement_bot is not None:
                with suppress(Exception):
                    await replacement_bot.stop()
            raise

        self._bot = replacement_bot
        self._config = next_config
