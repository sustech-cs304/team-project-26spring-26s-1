import datetime as dt
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from . import models as db_models
    
async def db_get_message_by_langchain_id(session_factory: async_sessionmaker, conversation_id: str, langchain_id: str) -> db_models.Message | None:
    async with session_factory() as session:
        session: AsyncSession
        result = await session.execute(
            select(db_models.Message)
                .where(db_models.Message.conversation_id == conversation_id)
                .where(db_models.Message.langchain_id == langchain_id)
                .order_by(db_models.Message.seq.desc())
                .limit(1)
        )
        return result.scalars().first()


async def db_get_conversation(session_factory: async_sessionmaker, conversation_id: str) -> db_models.Conversation | None:
    async with session_factory() as session:
        session: AsyncSession
        return await session.get(db_models.Conversation, conversation_id)


async def db_update_conversation_title(session_factory: async_sessionmaker, conversation_id: str, title: str) -> bool:
    async with session_factory() as session:
        session: AsyncSession
        result = await session.execute(
            update(db_models.Conversation)
                .where(db_models.Conversation.id == conversation_id)
                .values(title=title)
        )
        await session.commit()
        return result.rowcount > 0


async def db_update_message(
    session_factory: async_sessionmaker,
    conversation_id: str,
    content: str,
    message_id: str | None = None,
    langchain_id: str | None = None,
    attachments: list[str] = [],
    rollback_checkpoint_id: str | None = None,
) -> str:
    async with session_factory() as session:
        session: AsyncSession
        
        updates = {}
        
        updates["content"] = content
        updates["finished_at"] = dt.datetime.now(dt.timezone.utc)

        if rollback_checkpoint_id is not None:
            updates["rollback_checkpoint_id"] = rollback_checkpoint_id

        # updates["attachments"] = attachments
        if langchain_id is not None:
            updates["langchain_id"] = langchain_id

        async def get_last_seq():
            """allocate a new sequence number"""
            _result = await session.execute(
                select(db_models.Message.seq)
                    .where(db_models.Message.conversation_id == conversation_id)
                    .order_by(db_models.Message.seq.desc())
                    .limit(1)
            )
            last_seq = _result.scalar_one_or_none() or 0
            return last_seq

        if not message_id:
            if not langchain_id:
                raise ValueError("Either message_id or langchain_id must be provided")
            _result = await session.execute(
                select(db_models.Message)
                    .where(db_models.Message.langchain_id == langchain_id)
                    .where(db_models.Message.conversation_id == conversation_id)
            )
            _result = _result.scalars().first()
            if not _result: # assign a new message_id
                message_id = str(uuid4())
                
                updates["id"] = message_id
                updates["seq"] = (await get_last_seq()) + 1
                updates["conversation_id"] = conversation_id     
                updates["created_at"] = dt.datetime.now(dt.timezone.utc) # new creation timestamp    
                await session.execute(
                    insert(db_models.Message).values(updates)
                )
                
                await session.commit()
                return message_id
            else:
                message_id = _result.id
                found = True
        else:
            message_row = await session.execute(
                select(db_models.Message).where(db_models.Message.id == message_id)
            )
            found = message_row.scalar_one_or_none() is not None
            
        if not found:
            updates["id"] = message_id
            updates["seq"] = (await get_last_seq()) + 1
            updates["conversation_id"] = conversation_id     
            updates["created_at"] = dt.datetime.now(dt.timezone.utc) # new creation timestamp    
            await session.execute(
                insert(db_models.Message).values(updates)
            )
        else:
            await session.execute(
                update(db_models.Message)
                    .where(db_models.Message.id == message_id)
                    .values(updates)
            )

        await session.commit()
        return message_id
