from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import logging
import uuid
from importlib import import_module
from pathlib import Path
from typing import TypedDict

import aiohttp
import mimetypes
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent.config import AppConfig, ConfigMissingError, get_config, get_config_path, require_config_fields, require_mineru_config
from agent.db.models import Attachment
from agent.file_utils.mineru import (
    MineruError,
    _download_markdown,
    _make_headers,
    _poll_markdown_url,
    _submit_task,
    _upload_file_to_signed_url,
)
from agent.file_utils.utils import PARSE_REQUIRED_EXTENSIONS

log = logging.getLogger(__name__)

class FileProcessError(RuntimeError):
    """Raised when an uploaded file cannot be processed into a usable attachment."""


class MineruSegmentTask(TypedDict):
    index: int
    page_range: str
    task_id: str


PDF_SEGMENT_PAGE_LIMIT = 20
SEGMENT_POLL_CONCURRENCY = 2


def _build_pdf_page_ranges(total_pages: int, page_limit: int = PDF_SEGMENT_PAGE_LIMIT) -> list[str]:
    if total_pages <= 0:
        return []
    ranges: list[str] = []
    for start_page in range(1, total_pages + 1, page_limit):
        end_page = min(start_page + page_limit - 1, total_pages)
        ranges.append(f"{start_page}-{end_page}" if start_page != end_page else str(start_page))
    return ranges


def _serialize_mineru_segment_tasks(tasks: list[MineruSegmentTask]) -> str:
    return json.dumps(tasks, ensure_ascii=False, separators=(",", ":"))


def _parse_mineru_segment_tasks(raw_mineru_id: str) -> list[MineruSegmentTask] | None:
    try:
        payload = json.loads(raw_mineru_id)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, list) or not payload:
        return None

    tasks: list[MineruSegmentTask] = []
    for item in payload:
        if not isinstance(item, dict):
            return None
        index = item.get("index")
        page_range = item.get("page_range")
        task_id = item.get("task_id")
        if not isinstance(index, int) or not isinstance(page_range, str) or not isinstance(task_id, str):
            return None
        tasks.append(
            {
                "index": index,
                "page_range": page_range,
                "task_id": task_id,
            }
        )

    tasks.sort(key=lambda task: task["index"])
    return tasks


async def _cleanup_processing_artifacts(source_file: Path, *, keep_markdown: bool) -> None:
    markdown_file = source_file.with_suffix(".md")
    temp_markdown_file = markdown_file.with_suffix(".md.tmp")
    paths = [temp_markdown_file]
    if not keep_markdown:
        paths.append(markdown_file)

    for path in paths:
        try:
            await asyncio.to_thread(path.unlink)
        except FileNotFoundError:
            continue
        except OSError:
            continue


async def _write_markdown_atomically(markdown_file: Path, markdown_content: str) -> None:
    temp_markdown_file = markdown_file.with_suffix(".md.tmp")
    await asyncio.to_thread(temp_markdown_file.write_text, markdown_content, "utf-8")
    await asyncio.to_thread(temp_markdown_file.replace, markdown_file)


async def _poll_and_download_segment(
    session: aiohttp.ClientSession,
    base_url: str,
    task: MineruSegmentTask,
    semaphore: asyncio.Semaphore,
) -> tuple[int, str]:
    index = task["index"]
    page_range = task["page_range"]
    task_id = task["task_id"]

    async with semaphore:
        try:
            markdown_url = await _poll_markdown_url(session, base_url, task_id)
            markdown_content = await _download_markdown(session, markdown_url)
        except MineruError as exc:
            raise FileProcessError(
                f"MinerU segment {index + 1} ({page_range}) failed: {exc}"
            ) from exc
        except Exception as exc:
            raise FileProcessError(
                f"MinerU segment {index + 1} ({page_range}) failed: {exc}"
            ) from exc

    return index, markdown_content


async def _download_segmented_markdown(
    session: aiohttp.ClientSession,
    base_url: str,
    tasks: list[MineruSegmentTask],
) -> str:
    semaphore = asyncio.Semaphore(SEGMENT_POLL_CONCURRENCY)
    jobs = [
        _poll_and_download_segment(session, base_url, task, semaphore)
        for task in tasks
    ]
    results = await asyncio.gather(*jobs)
    results.sort(key=lambda item: item[0])
    return "\n\n".join(content for _, content in results)


