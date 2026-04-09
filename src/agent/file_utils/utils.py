from __future__ import annotations

import asyncio
import mimetypes
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import agent.db.models as db_models


MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_FILENAME_LENGTH = 512
ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".jp2": {"image/jp2", "image/jpx", "image/jpeg2000"},
    ".webp": {"image/webp"},
    ".gif": {"image/gif"},
    ".bmp": {"image/bmp", "image/x-ms-bmp"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
        "application/zip",
    },
    ".xls": {
        "application/vnd.ms-excel",
        "application/octet-stream",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    },
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
}


def _raise_invalid_upload(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _normalize_content_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    normalized = content_type.strip().lower()
    if not normalized:
        return None
    return normalized.split(";", 1)[0].strip()


def _validate_upload_filename(file_name: str | None) -> str:
    if not isinstance(file_name, str):
        _raise_invalid_upload("Invalid file input")

    normalized_name = file_name.strip()
    if not normalized_name:
        _raise_invalid_upload("Filename is required")

    if len(normalized_name) > MAX_UPLOAD_FILENAME_LENGTH:
        _raise_invalid_upload("Filename too long")

    if any(separator in normalized_name for separator in ("/", "\\")):
        _raise_invalid_upload("Invalid filename")

    if normalized_name in {".", ".."}:
        _raise_invalid_upload("Invalid filename")

    return normalized_name


def _validate_upload_extension_and_mime(file_name: str, content_type: str | None) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        _raise_invalid_upload(f"Unsupported file type: {suffix}")

    normalized_content_type = _normalize_content_type(content_type)
    guessed_content_type, _ = mimetypes.guess_type(file_name)
    allowed_content_types = ALLOWED_UPLOAD_EXTENSIONS[suffix]

    if normalized_content_type and normalized_content_type not in allowed_content_types:
        _raise_invalid_upload("MIME type does not match file extension")

    if guessed_content_type and guessed_content_type not in allowed_content_types:
        _raise_invalid_upload("MIME type does not match file extension")

    return suffix


async def validate_upload_file(file: UploadFile) -> tuple[str, str]:
    if not isinstance(file, UploadFile):
        _raise_invalid_upload("Invalid file input")

    file_name = _validate_upload_filename(file.filename)
    suffix = _validate_upload_extension_and_mime(file_name, file.content_type)

    content = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)
    await file.seek(0)

    if not content:
        _raise_invalid_upload("Empty file is not allowed")

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large",
        )

    return file_name, suffix


def validate_file_id(file_id: str) -> str:
    if not isinstance(file_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format",
        )

    normalized_file_id = file_id.strip()
    if not normalized_file_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format",
        )

    if len(normalized_file_id) > 36:
        raise HTTPException(
            status_code=status.HTTP_414_REQUEST_URI_TOO_LONG,
            detail="File ID too long",
        )

    try:
        parsed = uuid.UUID(normalized_file_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format",
        ) from exc

    canonical_file_id = str(parsed)
    if canonical_file_id != normalized_file_id.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format",
        )

    return canonical_file_id


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
