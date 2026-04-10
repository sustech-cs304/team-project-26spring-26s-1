from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse

from agent.api.file_models import FileInfoResponse, FileUploadResponse
from agent.file_utils.extract import FileProcessError, store_attachment
from agent.file_utils.utils import (
    create_pending_message_attachment,
    validate_file_id,
    validate_upload_file,
)
from agent.db.models import Attachment, MessageAttachment
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path

router = APIRouter()

@router.post("/files/upload", response_model=FileUploadResponse)
async def upload_file(request: Request, file: UploadFile = File(...)) -> FileUploadResponse:
    """Upload a file and return only after the attachment is ready for downstream consumption."""
    file_name, _ = await validate_upload_file(file)
    try:
        attachment_id, mime_type = await store_attachment(file, session_factory=request.app.state.async_session, config=request.app.state.config)
    except FileProcessError as exc:
        return JSONResponse(status_code=status.HTTP_417_EXPECTATION_FAILED, content={"message": str(exc)})
    pending_attachment = await create_pending_message_attachment(
        request.app.state.async_session,
        attachment_id,
        file_name,
    )
    return FileUploadResponse(
        file_id=pending_attachment.message_attachment_id,
        mime_type=mime_type,
        file_name=file_name,
    )


@router.get("/file/{file_id}")
async def get_file(request: Request, file_id: str):
    file_id = validate_file_id(file_id)
    async with request.app.state.async_session() as session:
        session : AsyncSession
        attachment = await session.execute(select(Attachment).where(Attachment.id == file_id).limit(1))
        attachment = attachment.scalar_one_or_none()
        file_path = attachment.path if attachment else None
    if file_path is None:
        raise HTTPException(status_code=404, detail="File not found")
    file_path = Path(file_path)
    return FileResponse(path=file_path)


@router.get("/files/{message_id}/{file_id}/info", response_model=FileInfoResponse)
async def get_file_info(request: Request, file_id: str, message_id: str) -> FileInfoResponse:
    file_id = validate_file_id(file_id)
    message_id = validate_file_id(message_id)
    async with request.app.state.async_session() as session:
        session : AsyncSession
        result = await session.execute(
            select(MessageAttachment, MessageAttachment.name)
            .where(MessageAttachment.attachment_id == file_id)
            .where(MessageAttachment.message_id == message_id)
            .limit(1)
        )
        row = result.one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")

        message_attachment, display_name = row
        if not message_attachment:
            raise HTTPException(status_code=404, detail="File not found")
        #type should be 'image', 'pdf', 'markdown', 'text' or 'other'
        suffix = Path(display_name).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".jp2", ".webp", ".gif", ".bmp"}:
            type = "image"
        elif suffix == ".pdf":
            type = "pdf"
        elif suffix in {".md", ".markdown"}:
            type = "markdown"
        elif suffix in {".txt"}:
            type = "text"
        else:
            type = "other"
        return FileInfoResponse(
            file_id=message_attachment.id,
            file_type=type,
            file_name=display_name,
        )