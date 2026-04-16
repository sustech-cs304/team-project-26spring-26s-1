from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

import aiohttp
from fastapi import HTTPException, status

from agent.config import SkillsCloudConfig, get_config


_MAX_ERROR_DETAIL_LEN = 4000


def _try_parse_json(text: str) -> tuple[bool, Any]:
    try:
        return True, json.loads(text)
    except json.JSONDecodeError:
        return False, None


def _extract_error_detail(body_text: str) -> Any:
    if not body_text:
        return "Upstream request failed."

    ok, body = _try_parse_json(body_text)
    if ok:
        if isinstance(body, dict) and "detail" in body:
            return body["detail"]
        return body

    if len(body_text) > _MAX_ERROR_DETAIL_LEN:
        return body_text[:_MAX_ERROR_DETAIL_LEN]
    return body_text


class SkillsHubClient:
    """HTTP client for forwarding Skills Hub cloud API calls."""

    def __init__(self, config_override: SkillsCloudConfig | None = None):
        self._config_override = config_override

    @property
    def delete_submission_path(self) -> str:
        return self._get_config().delete_submission_path

    def _get_config(self) -> SkillsCloudConfig:
        if self._config_override is not None:
            return self._config_override
        return get_config().skills_cloud

    def _build_endpoint(self, path: str) -> str:
        cfg = self._get_config()
        base_url = cfg.base_url.strip()
        if not base_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="skills_cloud.base_url is not configured.",
            )
        return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))

    def _build_timeout(self) -> aiohttp.ClientTimeout:
        timeout_ms = self._get_config().timeout_ms
        return aiohttp.ClientTimeout(total=max(timeout_ms, 1) / 1000)

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        form_data: aiohttp.FormData | None = None,
    ) -> Any:
        endpoint = self._build_endpoint(path)
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with aiohttp.ClientSession(timeout=self._build_timeout()) as session:
            async with session.request(
                method,
                endpoint,
                params=params,
                json=json_body,
                data=form_data,
                headers=headers,
            ) as response:
                payload = await response.read()
                text = payload.decode(response.charset or "utf-8", errors="replace")

                if response.status >= 400:
                    raise HTTPException(
                        status_code=response.status,
                        detail=_extract_error_detail(text),
                    )

                if not text.strip():
                    return {}

                ok, body = _try_parse_json(text)
                if not ok:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Upstream returned non-JSON payload.",
                    )
                return body

    async def request_text(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        endpoint = self._build_endpoint(path)
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with aiohttp.ClientSession(timeout=self._build_timeout()) as session:
            async with session.request(
                method,
                endpoint,
                params=params,
                headers=headers,
            ) as response:
                payload = await response.read()
                text = payload.decode(response.charset or "utf-8", errors="replace")
                if response.status >= 400:
                    raise HTTPException(
                        status_code=response.status,
                        detail=_extract_error_detail(text),
                    )
                return text

    async def post_multipart(
        self,
        path: str,
        *,
        token: str | None,
        fields: dict[str, str] | None,
        files: dict[str, tuple[str, bytes, str]],
    ) -> Any:
        form = aiohttp.FormData()
        if fields:
            for key, value in fields.items():
                form.add_field(key, value)

        for field_name, file_entry in files.items():
            filename, content, content_type = file_entry
            form.add_field(
                field_name,
                content,
                filename=filename,
                content_type=content_type,
            )

        return await self.request_json(
            "POST",
            path,
            token=token,
            form_data=form,
        )
