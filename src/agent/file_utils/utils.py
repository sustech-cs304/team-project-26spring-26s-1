from __future__ import annotations

import asyncio
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, status
from starlette.datastructures import UploadFile
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
PARSE_REQUIRED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".jp2",
    ".webp",
    ".gif",
    ".bmp",
    ".docx",
    ".pptx",
    ".xls",
    ".xlsx",
}
DIRECT_READ_EXTENSIONS = {".txt", ".md"}

SUPPORTED_UPLOAD_EXTENSIONS_TEXT = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
MAX_UPLOAD_SIZE_TEXT = "10MB"


@dataclass(slots=True)
class PendingMessageAttachmentRef:
    message_attachment_id: str
    attachment_id: str
    name: str


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
        _raise_invalid_upload("Invalid file input: expected a multipart uploaded file.")

    normalized_name = file_name.strip()
    if not normalized_name:
        _raise_invalid_upload("Filename is required: uploaded file must have a non-empty filename.")

    if len(normalized_name) > MAX_UPLOAD_FILENAME_LENGTH:
        _raise_invalid_upload(
            f"Filename too long: maximum length is {MAX_UPLOAD_FILENAME_LENGTH} characters."
        )

    if any(separator in normalized_name for separator in ("/", "\\")):
        _raise_invalid_upload(
            "Invalid filename: path separators are not allowed in uploaded filenames."
        )

    if normalized_name in {".", ".."}:
        _raise_invalid_upload("Invalid filename: reserved path names '.' and '..' are not allowed.")

    return normalized_name


def validate_attachment_display_name(name: str) -> str:
    return _validate_upload_filename(name)


def _validate_upload_extension_and_mime(file_name: str, content_type: str | None) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        _raise_invalid_upload(
            "Unsupported file type: "
            f"'{suffix or '(no extension)'}'. Supported file extensions are: {SUPPORTED_UPLOAD_EXTENSIONS_TEXT}."
        )

    normalized_content_type = _normalize_content_type(content_type)
    guessed_content_type, _ = mimetypes.guess_type(file_name)
    allowed_content_types = ALLOWED_UPLOAD_EXTENSIONS[suffix]

    if normalized_content_type and normalized_content_type not in allowed_content_types:
        _raise_invalid_upload(
            "MIME type does not match file extension: "
            f"received '{normalized_content_type}' for '{suffix}', expected one of {sorted(allowed_content_types)}."
        )

    if guessed_content_type and guessed_content_type not in allowed_content_types:
        _raise_invalid_upload(
            "File extension is not accepted: "
            f"'{suffix}' resolves to MIME '{guessed_content_type}', but allowed MIME types are {sorted(allowed_content_types)}."
        )

    return suffix


async def validate_upload_file(file: UploadFile) -> tuple[str, str]:
    file_name = _validate_upload_filename(file.filename)
    suffix = _validate_upload_extension_and_mime(file_name, file.content_type)

    content = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)
    await file.seek(0)

    if not content:
        _raise_invalid_upload("Empty file is not allowed: uploaded file content must not be empty.")

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                "File too large: uploaded files that require parsing must be no larger than "
                f"{MAX_UPLOAD_SIZE_TEXT}. Supported file extensions are: {SUPPORTED_UPLOAD_EXTENSIONS_TEXT}."
            ),
        )

    return file_name, suffix


def validate_file_id(file_id: str) -> str:
    if not isinstance(file_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format: file_id must be a UUID string.",
        )

    normalized_file_id = file_id.strip()
    if not normalized_file_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format: file_id must be a non-empty UUID string.",
        )

    if len(normalized_file_id) > 36:
        raise HTTPException(
            status_code=status.HTTP_414_REQUEST_URI_TOO_LONG,
            detail="File ID too long: file_id must be a standard 36-character UUID string.",
        )

    try:
        parsed = uuid.UUID(normalized_file_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format: file_id must match the canonical UUID format.",
        ) from exc

    canonical_file_id = str(parsed)
    if canonical_file_id != normalized_file_id.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format: file_id must match the canonical UUID format.",
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment not found: attachment_id={attachment_id}",
            )
        return attachment


