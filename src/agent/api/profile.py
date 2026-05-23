from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request
from langgraph.store.base import BaseStore
from langchain.messages import HumanMessage
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import async_sessionmaker

from agent.config import get_config, get_config_path, require_llm_endpoint_config
from agent.db.models import KeyValueStore
from agent.utils.model import build_model

router = APIRouter(tags=["profile"])
log = logging.getLogger(__name__)

CORE_MEMORY_NAMESPACE = ("core_memory",)
PROFILE_DB_KEY = "profile"
PROFILE_FALLBACK_CORE_MEMORY_KEY = "profile"
MODEL_CONFIG_PATHS = ("api.agent", "api.utility")
PROFILE_EXTRACTION_ATTEMPTS = 3

_profile_update_state_lock = asyncio.Lock()
_profile_update_underway = False


class ProfileItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(description="Stable core memory key for the extracted profile fact.")
    value: str = Field(description="Stable user-provided profile fact to store.")


class ProfileExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProfileItem] = Field(
        description="Stable profile facts explicitly stated by the user.",
    )


@router.post("/profile/write")
async def write_profile(request: Request, content: str = Form(...)) -> dict:
    await _upsert_kv_string(_get_session_factory(request), PROFILE_DB_KEY, content)
    return {}


@router.post("/profile/update")
async def update_profile(request: Request, background_tasks: BackgroundTasks) -> dict:
    global _profile_update_underway

    store = _get_profile_store(request)
    session_factory = _get_session_factory(request)

    async with _profile_update_state_lock:
        if _profile_update_underway:
            return {}
        _profile_update_underway = True

    background_tasks.add_task(_update_profile_background, store, session_factory)
    return {}


async def _update_profile_background(
    store: BaseStore,
    session_factory: async_sessionmaker,
) -> None:
    global _profile_update_underway

    try:
        await _delete_core_memory_entry_if_exists(store, PROFILE_FALLBACK_CORE_MEMORY_KEY)

        profile_raw = (await _get_kv_string(session_factory, PROFILE_DB_KEY) or "").strip()
        if not profile_raw:
            return

        items = await _extract_profile_items_with_retries(profile_raw)
        if items is None:
            await store.aput(
                CORE_MEMORY_NAMESPACE,
                key=PROFILE_FALLBACK_CORE_MEMORY_KEY,
                value={"data": profile_raw},
            )
            return

        for item in items:
            await store.aput(
                CORE_MEMORY_NAMESPACE,
                key=item["key"],
                value={"data": item["value"]},
            )
    except Exception:
        log.exception("Profile update background task failed")
    finally:
        async with _profile_update_state_lock:
            _profile_update_underway = False


def _get_profile_store(request: Request) -> BaseStore:
    store = getattr(request.app.state, "agent_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Profile store is not initialized")
    return store


def _get_session_factory(request: Request) -> async_sessionmaker:
    session_factory = getattr(request.app.state, "async_session", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Profile database is not initialized")
    return session_factory


async def _upsert_kv_string(session_factory: async_sessionmaker, key: str, value: str) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    async with session_factory() as session:
        row = await session.get(KeyValueStore, key)
        if row is None:
            session.add(KeyValueStore(key=key, value=value, created_at=now, updated_at=now))
        else:
            row.value = value
            row.updated_at = now
        await session.commit()


async def _get_kv_string(session_factory: async_sessionmaker, key: str) -> str | None:
    async with session_factory() as session:
        row = await session.get(KeyValueStore, key)
        if row is None:
            return None
        return row.value


async def _delete_core_memory_entry_if_exists(store: BaseStore, key: str) -> None:
    if await store.aget(CORE_MEMORY_NAMESPACE, key) is not None:
        await store.adelete(CORE_MEMORY_NAMESPACE, key)


async def _extract_profile_items_with_retries(
    raw_profile: str,
    *,
    attempts: int = PROFILE_EXTRACTION_ATTEMPTS,
) -> list[dict[str, str]] | None:
    for _ in range(attempts):
        items = await _extract_profile_items_once(raw_profile)
        if items is not None:
            return items
    return None


async def _extract_profile_items_once(raw_profile: str) -> list[dict[str, str]] | None:
    for config_path in MODEL_CONFIG_PATHS:
        items = await _try_extract_profile_items(config_path, raw_profile)
        if items is not None:
            return items
    return None


async def _try_extract_profile_items(
    config_path: str,
    raw_profile: str,
) -> list[dict[str, str]] | None:
    try:
        endpoint = require_llm_endpoint_config(
            get_config_path(get_config(), config_path),
            config_path,
        )
        model = build_model(endpoint)
        extractor = model.with_structured_output(ProfileExtraction, method="json_schema")
        response = await extractor.ainvoke([HumanMessage(content=_build_extraction_prompt(raw_profile))])
        return _parse_profile_items(response)
    except Exception as exc:
        log.info("Profile update model failed: %s: %s", config_path, exc)
        return None


def _build_extraction_prompt(raw_profile: str) -> str:
    return (
        "Extract stable, user-provided profile facts from the raw profile text below and convert "
        "them into core memory entries.\n"
        "Only use facts explicitly stated by the user. Do not infer, embellish, or include "
        "temporary instructions.\n"
        "Use an empty items list when there are no stable facts.\n\n"
        f"Raw profile:\n{raw_profile}"
    )


def _parse_profile_items(extraction: Any) -> list[dict[str, str]]:
    profile_extraction = ProfileExtraction.model_validate(extraction)
    items: list[dict[str, str]] = []
    for raw_item in profile_extraction.items:
        key = raw_item.key.strip()
        value = raw_item.value.strip()
        if key and value:
            items.append({"key": key, "value": value})
    return items
