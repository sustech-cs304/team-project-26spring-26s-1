from . import models as db_models
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from uuid import uuid4
import datetime as dt
    
async def db_get_message_by_langchain_id(session_factory: async_sessionmaker, langchain_id: str) -> db_models.Message | None:
    async with session_factory() as session:
        session: AsyncSession
        result = await session.execute(select(db_models.Message).where(db_models.Message.langchain_id == langchain_id))
        return result.scalars().first()
    
async def db_update_message(session_factory: async_sessionmaker, conversation_id: str, message_id: str | None, langchain_id: str | None, content: str, attachments: list[str] = []) -> str:
    async with session_factory() as session:
        session: AsyncSession
        
        updates = {}
        
        updates["content"] = content
        updates["finished_at"] = dt.datetime.now(dt.timezone.utc)
        
        # updates["attachments"] = attachments
        if langchain_id:
            updates["langchain_id"] = langchain_id
            
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
                # allocate a new sequence number
                _result = await session.execute(
                    select(db_models.Message.seq)
                        .where(db_models.Message.conversation_id == conversation_id)
                        .order_by(db_models.Message.seq.desc())
                        .limit(1)
                )
                last_seq = _result.scalar_one_or_none() or 0
                
                
                updates["id"] = message_id
                updates["seq"] = last_seq + 1
                updates["conversation_id"] = conversation_id     
                updates["created_at"] = dt.datetime.now(dt.timezone.utc) # new creation timestamp    
                await session.execute(
                    insert(db_models.Message).values(updates)
                )
            else:
                message_id = _result.id
            
        await session.execute(
            update(db_models.Message)
                .where(db_models.Message.id == message_id)
                .values(updates)
        )
            
        await session.commit()
        return message_id