async def load_attachment_content(
    session_factory: async_sessionmaker,
    attachment_id: str,
) -> tuple[str, str]:
    attachment = await get_attachment(session_factory, attachment_id)
    if attachment.status != "completed":
        if attachment.status in {"created", "processing"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Attachment is still being processed and cannot be used yet: "
                    f"attachment_id={attachment_id}, status={attachment.status}. "
                    f"If this file requires parsing, ensure it is within {MAX_UPLOAD_SIZE_TEXT} and one of: {SUPPORTED_UPLOAD_EXTENSIONS_TEXT}."
                ),
            )
        if attachment.status == "failed":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Attachment processing failed: "
                    f"attachment_id={attachment_id}. "
                    f"If this is a newly uploaded file, ensure the file is within {MAX_UPLOAD_SIZE_TEXT} and uses a supported extension: {SUPPORTED_UPLOAD_EXTENSIONS_TEXT}."
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attachment is not ready: "
                f"attachment_id={attachment_id}, status={attachment.status}"
            ),
        )

    suffix = Path(attachment.path).suffix.lower()
    name = Path(attachment.path).name
    read_path = (
        Path(attachment.path)
        if suffix in DIRECT_READ_EXTENSIONS
        else Path(attachment.path).with_suffix(".md")
    )
    if not read_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Attachment content file is missing: "
                f"attachment_id={attachment_id}, path={read_path}"
            ),
        )

    content = await asyncio.to_thread(lambda: read_path.read_text(encoding="utf-8"))
    return content, name


async def create_pending_message_attachment(
    session_factory: async_sessionmaker,
    attachment_id: str,
    name: str,
) -> PendingMessageAttachmentRef:
    attachment_id = validate_file_id(attachment_id)
    display_name = validate_attachment_display_name(name)

    async with session_factory() as session:
        session: AsyncSession
        async with session.begin():
            attachment = (
                await session.execute(
                    select(db_models.Attachment).where(db_models.Attachment.id == attachment_id)
                )
            ).scalar_one_or_none()
            if not attachment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        "Attachment not found during linking: "
                        f"attachment_id={attachment_id}"
                    ),
                )
            message_attachment_row = db_models.MessageAttachment(
                message_id=None,
                attachment_id=attachment_id,
                name=display_name,
            )
            session.add(message_attachment_row)
            await session.flush()

            return PendingMessageAttachmentRef(
                message_attachment_id=message_attachment_row.id,
                attachment_id=attachment_id,
                name=display_name,
            )


async def bind_pending_message_attachments(
    session_factory: async_sessionmaker,
    message_id: str,
    pending_attachment_ids: Iterable[str],
) -> list[PendingMessageAttachmentRef]:
    normalized_message_id = validate_file_id(message_id)
    normalized_pending_ids = [validate_file_id(pending_id) for pending_id in pending_attachment_ids]
    print(normalized_message_id)
    print(normalized_pending_ids)

    if not normalized_pending_ids:
        return []

    async with session_factory() as session:
        session: AsyncSession
        async with session.begin():
            rows = (
                await session.execute(
                    select(db_models.MessageAttachment)
                    .where(db_models.MessageAttachment.id.in_(normalized_pending_ids))
                )
            ).scalars().all()

            pending_by_id = {row.id: row for row in rows}
            print(pending_by_id)
            bound_attachments: list[PendingMessageAttachmentRef] = []

            for pending_id in normalized_pending_ids:
                pending = pending_by_id.get(pending_id)
                print(f"Processing pending attachment id {pending_id}: found={pending is not None}, message_id={pending.message_id if pending else 'N/A'}")
                if pending is None:
                    print(f"Pending attachment not found for id {pending_id}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Pending attachment not found: message_attachment_id={pending_id}",
                    )
                if pending.message_id is not None:
                    if pending.message_id == normalized_message_id:
                        bound_attachments.append(
                            PendingMessageAttachmentRef(
                                message_attachment_id=pending.id,
                                attachment_id=pending.attachment_id,
                                name=pending.name,
                            )
                        )
                        continue
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=(
                                "Pending attachment has already been bound: "
                                f"message_attachment_id={pending_id}, message_id={pending.message_id}"
                            ),
                        )

                pending.message_id = normalized_message_id
                bound_attachments.append(
                    PendingMessageAttachmentRef(
                        message_attachment_id=pending.id,
                        attachment_id=pending.attachment_id,
                        name=pending.name,
                    )
                )

            return bound_attachments