async def _get_pdf_total_pages(source_file: Path) -> int:
    def _count_pdf_pages() -> int:
        pypdf_module = import_module("pypdf")
        reader_cls = getattr(pypdf_module, "PdfReader", None)
        if reader_cls is None:
            raise FileProcessError("pypdf does not expose PdfReader")
        reader = reader_cls(str(source_file))
        return len(reader.pages)

    try:
        total_pages = await asyncio.to_thread(_count_pdf_pages)
    except Exception as exc:
        raise FileProcessError(f"Failed to read PDF page count for {source_file.name}: {exc}") from exc

    if total_pages <= 0:
        raise FileProcessError(f"PDF has no readable pages: {source_file.name}")
    return total_pages


def _safe_file_name(file_name: str | None) -> str:
    if not file_name:
        return "uploaded_file"
    clean_name = Path(file_name).name
    return clean_name or "uploaded_file"


def _relative_upload_root(app_config: AppConfig) -> Path:
    file_config = require_config_fields(get_config_path(app_config, "file"), "file", ("upload_path",))
    root = Path(file_config.upload_path)
    return _relative_storage_path(root) if root.is_absolute() else root


async def _read_file_and_hash(file: UploadFile) -> tuple[bytes, str]:
    content = await file.read()
    digest = hashlib.sha256(content).hexdigest()
    return content, digest


def _build_stored_file_name(attachment_id: str, file_name: str | None) -> str:
    suffix = Path(_safe_file_name(file_name)).suffix.lower()
    return f"{attachment_id}{suffix}"


def _relative_storage_path(path: Path) -> Path:
    if path.is_absolute():
        try:
            return path.relative_to(Path.cwd())
        except ValueError:
            return path
    return path


