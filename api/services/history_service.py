"""History and message-context service scaffold."""

from __future__ import annotations

from api.db.repository import ConversationRepository


class HistoryService:
    """Handles conversation history retrieval and history_context rewrite APIs."""

    def __init__(self, repo: ConversationRepository) -> None:
        self.repo = repo

    async def get_history(self, conversation_id: str) -> dict:
        raise NotImplementedError

    async def revise_history_context(self, message_id: str, history_context: list[dict]) -> dict:
        raise NotImplementedError
