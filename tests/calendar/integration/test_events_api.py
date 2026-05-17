from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import agent.api.routine_events as routine_events_api
from agent.api.routine_events import router as routine_events_router


pytestmark = pytest.mark.integration


def test_routine_events_api_create_query_update_and_delete(app_factory, sqlite_session_factory):
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.include_router(routine_events_router, prefix="/api")
    client = TestClient(app)

    invalid = client.post(
        "/api/events/create",
        json=[{"title": "bad", "start_time": 200, "end_time": 100}],
    )
    created = client.post(
        "/api/events/create",
        json=[
            {
                "title": "Software Engineering",
                "description": "Project meeting",
                "start_time": 100,
                "end_time": 200,
                "color": "#123456",
                "inform_type": "10_minutes_before",
            }
        ],
    )

    event_id = created.json()["ids"][0]
    queried = client.get("/api/events", params={"start_time": 0, "end_time": 300})
    sources = client.get("/api/events/sources")
    updated = client.put(
        "/api/events/modify",
        json=[{"id": event_id, "title": "Renamed", "color": "#abcdef"}],
    )
    by_id = client.get("/api/events", params={"id": event_id})
    deleted = client.request("DELETE", "/api/events/delete", json=[event_id])
    missing = client.get("/api/events", params={"id": event_id})

    assert invalid.status_code == 400
    assert created.status_code == 200
    assert queried.status_code == 200
    assert queried.json()["data"][0]["title"] == "Software Engineering"
    assert queried.json()["data"][0]["color"] == "#123456"
    assert queried.json()["data"][0]["inform_type"] == "10_minutes_before"
    assert sources.status_code == 200
    assert sources.json()[0]["title"] == "user"
    assert updated.status_code == 200
    assert by_id.json()["data"][0]["title"] == "Renamed"
    assert by_id.json()["data"][0]["color"] == "#abcdef"
    assert deleted.status_code == 200
    assert missing.status_code == 400


def test_routine_source_update_and_sync_entrypoints(
    app_factory,
    sqlite_session_factory,
    monkeypatch,
):
    async def fake_sync_managed_source(source_id, db):
        return {"message": "Routine updated", "ids": [101], "source": source_id}

    monkeypatch.setattr(routine_events_api, "sync_managed_source", fake_sync_managed_source)

    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.include_router(routine_events_router, prefix="/api")
    client = TestClient(app)

    created = client.post(
        "/api/events/create",
        json=[{"title": "Source test", "start_time": 100, "end_time": 200}],
    )
    assert created.status_code == 200
    source_id = client.get("/api/events/sources").json()[0]["id"]

    patched = client.patch(
        f"/api/events/sources/{source_id}",
        json={"color": "#abcdef", "is_visible": False},
    )
    bad_color = client.patch(
        f"/api/events/sources/{source_id}",
        json={"color": "javascript:alert(1)"},
    )
    missing_source = client.patch(
        "/api/events/sources/999999",
        json={"color": "#abcdef"},
    )
    managed_sync = client.patch("/api/events/update/bb")
    missing_sync = client.patch("/api/events/update/not-a-source")

    assert patched.status_code == 200
    assert patched.json()["color"] == "#abcdef"
    assert patched.json()["is_visible"] is False
    assert bad_color.status_code == 400
    assert missing_source.status_code == 404
    assert managed_sync.status_code == 200
    assert managed_sync.json()["source"] == "bb"
    assert missing_sync.status_code == 404
