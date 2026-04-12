from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

import aiohttp
from langchain.tools import tool

from agent.config import get_config


async def _post_json(base_url: str, path: str, api_key: str, payload: dict[str, Any], timeout_ms: int) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=max(timeout_ms, 1) / 1000)
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    endpoint = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(endpoint, json=payload, headers=headers) as response:
            text = await response.text()
            try:
                body = json.loads(text) if text else {}
            except json.JSONDecodeError:
                body = {"detail": text or "non-json response"}

            if response.status >= 400:
                detail = body.get("detail", text or "request failed")
                raise RuntimeError(
                    f"HTTP {response.status} from {endpoint}: {detail}")

            if not isinstance(body, dict):
                raise RuntimeError(
                    f"Invalid response from {endpoint}: expected object")

            return body


def _fallback_payload(tool_name: str, reason: str, query: str | None = None, url: str | None = None) -> str:
    payload: dict[str, Any] = {
        "ok": False,
        "fallback": True,
        "tool": tool_name,
        "error": reason,
    }
    if query is not None:
        payload["query"] = query
        payload["results"] = []
    if url is not None:
        payload["url"] = url
        payload["clean_markdown"] = ""
    return json.dumps(payload, ensure_ascii=False)


@tool
async def webfetch(
    url: str,
    stealth: bool = False,
    wait_ms: int = 3000,
    country_code: str | None = None,
) -> str:
    """Fetch and clean a single webpage through the configured WebFetch API.

    Use this when you already know the target URL and need page content for
    summarization, extraction, or citation.

    Args:
        url: Target page URL. Must be a fully qualified HTTP/HTTPS URL.
        stealth: Whether to enable stealth mode for anti-bot sensitive pages.
            Defaults to False.
        wait_ms: Extra wait time in milliseconds before extraction.
            Increase this for JS-heavy pages. Defaults to 3000.
        country_code: Optional country code (for example: "us", "sg", "jp")
            to influence regional rendering/egress.

    Returns:
        A JSON string converted from response ``data``. It usually includes
        upstream fields plus ``clean_markdown`` when available.

    Notes:
        If the upstream service is unavailable or returns an error, this tool
        returns a fallback JSON payload with ``fallback=true`` instead of
        raising an exception.
    """
    payload: dict[str, Any] = {
        "url": url,
        "stealth": stealth,
        "wait_ms": wait_ms,
    }
    if country_code:
        payload["country_code"] = country_code

    try:
        wf = get_config().webfetch
        response = await _post_json(
            base_url=wf.base_url,
            path=wf.path,
            api_key=wf.api_key,
            payload=payload,
            timeout_ms=wf.timeout_ms,
        )
        return json.dumps(response.get("data", response), ensure_ascii=False)
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, RuntimeError) as exc:
        return _fallback_payload("webfetch", str(exc), url=url)


@tool
async def websearch(
    q: str,
    search_type: Literal[
        "search",
        "images",
        "news",
        "videos",
        "places",
        "shopping",
        "scholar",
    ] = "search",
    num: int = 10,
    gl: str = "us",
    hl: str = "en",
) -> str:
    """Run a web search through the configured WebSearch API.

    Use this when you need discovery (find sources first), then optionally call
    ``webfetch`` on selected result URLs for deeper content extraction.

    Args:
        q: Search query text.
        search_type: Search vertical. Supported values are ``search``,
            ``images``, ``news``, ``videos``, ``places``, ``shopping``,
            ``scholar``. Defaults to ``search``.
        num: Desired result count. Defaults to 10.
        gl: Country/region hint (for example: ``us``, ``sg``, ``jp``).
            Defaults to ``us``.
        hl: Language hint (for example: ``en``, ``zh-cn``).
            Defaults to ``en``.

    Returns:
        A JSON string converted from response ``data`` with upstream search
        fields (for example organic results, news blocks, or image results,
        depending on ``search_type``).

    Notes:
        If the upstream service is unavailable or returns an error, this tool
        returns a fallback JSON payload with ``fallback=true`` instead of
        raising an exception.
    """
    payload = {
        "q": q,
        "search_type": search_type,
        "num": num,
        "gl": gl,
        "hl": hl,
    }

    try:
        ws = get_config().websearch
        response = await _post_json(
            base_url=ws.base_url,
            path=ws.path,
            api_key=ws.api_key,
            payload=payload,
            timeout_ms=ws.timeout_ms,
        )
        return json.dumps(response.get("data", response), ensure_ascii=False)
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, RuntimeError) as exc:
        return _fallback_payload("websearch", str(exc), query=q)
