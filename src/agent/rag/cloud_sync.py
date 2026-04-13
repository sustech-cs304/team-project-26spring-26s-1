from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import aiohttp

from agent.config import get_config
from agent.rag.restore import load_embedding_array, restore_from_embedding_array


STORE_DB_PATH = Path("agent_store.db")


@dataclass(slots=True)
class RagCloudSyncStatus:
    status: str = "idle"
    stage: str = "idle"
    progress: int = 0
    message: str = "No sync has been started."
    knowledge_base_id: str = "default"
    version: str | None = None
    downloaded_files: list[str] | None = None
    embedded_added: int = 0
    embedded_overwritten: int = 0
    embedded_failed: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "knowledge_base_id": self.knowledge_base_id,
            "version": self.version,
            "downloaded_files": self.downloaded_files or [],
            "embedded_added": self.embedded_added,
            "embedded_overwritten": self.embedded_overwritten,
            "embedded_failed": self.embedded_failed,
            "error": self.error,
        }


class RagCloudSyncService:
    def __init__(self):
        self._config = get_config()
        self._status = RagCloudSyncStatus()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None

    def get_status(self) -> dict[str, Any]:
        return self._status.to_dict()

    async def trigger_sync(self) -> dict[str, Any]:
        async with self._lock:
            if self._task and not self._task.done():
                return self._status.to_dict()

            self._status = RagCloudSyncStatus(
                status="running",
                stage="manifest",
                progress=5,
                message="Fetching cloud manifest.",
            )
            self._task = asyncio.create_task(self._run_sync())
            return self._status.to_dict()

    async def _run_sync(self) -> None:
        try:
            manifest = await self._fetch_manifest()
            knowledge_base_id = str(manifest.get("knowledge_base_id") or "default")
            version = str(manifest.get("version") or "unknown")
            files = manifest.get("files")
            if not isinstance(files, list) or not files:
                raise ValueError("Manifest must contain a non-empty 'files' list.")

            self._status = RagCloudSyncStatus(
                status="running",
                stage="download",
                progress=20,
                message="Downloading embedding files.",
                knowledge_base_id=knowledge_base_id,
                version=version,
            )

            cache_dir = self._prepare_cache_dir(knowledge_base_id, version)
            downloaded_files = await self._download_manifest_files(files, cache_dir)

            self._status.downloaded_files = [str(path) for path in downloaded_files]
            self._status.progress = 70
            self._status.stage = "import"
            self._status.message = "Importing embeddings into agent_store.db."

            stats = await self._import_downloaded_files(downloaded_files)

            self._status.status = "success"
            self._status.stage = "completed"
            self._status.progress = 100
            self._status.message = "Knowledge base sync completed."
            self._status.embedded_added = stats.added
            self._status.embedded_overwritten = stats.overwritten
            self._status.embedded_failed = stats.failed

            for file_path in downloaded_files:
                if file_path.exists():
                    file_path.unlink()
            if cache_dir.exists() and not any(cache_dir.iterdir()):
                cache_dir.rmdir()
        except Exception as exc:
            self._status.status = "failed"
            self._status.stage = "failed"
            self._status.progress = min(self._status.progress, 95)
            self._status.message = "Knowledge base sync failed."
            self._status.error = str(exc)

    async def _fetch_manifest(self) -> dict[str, Any]:
        cloud_config = self._config.rag_cloud
        if not cloud_config.base_url.strip():
            raise ValueError("rag_cloud.base_url is not configured.")

        endpoint = urljoin(cloud_config.base_url.rstrip("/") + "/", cloud_config.manifest_path.lstrip("/"))
        timeout = aiohttp.ClientTimeout(total=max(cloud_config.timeout_ms, 1000) / 1000)
        headers = {}
        if cloud_config.api_key:
            headers["Authorization"] = f"Bearer {cloud_config.api_key}"

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(endpoint) as response:
                body = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"Manifest request failed: status={response.status}, body={body[:300]}")
                try:
                    data = json.loads(body)
                except json.JSONDecodeError as exc:
                    raise ValueError("Manifest response is not valid JSON.") from exc

        if not isinstance(data, dict):
            raise ValueError("Manifest response must be a JSON object.")
        return data

    def _prepare_cache_dir(self, knowledge_base_id: str, version: str) -> Path:
        cache_dir = (
            Path(self._config.file.rag_path)
            / "embeddings"
            / "cloud-cache"
            / knowledge_base_id
            / version
        )
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    async def _download_manifest_files(self, files: list[Any], cache_dir: Path) -> list[Path]:
        downloaded: list[Path] = []
        cloud_config = self._config.rag_cloud
        timeout = aiohttp.ClientTimeout(total=max(cloud_config.timeout_ms, 1000) / 1000)
        headers = {}
        if cloud_config.api_key:
            headers["Authorization"] = f"Bearer {cloud_config.api_key}"

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for index, file_info in enumerate(files, start=1):
                if not isinstance(file_info, dict):
                    raise ValueError("Each manifest file entry must be an object.")
                name = Path(str(file_info.get("name") or "")).name
                url = str(file_info.get("url") or "").strip()
                if not name or not url:
                    raise ValueError("Each manifest file entry must include 'name' and 'url'.")
                target_url = urljoin(cloud_config.base_url.rstrip("/") + "/", url.lstrip("/"))
                target_path = cache_dir / name
                async with session.get(target_url) as response:
                    content = await response.read()
                    if response.status >= 400:
                        raise RuntimeError(f"Download failed for {name}: status={response.status}")
                target_path.write_bytes(content)
                downloaded.append(target_path)

                self._status.progress = min(20 + int(50 * index / len(files)), 69)
                self._status.message = f"Downloaded {index}/{len(files)} embedding files."

        return downloaded

    async def _import_downloaded_files(self, downloaded_files: list[Path]):
        embedding_items: list[dict[str, Any]] = []
        overwrite_sources: set[str] = set()

        for file_path in downloaded_files:
            items = load_embedding_array(file_path)
            embedding_items.extend(items)
            overwrite_sources.update(
                str(item.get("source_file") or "").strip()
                for item in items
                if str(item.get("source_file") or "").strip()
            )

        if not embedding_items:
            raise ValueError("Downloaded embedding files are empty.")
        if not overwrite_sources:
            raise ValueError("Downloaded embedding files do not include any source_file values.")

        return await restore_from_embedding_array(
            config=self._config,
            embedding_items=embedding_items,
            store_db=STORE_DB_PATH,
            overwrite_sources=overwrite_sources,
        )