async def _persist_uploaded_file(
    content: bytes,
    attachment_id: str,
    file_name: str | None,
    app_config: AppConfig,
) -> Path:
    timestamp = dt.datetime.now(tz=dt.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    target_dir = _relative_upload_root(app_config) / timestamp
    target_dir.mkdir(parents=True, exist_ok=True)
    source_file = target_dir / _build_stored_file_name(attachment_id, file_name)
    await asyncio.to_thread(source_file.write_bytes, content)
    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")
    return source_file


async def _request_mineru_parse(
    attachment_id: str,
    source_file: Path,
    session_factory: async_sessionmaker,
    *,
    app_config: AppConfig,
    page_ranges: list[str] | None = None,
) -> None:
    timeout = aiohttp.ClientTimeout(total=120)
    mineru_id: str | None = None
    try:
        mineru_config = require_mineru_config(get_config_path(app_config, "file.mineru"))
        base_url = mineru_config.base_url
        api_key = mineru_config.api_key
        async with aiohttp.ClientSession(headers=_make_headers(api_key), timeout=timeout) as csession:
            if page_ranges:
                segment_tasks: list[MineruSegmentTask] = []
                for index, page_range in enumerate(page_ranges):
                    task_id, file_url = await _submit_task(
                        csession,
                        base_url,
                        source_file,
                        page_range=page_range,
                    )
                    await _upload_file_to_signed_url(file_url, source_file)
                    segment_tasks.append(
                        {
                            "index": index,
                            "page_range": page_range,
                            "task_id": task_id,
                        }
                    )
                mineru_id = _serialize_mineru_segment_tasks(segment_tasks)
            else:
                task_id, file_url = await _submit_task(csession, base_url, source_file)
                await _upload_file_to_signed_url(file_url, source_file)
                mineru_id = task_id
    except Exception as exc:
        async with session_factory() as session:
            db_attachment = await session.get(Attachment, attachment_id)
            if db_attachment:
                db_attachment.status = "failed"
                db_attachment.mineru_id = None
                await session.commit()
        raise FileProcessError(str(exc)) from exc

    if not mineru_id:
        raise FileProcessError(f"Failed to create MinerU task for attachment: {attachment_id}")

    async with session_factory() as session:
        db_attachment = await session.get(Attachment, attachment_id)
        if not db_attachment:
            raise FileProcessError(f"Attachment not found during processing: {attachment_id}")
        db_attachment.mineru_id = mineru_id
        db_attachment.status = "processing"
        await session.commit()

async def store_attachment(file: UploadFile, session_factory: async_sessionmaker) -> tuple[str, str | None]:
    """Store uploaded file and synchronously produce a usable attachment."""
    app_config = get_config()
    content, digest = await _read_file_and_hash(file)
    safe_filename = file.filename or ""
    suffix = Path(safe_filename).suffix.lower()
    need_extract = suffix in PARSE_REQUIRED_EXTENSIONS
    async with session_factory() as session:
        existing = await session.execute(select(Attachment).where(Attachment.hash == digest).limit(1))
        existing_attachment = existing.scalar_one_or_none()
        if existing_attachment:
            log.info(
                "Found existing attachment with id %s, reusing processing result.",
                existing_attachment.id,
            )
            existing_path = Path(existing_attachment.path)
            normalized_path = _relative_storage_path(existing_path)
            if normalized_path != existing_path:
                existing_attachment.path = str(normalized_path)
                await session.commit()
            if existing_attachment.status == "completed":
                mime_type, _ = mimetypes.guess_type(existing_attachment.path)
                return existing_attachment.id, mime_type
        else:
            attachment_id = str(uuid.uuid4())
            log.info("Creating new attachment for file: %s", file.filename)
            source_file = await _persist_uploaded_file(content, attachment_id, file.filename, app_config)

            attachment = Attachment(
                id=attachment_id,
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
        source_file = Path(existing_attachment.path)
        if not source_file.exists():
            source_file = await _persist_uploaded_file(content, existing_attachment.id, file.filename, app_config)
            async with session_factory() as session:
                db_attachment = await session.get(Attachment, existing_attachment.id)
                if not db_attachment:
                    raise FileProcessError(f"Attachment not found before retry: {existing_attachment.id}")
                db_attachment.path = str(source_file)
                db_attachment.status = "created"
                db_attachment.mineru_id = None
                await session.commit()
        else:
            async with session_factory() as session:
                db_attachment = await session.get(Attachment, existing_attachment.id)
                if not db_attachment:
                    raise FileProcessError(f"Attachment not found before retry: {existing_attachment.id}")
                normalized_path = _relative_storage_path(source_file)
                if normalized_path != source_file:
                    db_attachment.path = str(normalized_path)
                db_attachment.status = "created"
                db_attachment.mineru_id = None
                await session.commit()

        page_ranges: list[str] | None = None
        if source_file.suffix.lower() == ".pdf":
            total_pages = await _get_pdf_total_pages(source_file)
            if total_pages > PDF_SEGMENT_PAGE_LIMIT:
                page_ranges = _build_pdf_page_ranges(total_pages)

        await _cleanup_processing_artifacts(source_file, keep_markdown=False)
        await _request_mineru_parse(
            existing_attachment.id,
            source_file,
            session_factory,
            app_config=app_config,
            page_ranges=page_ranges,
        )
        try:
            await extract_attachment(existing_attachment.id, session_factory, app_config=app_config)
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


async def extract_attachment(
    file_id: str,
    session_factory: async_sessionmaker,
    *,
    app_config: AppConfig | None = None,
):
    """Poll and download markdown result for an attachment that has already submitted a parse task."""
    app_config = app_config if app_config is not None else get_config()

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

        mineru_id = attachment.mineru_id
        source_file = Path(attachment.path)

    log.info("Extracting attachment %s with MinerU task %s", file_id, mineru_id)
    markdown_file = source_file.with_suffix(".md")
    segmented_tasks = _parse_mineru_segment_tasks(mineru_id)
    try:
        mineru_config = require_mineru_config(get_config_path(app_config, "file.mineru"))
    except ConfigMissingError as exc:
        raise FileProcessError(str(exc)) from exc
    base_url = mineru_config.base_url
    api_key = mineru_config.api_key
    timeout = aiohttp.ClientTimeout(total=120)
    await _cleanup_processing_artifacts(source_file, keep_markdown=False)

    try:
        async with aiohttp.ClientSession(headers=_make_headers(api_key), timeout=timeout) as csession:
            if segmented_tasks:
                markdown_content = await _download_segmented_markdown(
                    csession,
                    base_url,
                    segmented_tasks,
                )
            else:
                markdown_url = await _poll_markdown_url(
                    csession,
                    base_url,
                    mineru_id,
                )
                markdown_content = await _download_markdown(csession, markdown_url)

        markdown_file.parent.mkdir(parents=True, exist_ok=True)
        await _write_markdown_atomically(markdown_file, markdown_content)

        normalized_path = _relative_storage_path(source_file)
        async with session_factory() as session:
            existing = await session.execute(select(Attachment).where(Attachment.id == file_id).limit(1))
            attachment = existing.scalar_one_or_none()
            if not attachment:
                raise FileProcessError(f"Attachment with id {file_id} not found during finalize")
            if normalized_path != source_file:
                attachment.path = str(normalized_path)
            attachment.status = "completed"
            await session.commit()

        await _cleanup_processing_artifacts(source_file, keep_markdown=True)
    except Exception as exc:
        await _cleanup_processing_artifacts(source_file, keep_markdown=False)
        async with session_factory() as session:
            existing = await session.execute(select(Attachment).where(Attachment.id == file_id).limit(1))
            attachment = existing.scalar_one_or_none()
            if attachment:
                attachment.status = "failed"
                await session.commit()

        if isinstance(exc, FileProcessError):
            raise
        raise FileProcessError(str(exc)) from exc
