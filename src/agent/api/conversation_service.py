import datetime as dt
from uuid import uuid4

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import agent.db.models as db_models


async def create_conversation(
    session_factory: async_sessionmaker,
    title: str = "New Conversation",
) -> db_models.Conversation:
    conversation = db_models.Conversation(
        id=str(uuid4()),
        title=title,
        time_last_used=dt.datetime.now(tz=dt.timezone.utc),
    )

    async with session_factory() as session:
        session: AsyncSession
        session.add(conversation)
        await session.commit()

    return conversation


async def search_conversations(
    session_factory: async_sessionmaker,
    keywords: str,
    page: int = 1,
    page_size: int = 25,
) -> list[db_models.Conversation]:
    terms = [term for term in keywords.split() if term]

    async with session_factory() as session:
        session: AsyncSession

        stmt = select(db_models.Conversation)
        for term in terms:
            stmt = stmt.where(
                or_(
                    db_models.Conversation.title.ilike(f"%{term}%"),
                    exists(
                        select(1)
                        .where(db_models.Message.conversation_id == db_models.Conversation.id)
                        .where(db_models.Message.content.ilike(f"%{term}%"))
                    ),
                )
            )

        stmt = (
            stmt
            .order_by(db_models.Conversation.pinned.desc(), db_models.Conversation.time_last_used.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())


async def delete_conversation(
    session_factory: async_sessionmaker,
    graph,
    conversation_id: str,
) -> bool:
    async with session_factory() as session:
        session: AsyncSession
        conversation = await session.get(db_models.Conversation, conversation_id)
        if conversation is None:
            return False

        await session.execute(
            delete(db_models.Message).where(db_models.Message.conversation_id == conversation_id)
        )
        await session.execute(
            delete(db_models.Conversation).where(db_models.Conversation.id == conversation_id)
        )
        await session.commit()

    await graph.checkpointer.adelete_thread(conversation_id)
    return True
