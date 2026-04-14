from __future__ import annotations

import asyncio
import time
from pathlib import Path

import aiohttp
import requests


class MineruError(RuntimeError):
    """Raised when MinerU conversion fails."""

    def __init__(
        self,
        message: str,
        *,
        err_code: int | None = None,
        err_msg: str | None = None,
    ) -> None:
        super().__init__(message)
        self.err_code = err_code
        self.err_msg = err_msg


def _make_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def _submit_task(
    session: aiohttp.ClientSession,
    base_url: str,
    source_file: Path,
    language: str = "ch",
    page_range: str | None = None,
) -> tuple[str, str]:
    payload = {"file_name": source_file.name, "language": language}
    if page_range:
        payload["page_range"] = page_range
    async with session.post(f"{base_url}/parse/file", json=payload) as resp:
        result = await resp.json()

    if result.get("code") != 0:
        msg = str(result.get("msg", "unknown error"))
        raise MineruError(
            f"MinerU submit failed: {msg}",
            err_msg=msg,
        )

    data = result.get("data") or {}
    task_id = data.get("task_id")
    file_url = data.get("file_url")
    if not task_id or not file_url:
        raise MineruError("MinerU submit succeeded but missing task_id or file_url")

    return str(task_id), str(file_url)


async def _upload_file_to_signed_url(file_url: str, source_file: Path) -> None:
    # Keep upload behavior consistent with prior implementation: signed OSS URL may reject
    # aiohttp-added headers, so upload via requests in a worker thread.
    def _sync_put() -> requests.Response:
        with open(source_file, "rb") as f:
            return requests.put(file_url, data=f, timeout=120)

    resp = await asyncio.to_thread(_sync_put)
    if resp.status_code not in (200, 201):
        raise MineruError(
            f"MinerU file upload failed with HTTP {resp.status_code}: {resp.text[:200]}"
        )


async def _poll_markdown_url(
    session: aiohttp.ClientSession,
    base_url: str,
    task_id: str,
    poll_interval: float = 4.0,
    poll_timeout: float = 300.0,
) -> str:
    started = time.time()
    while time.time() - started < poll_timeout:
        async with session.get(f"{base_url}/parse/{task_id}") as resp:
            result = await resp.json()

        data = result.get("data") or {}
        state = data.get("state")
        if state == "done":
            markdown_url = data.get("markdown_url")
            if not markdown_url:
                raise MineruError("MinerU returned done state without markdown_url")
            return str(markdown_url)

        if state == "failed":
            err_msg_raw = data.get("err_msg", "unknown error")
            err_msg = str(err_msg_raw)
            err_code_raw = data.get("err_code")
            err_code = err_code_raw if isinstance(err_code_raw, int) else None
            code_text = f" ({err_code})" if err_code is not None else ""
            raise MineruError(
                f"MinerU task failed{code_text}: {err_msg}",
                err_code=err_code,
                err_msg=err_msg,
            )

        await asyncio.sleep(poll_interval)

    raise MineruError(f"MinerU polling timed out after {poll_timeout}s")


async def _download_markdown(session: aiohttp.ClientSession, markdown_url: str) -> str:
    async with session.get(markdown_url) as resp:
        resp.raise_for_status()
        return await resp.text(encoding="utf-8")


async def convert_file_to_markdown(
    source_file: Path,
    markdown_file: Path,
    *,
    base_url: str,
    api_key: str,
    language: str = "ch",
    poll_interval: float = 4.0,
    poll_timeout: float = 300.0,
) -> Path:
    """Convert a local file to markdown via MinerU and save it next to source file."""
    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")

    headers = _make_headers(api_key)
    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        task_id, file_url = await _submit_task(session, base_url, source_file, language)
        print(f"Submitted MinerU task {task_id}, uploading file to {file_url}...")
        await _upload_file_to_signed_url(file_url, source_file)
        markdown_url = await _poll_markdown_url(
            session,
            base_url,
            task_id,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
        )
        markdown_content = await _download_markdown(session, markdown_url)

    markdown_file.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(markdown_file.write_text, markdown_content, "utf-8")
    return markdown_file
