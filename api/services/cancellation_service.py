"""Cancellation service."""

from __future__ import annotations

from api.db.repository import ConversationRepository
from api.runtime.manager import ConversationRuntimeManager


class CancellationService:
    def __init__(
        self,
        repo: ConversationRepository,
        runtime_manager: ConversationRuntimeManager,
    ) -> None:
        self.repo = repo
        self.runtime_manager = runtime_manager

    async def cancel(self, conversation_id: str, message_id: str) -> dict:
        await self.repo.mark_cancelled(
            conversation_id=conversation_id, message_id=message_id
        )
        self.runtime_manager.cancel_worker(conversation_id)
        return {"message": "ok"}
