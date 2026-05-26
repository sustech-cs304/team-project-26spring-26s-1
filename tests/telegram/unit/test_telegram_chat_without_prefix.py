from __future__ import annotations

from agent.config import TelegramConfig
from agent.im.telegram.bot import TelegramBot


def _bot() -> TelegramBot:
    return TelegramBot(
        session_factory=None,
        graph=None,
        runner=None,
        telegram_config=TelegramConfig(),
    )


def test_telegram_plain_text_routes_as_chat_without_message_prefix():
    bot = _bot()

    assert bot.extract_message_text("hello") == "hello"
    assert bot.extract_message_text("  今天有什么安排？  ") == "今天有什么安排？"


def test_telegram_command_trigger_still_parses_management_commands():
    bot = _bot()

    assert bot.parse_command("/agent cancel") == ("cancel", [])
    assert bot.parse_command("/agent allow user 123") == ("allow", ["user", "123"])
