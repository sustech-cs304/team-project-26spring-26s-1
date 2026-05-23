from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agent.api import profile


pytestmark = pytest.mark.api


class FakeStore:
    def __init__(self):
        self.data: dict[tuple[str, ...], dict[str, Any]] = {}

    async def aput(self, namespace: tuple[str, ...], key: str, value: Any):
        self.data.setdefault(namespace, {})[key] = value

    async def aget(self, namespace: tuple[str, ...], key: str):
        value = self.data.get(namespace, {}).get(key)
        if value is None:
            return None
        return SimpleNamespace(key=key, value=value)

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
    app = app_factory()
    app.state.agent_store = store
    app.include_router(profile.router)
    yield TestClient(app), store


def test_profile_write_stores_multipart_content_as_raw_core_memory(profile_client):
    client, store = profile_client

    response = client.post(
        "/profile/write",
        files={"content": (None, "I am Tom.")},
    )

    assert response.status_code == 200
    assert response.json() == {}
    value = store.data[profile.CORE_MEMORY_NAMESPACE][profile.PROFILE_RAW_KEY]
    assert value == {"data": "I am Tom."}


def test_profile_write_rejects_missing_content(profile_client):
    client, _ = profile_client

    response = client.post("/profile/write")

    assert response.status_code == 400


def test_profile_update_returns_empty_when_no_raw_profile(profile_client, monkeypatch):
    client, _ = profile_client

    async def fail_if_called(_raw_profiles):
        raise AssertionError("model extraction should not run without raw profile")

    monkeypatch.setattr(profile, "_extract_profile_items_once", fail_if_called)

    response = client.post("/profile/update")

    assert response.status_code == 200
    assert response.json() == {}


def test_profile_update_writes_core_memory_and_deletes_profile_raw_on_success(profile_client, monkeypatch):
    client, store = profile_client
    store.data[profile.CORE_MEMORY_NAMESPACE] = {
        profile.PROFILE_RAW_KEY: {"data": "I am Tom."},
    }

    async def fake_extract(raw_profiles):
        assert raw_profiles == [(profile.PROFILE_RAW_KEY, "I am Tom.")]
        return [{"key": "user_identity", "value": "The user is Tom."}]

    monkeypatch.setattr(profile, "_extract_profile_items_once", fake_extract)

    response = client.post("/profile/update")

    assert response.status_code == 200
    assert response.json() == {}
    assert store.data[profile.CORE_MEMORY_NAMESPACE]["user_identity"] == {"data": "The user is Tom."}
    assert profile.PROFILE_RAW_KEY not in store.data[profile.CORE_MEMORY_NAMESPACE]


def test_profile_update_preserves_profile_raw_when_extraction_fails(profile_client, monkeypatch):
    client, store = profile_client
    store.data[profile.CORE_MEMORY_NAMESPACE] = {
        profile.PROFILE_RAW_KEY: {"data": "I am Tom."},
    }

    async def fake_extract(_raw_profiles):
        return None

    monkeypatch.setattr(profile, "_extract_profile_items_once", fake_extract)

    response = client.post("/profile/update")

    assert response.status_code == 200
    assert response.json() == {}
    assert store.data[profile.CORE_MEMORY_NAMESPACE][profile.PROFILE_RAW_KEY] == {"data": "I am Tom."}


def test_profile_model_helper_falls_back_to_utility_model(monkeypatch, run_async):
    calls: list[str] = []

    async def fake_try(config_path, _raw_profiles):
        calls.append(config_path)
        if config_path == "api.agent":
            return None
        return [{"key": "user_identity", "value": "The user is Tom."}]

    monkeypatch.setattr(profile, "_try_extract_profile_items", fake_try)

    items = run_async(profile._extract_profile_items_once([(profile.PROFILE_RAW_KEY, "I am Tom.")]))

    assert calls == ["api.agent", "api.utility"]
    assert items == [{"key": "user_identity", "value": "The user is Tom."}]


def test_profile_model_helper_returns_none_when_both_models_are_unavailable(monkeypatch, run_async):
    calls: list[str] = []

    async def fake_try(config_path, _raw_profiles):
        calls.append(config_path)
        return None

    monkeypatch.setattr(profile, "_try_extract_profile_items", fake_try)

    items = run_async(profile._extract_profile_items_once([(profile.PROFILE_RAW_KEY, "I am Tom.")]))

    assert calls == ["api.agent", "api.utility"]
    assert items is None
