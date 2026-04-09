from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse

from agent.api.file_models import FileInfoResponse, FileUploadResponse
from agent.file_utils.extract import FileProcessError, store_attachment
from agent.db.models import Attachment
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
import asyncio
import mimetypes
from agent.file_utils.extract import legal_extensions, readable_extensions

router = APIRouter()

@router.post("/files/upload", response_model=FileUploadResponse)
async def upload_file(request: Request, file: UploadFile = File(...)) -> FileUploadResponse:
    """Upload a file and return only after the attachment is ready for downstream consumption."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in legal_extensions and suffix not in readable_extensions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file type: {suffix}")
    try:
        attachment_id, mime_type = await store_attachment(file, session_factory=request.app.state.async_session, config=request.app.state.config)
    except FileProcessError as exc:
        return JSONResponse(status_code=status.HTTP_417_EXPECTATION_FAILED, content={"message": str(exc)})
    return FileUploadResponse(file_id=attachment_id, mime_type=mime_type)


@router.get("/file/{file_id}")
async def get_file(request: Request, file_id: str):
    async with request.app.state.async_session() as session:
        session : AsyncSession
        attachment = await session.execute(select(Attachment).where(Attachment.id == file_id).limit(1))
        attachment = attachment.scalar_one_or_none()
        file_path = attachment.path if attachment else None
    if file_path is None:
        raise HTTPException(status_code=404, detail="File not found")
    file_path = Path(file_path)
    return FileResponse(path=file_path)


@router.post("/files/{file_id}/info", response_model=FileInfoResponse)
async def get_file_info(request: Request, file_id: str) -> FileInfoResponse:
    async with request.app.state.async_session() as session:
        session : AsyncSession
        attachment = await session.execute(select(Attachment).where(Attachment.id == file_id).limit(1))
        attachment = attachment.scalar_one_or_none()
        if not attachment:
            raise HTTPException(status_code=404, detail="File not found")
        name = Path(attachment.path).name
        #type should be 'image', 'pdf', 'markdown', 'text' or 'other'
        suffix = Path(attachment.path).suffix.lower()
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
            file_id=attachment.id,
            file_type=type,
            file_name=name,
        )