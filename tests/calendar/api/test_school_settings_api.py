from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import agent.api.school_settings as school_settings_api
from agent.api.school_settings import router as school_settings_router


pytestmark = pytest.mark.api


async def _fake_sync_calendar_sources_once(*_args, **_kwargs):
    return None


def _school_settings_client(app_factory, monkeypatch, *, raise_server_exceptions=True):
    monkeypatch.setattr(school_settings_api, "_sync_calendar_sources_once", _fake_sync_calendar_sources_once)
    app = app_factory()
    app.state.async_session = object()
    app.include_router(school_settings_router, prefix="/api")
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_school_credentials_apis_never_return_password_and_schedule_refresh(
    app_factory,
    monkeypatch,
):
    state = {"student_id": None, "password_set": False}
    calls = []

    async def fake_get_status():
        return {
            "runtime_configured": bool(state["student_id"] and state["password_set"]),
            "student_id": state["student_id"],
            "password_set": state["password_set"],
        }

    async def fake_set(student_id, password):
        state["student_id"] = student_id.strip()
        state["password_set"] = bool(password)
        calls.append(("set", student_id, password))

    async def fake_clear():
        state["student_id"] = None
        state["password_set"] = False
        calls.append(("clear",))

    async def fake_patch(student_id=None, password=None):
        if student_id is not None:
            state["student_id"] = student_id.strip()
        if password is not None:
            state["password_set"] = bool(password)
        if not state["student_id"] or not state["password_set"]:
            raise ValueError("Both id and password are required after patch merge")
        calls.append(("patch", student_id, password))
        return "database"

    monkeypatch.setattr(school_settings_api.school_credentials, "get_school_cas_credentials_status", fake_get_status)
    monkeypatch.setattr(school_settings_api.school_credentials, "set_school_cas_credentials", fake_set)
    monkeypatch.setattr(school_settings_api.school_credentials, "clear_school_cas_credentials", fake_clear)
    monkeypatch.setattr(school_settings_api.school_credentials, "patch_school_cas_config", fake_patch)
    monkeypatch.setattr(school_settings_api, "_sync_calendar_sources_once", _fake_sync_calendar_sources_once)

    app = app_factory()
    app.state.async_session = object()
    app.include_router(school_settings_router, prefix="/api")
    client = TestClient(app)

    tis_put = client.put(
        "/api/settings/tis/credentials",
        json={"student_id": " 12345678 ", "password": "secret"},
    )
    tis_get = client.get("/api/settings/tis/credentials")
    bb_get = client.get("/api/settings/bb/credentials")
    patch = client.patch("/api/patch_cas", json={"id": "87654321"})
    bb_put = client.put(
        "/api/settings/bb/credentials",
        json={"student_id": " 99999999 ", "password": "bb-secret"},
    )
    tis_delete = client.delete("/api/settings/tis/credentials")
    bad_patch = client.patch("/api/patch_cas", json={"id": ""})
    bb_delete = client.delete("/api/settings/bb/credentials")

    assert tis_put.status_code == 200
    assert tis_put.json()["student_id"] == "12345678"
    assert "secret" not in tis_get.text
    assert tis_get.json() == {
        "runtime_configured": True,
        "student_id": "12345678",
        "password_set": True,
    }
    assert bb_get.json()["password_set"] is True
    assert patch.status_code == 200
    assert "successfully" in patch.json()["message"]
    assert bb_put.status_code == 200
    assert bb_put.json()["student_id"] == "99999999"
    assert "bb-secret" not in bb_put.text
    assert tis_delete.status_code == 200
    assert bad_patch.status_code == 400
    assert bb_delete.status_code == 200
    assert calls[0][0] == "set"
    assert calls[-1] == ("clear",)


def test_school_credentials_reject_empty_values_wrong_types_and_keep_password_secret(
    app_factory,
    monkeypatch,
):
    state = {"student_id": None, "password": None}

    async def fake_get_status():
        return {
            "runtime_configured": bool(state["student_id"] and state["password"]),
            "student_id": state["student_id"],
            "password_set": bool(state["password"]),
        }

    async def fake_set(student_id, password):
        student_id = student_id.strip()
        if not student_id or not password:
            state["student_id"] = None
            state["password"] = None
            return None
        state["student_id"] = student_id
        state["password"] = password

    async def fake_patch(student_id=None, password=None):
        merged_student_id = state["student_id"] if student_id is None else student_id.strip()
        merged_password = state["password"] if password is None else password
        if not merged_student_id or not merged_password:
            raise ValueError("Both id and password are required after patch merge")
        state["student_id"] = merged_student_id
        state["password"] = merged_password
        return "database"

    monkeypatch.setattr(school_settings_api.school_credentials, "get_school_cas_credentials_status", fake_get_status)
    monkeypatch.setattr(school_settings_api.school_credentials, "set_school_cas_credentials", fake_set)
    monkeypatch.setattr(school_settings_api.school_credentials, "patch_school_cas_config", fake_patch)
    monkeypatch.setattr(school_settings_api, "_sync_calendar_sources_once", _fake_sync_calendar_sources_once)

    app = app_factory()
    app.state.async_session = object()
    app.include_router(school_settings_router, prefix="/api")
    client = TestClient(app)

    wrong_type_put = client.put("/api/settings/tis/credentials", json={"student_id": 123, "password": []})
    incomplete_patch = client.patch("/api/patch_cas", json={"id": " 2468 "})
    full_patch = client.patch("/api/patch_cas", json={"id": " 2468 ", "password": "patch-secret"})
    password_only_patch = client.patch("/api/patch_cas", json={"password": "rotated-secret"})
    status = client.get("/api/settings/tis/credentials")

    assert wrong_type_put.status_code == 400
    assert incomplete_patch.status_code == 400
    assert full_patch.status_code == 200
    assert password_only_patch.status_code == 200
    assert status.json() == {
        "runtime_configured": True,
        "student_id": "2468",
        "password_set": True,
    }
    assert "patch-secret" not in status.text
    assert "rotated-secret" not in status.text


