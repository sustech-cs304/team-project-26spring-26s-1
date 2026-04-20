import datetime as dt
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import agent.db.models as db_models


async def get_im_session_conversation_id(
    session_factory: async_sessionmaker,
    account_id: str,
    chat_type: str,
    chat_id: str,
) -> str | None:
    async with session_factory() as session:
        session: AsyncSession
        result = await session.execute(
            select(db_models.IMSessionBinding.conversation_id)
            .where(db_models.IMSessionBinding.account_id == account_id)
            .where(db_models.IMSessionBinding.chat_type == chat_type)
            .where(db_models.IMSessionBinding.chat_id == chat_id)
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_or_create_im_session_conversation(
    session_factory: async_sessionmaker,
    account_id: str,
    chat_type: str,
    chat_id: str,
    title: str,
) -> str:
    now = dt.datetime.now(tz=dt.timezone.utc)

    async with session_factory() as session:
        session: AsyncSession
        result = await session.execute(
            select(db_models.IMSessionBinding)
            .where(db_models.IMSessionBinding.account_id == account_id)
            .where(db_models.IMSessionBinding.chat_type == chat_type)
            .where(db_models.IMSessionBinding.chat_id == chat_id)
            .limit(1)
        )
        binding = result.scalar_one_or_none()

        if binding is not None:
            conversation = await session.get(db_models.Conversation, binding.conversation_id)
            if conversation is not None:
                conversation.time_last_used = now
            binding.updated_at = now
            await session.commit()
            return binding.conversation_id

    conversation = db_models.Conversation(
        id=str(uuid4()),
        title=title,
        time_last_used=now,
    )
    binding = db_models.IMSessionBinding(
        account_id=account_id,
        chat_type=chat_type,
        chat_id=chat_id,
        conversation_id=conversation.id,
        created_at=now,
        updated_at=now,
    )

    try:
        async with session_factory() as session:
            session: AsyncSession
            session.add_all([conversation, binding])
            await session.commit()
        return conversation.id
    except IntegrityError:
        async with session_factory() as session:
            session: AsyncSession
            result = await session.execute(
                select(db_models.IMSessionBinding.conversation_id)
                .where(db_models.IMSessionBinding.account_id == account_id)
                .where(db_models.IMSessionBinding.chat_type == chat_type)
                .where(db_models.IMSessionBinding.chat_id == chat_id)
                .limit(1)
            )
            conversation_id = result.scalar_one_or_none()
            if conversation_id is None:
                raise
            return conversation_id


async def get_im_permission(
    session_factory: async_sessionmaker,
    account_id: str,
    chat_type: str,
    chat_id: str,
) -> bool | None:
    async with session_factory() as session:
        session: AsyncSession
        result = await session.execute(
            select(db_models.IMPermission.is_allowed)
            .where(db_models.IMPermission.account_id == account_id)
            .where(db_models.IMPermission.chat_type == chat_type)
            .where(db_models.IMPermission.chat_id == chat_id)
            .limit(1)
        )
        return result.scalar_one_or_none()


async def set_im_permission(
    session_factory: async_sessionmaker,
    account_id: str,
    chat_type: str,
    chat_id: str,
    is_allowed: bool,
):
    now = dt.datetime.now(tz=dt.timezone.utc)

    async with session_factory() as session:
        session: AsyncSession
        result = await session.execute(
            select(db_models.IMPermission)
            .where(db_models.IMPermission.account_id == account_id)
            .where(db_models.IMPermission.chat_type == chat_type)
            .where(db_models.IMPermission.chat_id == chat_id)
            .limit(1)
        )
        permission = result.scalar_one_or_none()

        if permission is None:
            permission = db_models.IMPermission(
                account_id=account_id,
                chat_type=chat_type,
                chat_id=chat_id,
                is_allowed=is_allowed,
                created_at=now,
                updated_at=now,
            )
            session.add(permission)
        else:
            permission.is_allowed = is_allowed
            permission.updated_at = now

        await session.commit()

