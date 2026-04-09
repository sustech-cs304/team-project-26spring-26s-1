from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import agent.db.models as db_models


async def get_attachment(
    session_factory: async_sessionmaker,
    attachment_id: str,
) -> db_models.Attachment:
    async with session_factory() as session:
        session: AsyncSession
        attachment_row = await session.execute(
            select(db_models.Attachment).where(db_models.Attachment.id == attachment_id)
        )
        attachment = attachment_row.scalars().first()
        if not attachment:
            raise ValueError(f"Attachment not found in database: attachment_id={attachment_id}")
        return attachment


async def load_attachment_content(
    session_factory: async_sessionmaker,
    attachment_id: str,
) -> tuple[str, str]:
    attachment = await get_attachment(session_factory, attachment_id)
    if attachment.status != "completed":
        raise NotImplementedError(
            f"TODO: handle unparsed attachment in SSE flow: attachment_id={attachment_id}, status={attachment.status}"
        )

    suffix = Path(attachment.path).suffix.lower()
    name = Path(attachment.path).name
    read_path = Path(attachment.path) if suffix == ".txt" else Path(attachment.path).with_suffix(".md")
    if not read_path.exists():
        raise NotImplementedError(
            f"TODO: handle missing parsed attachment content in SSE flow: attachment_id={attachment_id}, path={read_path}"
        )

    content = await asyncio.to_thread(lambda: read_path.read_text(encoding="utf-8"))
    return content, name


async def link_message_attachment(
    session_factory: async_sessionmaker,
    message_id: str,
    attachment_id: str,
    name: str | None = None,
) -> None:
    async with session_factory() as session:
        session: AsyncSession
        async with session.begin():
            attachment = (
                await session.execute(
                    select(db_models.Attachment).where(db_models.Attachment.id == attachment_id)
                )
            ).scalar_one_or_none()
            if not attachment:
                raise ValueError(
                    f"Attachment not found in database during linking: attachment_id={attachment_id}"
                )
            existed = (
                await session.execute(
                    select(db_models.MessageAttachment)
                    .where(db_models.MessageAttachment.message_id == message_id)
                    .where(db_models.MessageAttachment.attachment_id == attachment_id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existed:
                return
            display_name = name or Path(attachment.path).name
            message_attachment_row = db_models.MessageAttachment(
                message_id=message_id,
                attachment_id=attachment_id,
                name=display_name,
            )
            session.add(message_attachment_row)


async def link_message_attachments(
    session_factory: async_sessionmaker,
    message_id: str,
    attachment_ids: list[str],
) -> None:
    for attachment_id in attachment_ids:
        print(f"Linking attachment {attachment_id} to message {message_id}")
        await link_message_attachment(session_factory, message_id, attachment_id)
