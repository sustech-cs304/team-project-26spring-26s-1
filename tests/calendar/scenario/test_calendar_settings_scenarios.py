from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import agent.api.school_settings as school_settings_api
from agent.api.routine_events import router as routine_events_router
from agent.api.school_settings import router as school_settings_router


pytestmark = pytest.mark.scenario


def test_calendar_event_source_lifecycle_with_alias_queries(app_factory, sqlite_session_factory):
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.include_router(routine_events_router, prefix="/api")
    client = TestClient(app)

    created = client.post(
        "/api/events/create",
        json=[
            {
                "title": "Scenario Lecture",
                "description": "Software engineering workshop",
                "start_time": 100,
                "end_time": 200,
                "inform_type": "5_minutes_before",
            },
            {
                "title": "Unrelated",
                "description": "different event",
                "start_time": 300,
                "end_time": 400,
            },
        ],
    )
    source = client.get("/api/events/sources").json()[0]
    patched_source = client.patch(
        f"/api/events/sources/{source['id']}",
        json={"color": "#00ff00", "is_visible": False},
    )
    queried = client.get(
        "/api/events",
        params={"startTime": 0, "endTime": 250, "keyWord": "workshop", "source": "user"},
    )
    event_id = queried.json()["data"][0]["id"]
    updated = client.put(
        "/api/events/modify",
        json=[{"id": event_id, "title": "Scenario Lecture Updated", "inform_type": "none"}],
    )
    by_id = client.get("/api/events", params={"id": event_id})
    deleted = client.request("DELETE", "/api/events/delete", json=[event_id])

    assert created.status_code == 200
    assert len(created.json()["ids"]) == 2
    assert patched_source.status_code == 200
    assert patched_source.json()["color"] == "#00ff00"
    assert patched_source.json()["is_visible"] is False
    assert queried.status_code == 200
    assert len(queried.json()["data"]) == 1
    assert queried.json()["data"][0]["title"] == "Scenario Lecture"
    assert queried.json()["data"][0]["color"] is None
    assert queried.json()["data"][0]["source"]["color"] == "#00ff00"
    assert queried.json()["data"][0]["inform_type"] == "5_minutes_before"
    assert updated.status_code == 200
    assert by_id.json()["data"][0]["title"] == "Scenario Lecture Updated"
    assert by_id.json()["data"][0]["inform_type"] == "none"
    assert deleted.status_code == 200


def test_school_credentials_are_shared_between_tis_and_bb_and_never_return_password(
    app_factory,
    sqlite_session_factory,
    monkeypatch,
):
    stored: dict[str, str] = {}
    refresh_calls: list[tuple] = []

    async def fake_get_status():
        return {
            "runtime_configured": False,
            "student_id": stored.get("student_id"),
            "password_set": bool(stored.get("password")),
        }

    async def fake_set(student_id, password):
        stored["student_id"] = student_id.strip()
        stored["password"] = password

    async def fake_clear():
        stored.clear()

    async def fake_patch_school_cas_config(student_id=None, password=None):
        if student_id is not None:
            stored["student_id"] = student_id.strip()
        if password is not None:
            stored["password"] = password
        return "database"

    async def fake_refresh(session_factory, sources):
        refresh_calls.append(tuple(sources))

    monkeypatch.setattr(school_settings_api.school_credentials, "get_school_cas_credentials_status", fake_get_status)
    monkeypatch.setattr(school_settings_api.school_credentials, "set_school_cas_credentials", fake_set)
    monkeypatch.setattr(school_settings_api.school_credentials, "clear_school_cas_credentials", fake_clear)
    monkeypatch.setattr(school_settings_api.school_credentials, "patch_school_cas_config", fake_patch_school_cas_config)
    monkeypatch.setattr(school_settings_api, "_sync_calendar_sources_once", fake_refresh)

    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.include_router(school_settings_router, prefix="/api")
    client = TestClient(app)

    initial_tis = client.get("/api/settings/tis/credentials")
    saved_bb = client.put("/api/settings/bb/credentials", json={"student_id": " 12345678 ", "password": "secret"})
    tis_after_bb = client.get("/api/settings/tis/credentials")
    patched = client.patch("/api/patch_cas", json={"id": "87654321"})
    bb_after_patch = client.get("/api/settings/bb/credentials")
    deleted_tis = client.delete("/api/settings/tis/credentials")
    bb_after_delete = client.get("/api/settings/bb/credentials")

    assert initial_tis.status_code == 200
    assert initial_tis.json()["password_set"] is False
    assert saved_bb.status_code == 200
    assert saved_bb.json()["student_id"] == "12345678"
    assert "password" not in saved_bb.text.lower()
    assert tis_after_bb.json() == {
        "runtime_configured": False,
        "student_id": "12345678",
        "password_set": True,
    }
    assert patched.status_code == 200
    assert bb_after_patch.json()["student_id"] == "87654321"
    assert bb_after_patch.json()["password_set"] is True
    assert deleted_tis.status_code == 200
    assert bb_after_delete.json()["password_set"] is False
    assert refresh_calls
