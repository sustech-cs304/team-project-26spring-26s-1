from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.config import AppConfig
from agent.db.models import Attachment
from agent.file_utils.mineru import _make_headers, _submit_task, _upload_file_to_signed_url, _poll_markdown_url, _download_markdown
import aiohttp
import mimetypes
from sqlalchemy.ext.asyncio import async_sessionmaker

legal_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".jp2", ".webp", ".gif", ".bmp", ".docx", ".pptx", ".xls", ".xlsx"}
readable_extensions = {".txt", ".md"}


class FileProcessError(RuntimeError):
    """Raised when an uploaded file cannot be processed into a usable attachment."""

def _safe_file_name(file_name: str | None) -> str:
    if not file_name:
        return "uploaded_file"
    clean_name = Path(file_name).name
    return clean_name or "uploaded_file"


def _resolve_upload_root(config: AppConfig) -> Path:
    root = Path(config.file.upload_path)
    if not root.is_absolute():
        root = (Path.cwd() / root).resolve()
    return root


async def _read_file_and_hash(file: UploadFile) -> tuple[bytes, str]:
    content = await file.read()
    digest = hashlib.sha256(content).hexdigest()
    return content, digest

async def store_attachment(file: UploadFile, session_factory: async_sessionmaker, config: AppConfig) -> tuple[str, str | None]:
    """Store uploaded file and synchronously produce a usable attachment."""
    content, digest = await _read_file_and_hash(file)
    suffix = Path(file.filename).suffix.lower()
    need_extract = suffix in legal_extensions
    async with session_factory() as session:
        existing = await session.execute(select(Attachment).where(Attachment.hash == digest).limit(1))
        existing_attachment = existing.scalar_one_or_none()
        if existing_attachment:
            print(f"Found existing attachment with id {existing_attachment.id}, reusing processing result.")
            if existing_attachment.status == "completed":
                mime_type, _ = mimetypes.guess_type(existing_attachment.path)
                return existing_attachment.id, mime_type
            if existing_attachment.status == "failed":
                raise FileProcessError(f"File processing previously failed: {file.filename}")
        else:
            print(f"Creating new attachment for file: {file.filename}")
            timestamp = dt.datetime.now(tz=dt.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            target_dir = _resolve_upload_root(config) / timestamp
            target_dir.mkdir(parents=True, exist_ok=True)
            source_file = (target_dir / _safe_file_name(file.filename)).resolve()
            await asyncio.to_thread(source_file.write_bytes, content)
            if not source_file.exists():
                raise FileNotFoundError(f"Source file not found: {source_file}")

            attachment = Attachment(
                hash=digest,
                path=str(source_file),
                status="created" if need_extract else "completed",
                mineru_id=None,
            )
            session.add(attachment)
            await session.commit()
            await session.refresh(attachment)
            existing_attachment = attachment

    assert existing_attachment is not None
    if need_extract and existing_attachment.status != "completed":
        base_url = config.file.mineru.base_url
        api_key = config.file.mineru.api_key
        source_file = Path(existing_attachment.path).resolve()
        if not existing_attachment.mineru_id:
            timeout = aiohttp.ClientTimeout(total=120)
            try:
                async with aiohttp.ClientSession(headers=_make_headers(api_key), timeout=timeout) as csession:
                    task_id, file_url = await _submit_task(csession, base_url, source_file)
                    await _upload_file_to_signed_url(file_url, source_file)
            except Exception as exc:
                existing_attachment.status = "failed"
                async with session_factory() as session:
                    db_attachment = await session.get(Attachment, existing_attachment.id)
                    if db_attachment:
                        db_attachment.status = "failed"
                        await session.commit()
                raise FileProcessError(str(exc)) from exc
            async with session_factory() as session:
                db_attachment = await session.get(Attachment, existing_attachment.id)
                if not db_attachment:
                    raise FileProcessError(f"Attachment not found during processing: {existing_attachment.id}")
                db_attachment.mineru_id = task_id
                db_attachment.status = "processing"
                await session.commit()
        try:
            await extract_attachment(existing_attachment.id, session_factory, config)
        except FileProcessError:
            raise
        except Exception as exc:
            raise FileProcessError(str(exc)) from exc

    async with session_factory() as session:
        attachment = await session.get(Attachment, existing_attachment.id)
        if not attachment:
            raise FileProcessError(f"Attachment not found after processing: {existing_attachment.id}")
        if attachment.status != "completed":
            raise FileProcessError(f"File processing did not complete successfully: {file.filename}")
        mime_type, _ = mimetypes.guess_type(attachment.path)
        return attachment.id, mime_type


async def extract_attachment(file_id: str, session_factory: async_sessionmaker, config: AppConfig):
    """Poll and download markdown result."""
    
    async with session_factory() as session:
        existing = await session.execute(select(Attachment).where(Attachment.id == file_id).limit(1))
        attachment = existing.scalar_one_or_none()
        if not attachment:
            raise FileProcessError(f"Attachment with id {file_id} not found")
        if attachment.status == "completed":
            return
        if not attachment.mineru_id:
            attachment.status = "failed"
            await session.commit()
            raise FileProcessError(f"Attachment has no parser task id: {file_id}")
        
        print(f"Extracting attachment {file_id} with MinerU task {attachment.mineru_id}...")
        source_file = Path(attachment.path).resolve()
        markdown_file = source_file.with_suffix(".md")
        task_id = attachment.mineru_id
        base_url=config.file.mineru.base_url
        api_key=config.file.mineru.api_key
        timeout = aiohttp.ClientTimeout(total=120)
        try:
            async with aiohttp.ClientSession(headers=_make_headers(api_key), timeout=timeout) as csession:
                markdown_url = await _poll_markdown_url(
                    csession,
                    base_url,
                    task_id,
                )
                markdown_content = await _download_markdown(csession, markdown_url)
            markdown_file.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(markdown_file.write_text, markdown_content, "utf-8")
            attachment.status = "completed"
            await session.commit()
        except Exception as exc:
            attachment.status = "failed"
            await session.commit()
            raise FileProcessError(str(exc)) from exc
