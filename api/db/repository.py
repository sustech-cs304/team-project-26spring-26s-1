"""Repository layer — ORM-based persistence operations."""

from __future__ import annotations

import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.orm import ConversationORM, MessageORM


class ConversationRepository:
    """Persistence abstraction for conversation/message operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def create_conversation(self) -> ConversationORM:
        now = int(time.time() * 1000)
        conv = ConversationORM(
            conversation_id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            title="新对话",
            is_active=1,
            is_pinned=0,
            context="{}",
            metadata_json="{}",
        )
        self.session.add(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv

    async def get_conversation(self, conversation_id: str) -> ConversationORM | None:
        stmt = select(ConversationORM).where(
            ConversationORM.conversation_id == conversation_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_conversations(
        self, page: int, page_size: int
    ) -> list[ConversationORM]:
        offset = (page - 1) * page_size
        stmt = (
            select(ConversationORM)
            .order_by(
                ConversationORM.is_pinned.desc(),
                ConversationORM.updated_at.desc(),
            )
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_conversations(
        self, keywords: str, page: int, page_size: int
    ) -> list[ConversationORM]:
        offset = (page - 1) * page_size
        stmt = (
            select(ConversationORM)
            .where(ConversationORM.title.contains(keywords))
            .order_by(ConversationORM.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_conversation(
        self,
        conversation_id: str,
        title: str | None,
        is_pinned: bool | None,
    ) -> ConversationORM:
        conv = await self.get_conversation(conversation_id)
        if conv is None:
            raise ValueError(f"Conversation {conversation_id!r} not found.")
        now = int(time.time() * 1000)
        if title is not None:
            conv.title = title
        if is_pinned is not None:
            conv.is_pinned = int(is_pinned)
        conv.updated_at = now
        await self.session.commit()
        await self.session.refresh(conv)
        return conv

    async def delete_conversation(self, conversation_id: str) -> None:
        conv = await self.get_conversation(conversation_id)
        if conv is None:
            raise ValueError(f"Conversation {conversation_id!r} not found.")
        await self.session.delete(conv)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def create_user_message(
        self,
        conversation_id: str,
        request_id: str,
        content: str | None,
    ) -> MessageORM:
        """Insert the user-turn message and return it."""
        seq_stmt = (
            select(MessageORM.seq)
            .where(MessageORM.conversation_id == conversation_id)
            .order_by(MessageORM.seq.desc())
            .limit(1)
        )
        last_seq = (await self.session.execute(seq_stmt)).scalar_one_or_none()
        now = int(time.time() * 1000)
        msg = MessageORM(
            message_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            seq=(last_seq or 0) + 1,
            role="user",
            content=content or "",
            status="final",
            thought_steps="[]",
            history_context="[]",
            created_at=now,
            updated_at=now,
            metadata_json="{}",
        )
        self.session.add(msg)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def save_completion_result(
        self, conversation_id: str, message_id: str
    ) -> None:
        """Mark an assistant message as fully streamed."""
        stmt = select(MessageORM).where(MessageORM.message_id == message_id)
        msg = (await self.session.execute(stmt)).scalar_one_or_none()
        if msg is not None:
            msg.status = "final"
            msg.updated_at = int(time.time() * 1000)
            await self.session.commit()

    async def mark_cancelled(self, conversation_id: str, message_id: str) -> None:
        """Mark a message as errored and the conversation as inactive."""
        now = int(time.time() * 1000)
        msg_stmt = select(MessageORM).where(MessageORM.message_id == message_id)
        msg = (await self.session.execute(msg_stmt)).scalar_one_or_none()
        if msg is not None:
            msg.status = "error"
            msg.updated_at = now
        conv = await self.get_conversation(conversation_id)
        if conv is not None:
            conv.is_active = 0
            conv.updated_at = now
        await self.session.commit()