@pytest.mark.xfail(
    reason="Known issue: PUT credentials treats empty values as clear instead of rejecting them.",
    strict=True,
)
def test_school_credentials_should_reject_empty_put_values(
    app_factory,
    monkeypatch,
):
    async def fake_set(_student_id, _password):
        return None

    monkeypatch.setattr(school_settings_api.school_credentials, "set_school_cas_credentials", fake_set)
    monkeypatch.setattr(school_settings_api, "_sync_calendar_sources_once", _fake_sync_calendar_sources_once)

    app = app_factory()
    app.state.async_session = object()
    app.include_router(school_settings_router, prefix="/api")
    client = TestClient(app)

    response = client.put("/api/settings/tis/credentials", json={"student_id": "", "password": ""})

    assert response.status_code == 400


@pytest.mark.xfail(
    reason="Known issue: background calendar refresh errors can escape credential update responses.",
    strict=True,
)
def test_school_credentials_background_refresh_failure_should_not_fail_save(
    app_factory,
    monkeypatch,
):
    async def fake_set(_student_id, _password):
        return None

    async def fake_sync_failure(*_args, **_kwargs):
        raise RuntimeError("fake refresh failed")

    monkeypatch.setattr(school_settings_api.school_credentials, "set_school_cas_credentials", fake_set)
    monkeypatch.setattr(school_settings_api, "_sync_calendar_sources_once", fake_sync_failure)

    app = app_factory()
    app.state.async_session = object()
    app.include_router(school_settings_router, prefix="/api")
    client = TestClient(app)

    response = client.put(
        "/api/settings/tis/credentials",
        json={"student_id": "12345678", "password": "secret"},
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("put", "/api/settings/tis/credentials"),
        ("put", "/api/settings/bb/credentials"),
        ("patch", "/api/patch_cas"),
    ],
)
@pytest.mark.xfail(
    reason="Spec declares 422 for request validation, but the app-level validation handler maps it to 400.",
    strict=True,
)
def test_school_settings_body_validation_should_match_spec_422(app_factory, monkeypatch, method, path):
    client = _school_settings_client(app_factory, monkeypatch)

    response = getattr(client, method)(path, json={})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/settings/tis/credentials", {"student_id": "1" * 64, "password": "p" * 4096}),
        ("/api/settings/bb/credentials", {"student_id": "学号-0001", "password": "pa$$' OR 1=1 --"}),
    ],
)
def test_school_credentials_accept_long_unicode_and_injection_as_secret_data(
    app_factory,
    monkeypatch,
    path,
    payload,
):
    calls = []

    async def fake_set(student_id, password):
        calls.append((student_id, password))

    monkeypatch.setattr(school_settings_api.school_credentials, "set_school_cas_credentials", fake_set)
    client = _school_settings_client(app_factory, monkeypatch)

    response = client.put(path, json=payload)

    assert response.status_code == 200
    assert response.json()["student_id"] == payload["student_id"].strip()
    assert payload["password"] not in response.text
    assert calls == [(payload["student_id"], payload["password"])]


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/settings/tis/credentials", {"student_id": None, "password": "secret"}),
        ("/api/settings/tis/credentials", {"student_id": "12345678", "password": None}),
        ("/api/settings/bb/credentials", {"student_id": ["12345678"], "password": "secret"}),
        ("/api/settings/bb/credentials", {"student_id": "12345678", "password": {"$ne": ""}}),
    ],
)
def test_school_credentials_reject_null_wrong_type_and_nosql_shapes(app_factory, monkeypatch, path, payload):
    client = _school_settings_client(app_factory, monkeypatch)

    response = client.put(path, json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize("path", ["/api/settings/tis/credentials", "/api/settings/bb/credentials"])
def test_school_credentials_get_and_delete_surface_dependency_500(app_factory, monkeypatch, path):
    async def fake_get_status():
        raise RuntimeError("credential store down")

    async def fake_clear():
        raise RuntimeError("credential store down")

    monkeypatch.setattr(school_settings_api.school_credentials, "get_school_cas_credentials_status", fake_get_status)
    monkeypatch.setattr(school_settings_api.school_credentials, "clear_school_cas_credentials", fake_clear)
    client = _school_settings_client(app_factory, monkeypatch, raise_server_exceptions=False)

    get_response = client.get(path)
    delete_response = client.delete(path)

    assert get_response.status_code == 500
    assert delete_response.status_code == 500


def test_patch_cas_rejects_empty_null_and_wrong_type_without_leaking_password(app_factory, monkeypatch):
    async def fake_patch(student_id=None, password=None):
        if not student_id or not password:
            raise ValueError("Both id and password are required after patch merge")
        return "database"

    monkeypatch.setattr(school_settings_api.school_credentials, "patch_school_cas_config", fake_patch)
    client = _school_settings_client(app_factory, monkeypatch)

    empty = client.patch("/api/patch_cas", json={"id": "", "password": ""})
    nulls = client.patch("/api/patch_cas", json={"id": None, "password": None})
    wrong_type = client.patch("/api/patch_cas", json={"id": {"$ne": ""}, "password": ["secret"]})

    assert empty.status_code == 400
    assert nulls.status_code == 400
    assert wrong_type.status_code == 400
    assert "secret" not in wrong_type.text
