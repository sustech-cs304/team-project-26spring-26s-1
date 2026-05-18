from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Form, HTTPException
from langchain.messages import HumanMessage

from agent.config import get_config, get_config_path, require_llm_endpoint_config
from agent.services.profile_store import get_profile_store
from agent.utils.model import build_model

router = APIRouter(tags=["profile"])
log = logging.getLogger(__name__)

DRAFT_NAMESPACE = ("draft",)
CORE_MEMORY_NAMESPACE = ("core_memory",)
DRAFT_LIMIT = 1000
MODEL_RETRY_DELAY_SECONDS = 5
MODEL_CONFIG_PATHS = ("api.agent", "api.utility")

_profile_update_lock = asyncio.Lock()


@router.post("/profile/write")
async def write_profile(content: str = Form(...)) -> dict:
    store = get_profile_store()
    await store.aput(
        DRAFT_NAMESPACE,
        key=str(uuid4()),
        value={
            "data": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {}


@router.post("/profile/update")
async def update_profile() -> dict:
    async with _profile_update_lock:
        store = get_profile_store()
        draft_entries = await store.asearch(DRAFT_NAMESPACE, limit=DRAFT_LIMIT)
        drafts = [
            (entry.key, text)
            for entry in draft_entries
            if (text := _draft_entry_text(entry.value))
        ]
        if not drafts:
            return {}

        items = await _extract_profile_items_with_available_model(drafts)
        for item in items:
            await store.aput(
                CORE_MEMORY_NAMESPACE,
                key=item["key"],
                value={"data": item["value"]},
            )

        for key, _ in drafts:
            await store.adelete(DRAFT_NAMESPACE, key)

    return {}


def _draft_entry_text(value: Any) -> str:
    if isinstance(value, dict):
        raw = value.get("data")
    else:
        raw = value
    if raw is None:
        return ""
    return str(raw).strip()


async def _extract_profile_items_with_available_model(
    drafts: list[tuple[str, str]],
) -> list[dict[str, str]]:
    while True:
        for config_path in MODEL_CONFIG_PATHS:
            items = await _try_extract_profile_items(config_path, drafts)
            if items is not None:
                return items
        await asyncio.sleep(MODEL_RETRY_DELAY_SECONDS)


async def _try_extract_profile_items(
    config_path: str,
    drafts: list[tuple[str, str]],
) -> list[dict[str, str]] | None:
    try:
        endpoint = require_llm_endpoint_config(
            get_config_path(get_config(), config_path),
            config_path,
        )
        model = build_model(endpoint)
        response = await model.ainvoke([HumanMessage(content=_build_extraction_prompt(drafts))])
        return _parse_profile_items(_message_content_text(getattr(response, "content", "")))
    except HTTPException:
        raise
    except Exception as exc:
        log.info("Profile update model unavailable: %s: %s", config_path, exc)
        return None


def _build_extraction_prompt(drafts: list[tuple[str, str]]) -> str:
    draft_text = "\n\n".join(
        f"Draft {index} ({key}):\n{text}"
        for index, (key, text) in enumerate(drafts, start=1)
    )
    return (
        "Extract stable, user-provided profile facts from the draft text below and convert "
        "them into core memory entries.\n"
        "Only use facts explicitly stated by the user. Do not infer, embellish, or include "
        "temporary instructions.\n"
        "Return JSON only, with this exact shape:\n"
        '{"items":[{"key":"user_identity","value":"The user is Tom."}]}\n'
        'If there are no stable facts, return {"items":[]}.\n\n'
        f"{draft_text}"
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
