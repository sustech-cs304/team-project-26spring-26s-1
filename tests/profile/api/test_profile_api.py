from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agent.api import profile
from agent.services.profile_store import bind_profile_store, clear_profile_store


pytestmark = pytest.mark.api


class FakeStore:
    def __init__(self):
        self.data: dict[tuple[str, ...], dict[str, Any]] = {}

    async def aput(self, namespace: tuple[str, ...], key: str, value: Any):
        self.data.setdefault(namespace, {})[key] = value

    async def asearch(self, namespace: tuple[str, ...], limit: int = 1000):
        rows = list(self.data.get(namespace, {}).items())[:limit]
        return [
            SimpleNamespace(key=key, value=value)
            for key, value in rows
        ]

    async def adelete(self, namespace: tuple[str, ...], key: str):
        self.data.get(namespace, {}).pop(key, None)


@pytest.fixture
def profile_client(app_factory):
    store = FakeStore()
    bind_profile_store(store)
    app = app_factory()
    app.include_router(profile.router)
    try:
        yield TestClient(app), store
    finally:
        clear_profile_store()


def test_profile_write_stores_multipart_content_in_draft(profile_client):
    client, store = profile_client

    response = client.post(
        "/profile/write",
        files={"content": (None, "I am Tom.")},
    )

    assert response.status_code == 200
    assert response.json() == {}
    draft_rows = store.data[profile.DRAFT_NAMESPACE]
    assert len(draft_rows) == 1
    value = next(iter(draft_rows.values()))
    assert value["data"] == "I am Tom."
    assert value["created_at"]


def test_profile_write_rejects_missing_content(profile_client):
    client, _ = profile_client

    response = client.post("/profile/write")

    assert response.status_code == 400


def test_profile_update_returns_empty_when_no_drafts(profile_client, monkeypatch):
    client, _ = profile_client

    async def fail_if_called(_drafts):
        raise AssertionError("model extraction should not run without drafts")

    monkeypatch.setattr(profile, "_extract_profile_items_with_available_model", fail_if_called)

    response = client.post("/profile/update")

    assert response.status_code == 200
    assert response.json() == {}


def test_profile_update_writes_core_memory_and_deletes_processed_drafts(profile_client, monkeypatch):
    client, store = profile_client
    store.data[profile.DRAFT_NAMESPACE] = {
        "draft-1": {"data": "I am Tom."},
    }

    async def fake_extract(drafts):
        assert drafts == [("draft-1", "I am Tom.")]
        return [{"key": "user_identity", "value": "The user is Tom."}]

    monkeypatch.setattr(profile, "_extract_profile_items_with_available_model", fake_extract)

    response = client.post("/profile/update")

    assert response.status_code == 200
    assert response.json() == {}
    assert store.data[profile.CORE_MEMORY_NAMESPACE]["user_identity"] == {"data": "The user is Tom."}
    assert store.data[profile.DRAFT_NAMESPACE] == {}


def test_profile_model_helper_falls_back_to_utility_model(monkeypatch, run_async):
    calls: list[str] = []

    async def fake_try(config_path, _drafts):
        calls.append(config_path)
        if config_path == "api.agent":
            return None
        return [{"key": "user_identity", "value": "The user is Tom."}]

    monkeypatch.setattr(profile, "_try_extract_profile_items", fake_try)

    items = run_async(profile._extract_profile_items_with_available_model([("draft-1", "I am Tom.")]))

    assert calls == ["api.agent", "api.utility"]
    assert items == [{"key": "user_identity", "value": "The user is Tom."}]


def test_profile_model_helper_blocks_when_both_models_are_unavailable(monkeypatch, run_async):
    class SleepReached(Exception):
        pass

    calls: list[str] = []

    async def fake_try(config_path, _drafts):
        calls.append(config_path)
        return None

    async def fake_sleep(delay):
        assert delay == profile.MODEL_RETRY_DELAY_SECONDS
        raise SleepReached

    monkeypatch.setattr(profile, "_try_extract_profile_items", fake_try)
    monkeypatch.setattr(profile.asyncio, "sleep", fake_sleep)

    with pytest.raises(SleepReached):
        run_async(profile._extract_profile_items_with_available_model([("draft-1", "I am Tom.")]))

    assert calls == ["api.agent", "api.utility"]
