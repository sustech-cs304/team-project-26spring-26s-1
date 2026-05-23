from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from langgraph.store.base import BaseStore
from langchain.messages import HumanMessage

from agent.config import get_config, get_config_path, require_llm_endpoint_config
from agent.utils.model import build_model

router = APIRouter(tags=["profile"])
log = logging.getLogger(__name__)

CORE_MEMORY_NAMESPACE = ("core_memory",)
PROFILE_RAW_KEY = "profile_raw"
MODEL_CONFIG_PATHS = ("api.agent", "api.utility")

_profile_update_lock = asyncio.Lock()


@router.post("/profile/write")
async def write_profile(request: Request, content: str = Form(...)) -> dict:
    store = _get_profile_store(request)
    await store.aput(
        CORE_MEMORY_NAMESPACE,
        key=PROFILE_RAW_KEY,
        value={"data": content},
    )
    return {}


@router.post("/profile/update")
async def update_profile(request: Request) -> dict:
    async with _profile_update_lock:
        store = _get_profile_store(request)
        raw_entry = await store.aget(CORE_MEMORY_NAMESPACE, PROFILE_RAW_KEY)
        if raw_entry is None:
            return {}

        profile_raw = _core_memory_entry_text(raw_entry.value)
        if not profile_raw:
            return {}

        items = await _extract_profile_items_once([(PROFILE_RAW_KEY, profile_raw)])
        if items is None:
            return {}

        for item in items:
            await store.aput(
                CORE_MEMORY_NAMESPACE,
                key=item["key"],
                value={"data": item["value"]},
            )

        await store.adelete(CORE_MEMORY_NAMESPACE, PROFILE_RAW_KEY)

    return {}


def _get_profile_store(request: Request) -> BaseStore:
    store = getattr(request.app.state, "agent_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Profile store is not initialized")
    return store


def _core_memory_entry_text(value: Any) -> str:
    if isinstance(value, dict):
        raw = value.get("data")
    else:
        raw = value
    if raw is None:
        return ""
    return str(raw).strip()


async def _extract_profile_items_once(
    raw_profiles: list[tuple[str, str]],
) -> list[dict[str, str]] | None:
    for config_path in MODEL_CONFIG_PATHS:
        items = await _try_extract_profile_items(config_path, raw_profiles)
        if items is not None:
            return items
    return None


async def _try_extract_profile_items(
    config_path: str,
    raw_profiles: list[tuple[str, str]],
) -> list[dict[str, str]] | None:
    try:
        endpoint = require_llm_endpoint_config(
            get_config_path(get_config(), config_path),
            config_path,
        )
        model = build_model(endpoint)
        response = await model.ainvoke([HumanMessage(content=_build_extraction_prompt(raw_profiles))])
        return _parse_profile_items(_message_content_text(getattr(response, "content", "")))
    except Exception as exc:
        log.info("Profile update model failed: %s: %s", config_path, exc)
        return None


def _build_extraction_prompt(raw_profiles: list[tuple[str, str]]) -> str:
    raw_profile_text = "\n\n".join(
        f"Raw profile {index} ({key}):\n{text}"
        for index, (key, text) in enumerate(raw_profiles, start=1)
    )
    return (
        "Extract stable, user-provided profile facts from the raw profile text below and convert "
        "them into core memory entries.\n"
        "Only use facts explicitly stated by the user. Do not infer, embellish, or include "
        "temporary instructions.\n"
        "Return JSON only, with this exact shape:\n"
        '{"items":[{"key":"user_identity","value":"The user is Tom."}]}\n'
        'If there are no stable facts, return {"items":[]}.\n\n'
        f"{raw_profile_text}"
    )


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return str(content).strip()

    parts: list[str] = []
    for chunk in content:
        if isinstance(chunk, str):
            parts.append(chunk)
            continue
        if isinstance(chunk, dict):
            text = chunk.get("text")
            if text is not None:
                parts.append(str(text))
    return "".join(parts).strip()


def _parse_profile_items(text: str) -> list[dict[str, str]]:
    payload = _load_json_object(text)
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise HTTPException(status_code=502, detail="Profile extraction response missing items")

    items: list[dict[str, str]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        key = str(raw_item.get("key") or "").strip()
        value = str(raw_item.get("value") or "").strip()
        if key and value:
            items.append({"key": key, "value": value})
    return items


def _load_json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise HTTPException(status_code=502, detail="Profile extraction response is not JSON")
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="Profile extraction response is not JSON") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Profile extraction response is not an object")
    return payload
