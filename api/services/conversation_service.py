"""Conversation CRUD service."""

from __future__ import annotations

from fastapi import HTTPException, status

from api.db.repository import ConversationRepository
from api.models.orm import ConversationORM


class ConversationService:
    def __init__(self, repo: ConversationRepository) -> None:
        self.repo = repo

    async def create(self) -> dict:
        conv = await self.repo.create_conversation()
        return _to_dict(conv)

    async def list(self, page: int, page_size: int) -> dict:
        convs = await self.repo.list_conversations(page=page, page_size=page_size)
        return {"conversations": [_to_dict(c) for c in convs]}

    async def search(self, keywords: str, page: int, page_size: int) -> dict:
        convs = await self.repo.search_conversations(
            keywords=keywords, page=page, page_size=page_size
        )
        return {"conversations": [_to_dict(c) for c in convs]}

    async def patch(
        self, conversation_id: str, title: str | None, is_pinned: bool | None
    ) -> dict:
        try:
            await self.repo.update_conversation(
                conversation_id=conversation_id, title=title, is_pinned=is_pinned
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        return {"message": "ok"}

    async def delete(self, conversation_id: str) -> dict:
        try:
            await self.repo.delete_conversation(conversation_id=conversation_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        return {"message": "ok"}


def _to_dict(conv: ConversationORM) -> dict:
    return {
        "conversation_id": conv.conversation_id,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "title": conv.title,
        "is_active": bool(conv.is_active),
        "is_pinned": bool(conv.is_pinned),
    }
