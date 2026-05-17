from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import agent.api.routine_events as routine_events_api
from agent.api.routine_events import router as routine_events_router
from agent.db.models import RoutineEvent, RoutineSource


pytestmark = pytest.mark.api


@pytest.fixture
def calendar_validation_client(app_factory, sqlite_session_factory):
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.include_router(routine_events_router, prefix="/api")
    return TestClient(app)


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "not-a-list"},
        [{"title": "bad range", "start_time": 200, "end_time": 100}],
        [{"title": "bad color", "start_time": 100, "end_time": 200, "color": "red"}],
        [{"title": "bad color", "start_time": 100, "end_time": 200, "color": "url(javascript:alert(1))"}],
        [{"title": "bad inform", "start_time": 100, "end_time": 200, "inform_type": "yesterday"}],
        [{"title": 123, "start_time": 100, "end_time": 200}],
    ],
)
def test_events_create_rejects_missing_type_format_and_security_inputs(calendar_validation_client, payload):
    response = calendar_validation_client.post("/api/events/create", json=payload)

    assert response.status_code == 400


@pytest.mark.xfail(reason="Known issue: event create accepts an item without a title.", strict=True)
def test_events_create_should_reject_missing_title(calendar_validation_client):
    response = calendar_validation_client.post("/api/events/create", json=[{"end_time": 200}])

    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        [{"title": "missing start", "end_time": 200}],
        [{"title": "missing end", "start_time": 100}],
        [{"title": "missing both"}],
    ],
)
@pytest.mark.xfail(reason="Known issue: event create treats start_time/end_time as optional.", strict=True)
def test_events_create_should_reject_missing_required_times(calendar_validation_client, payload):
    response = calendar_validation_client.post("/api/events/create", json=payload)

    assert response.status_code == 400


def test_events_create_rejects_batch_with_multiple_illegal_fields_without_partial_write(calendar_validation_client):
    response = calendar_validation_client.post(
        "/api/events/create",
        json=[
            {"title": "valid", "start_time": 100, "end_time": 200},
            {
                "title": 123,
                "start_time": 300,
                "end_time": 100,
                "color": "javascript:alert(1)",
                "inform_type": "before-lunch",
            },
        ],
    )
    queried = calendar_validation_client.get("/api/events", params={"start_time": 0, "end_time": 500})

    assert response.status_code == 400
    assert queried.json()["data"] == []


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [{"title": "Epoch", "start_time": 0, "end_time": 0, "description": None, "color": None}],
        [{"title": "<script>alert(1)</script>", "start_time": -1, "end_time": 1, "description": "' OR 1=1 --"}],
        [{"title": "Huge future", "start_time": 4_102_444_800, "end_time": 4_102_448_400}],
        [{"title": "Long", "start_time": 100, "end_time": 200, "description": "x" * 4096}],
    ],
)
def test_events_create_accepts_current_positive_boundary_and_injection_as_data(calendar_validation_client, payload):
    response = calendar_validation_client.post("/api/events/create", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"start_time": 200, "end_time": 100},
        {"start_time": "bad", "end_time": 100},
        {"id": "bad"},
    ],
)
def test_events_query_rejects_missing_range_bad_range_and_bad_types(calendar_validation_client, params):
    response = calendar_validation_client.get("/api/events", params=params)

    assert response.status_code == 400


def test_events_query_treats_keyword_and_source_injection_as_data(calendar_validation_client):
    calendar_validation_client.post(
        "/api/events/create",
        json=[{"title": "Project meeting", "start_time": 100, "end_time": 200}],
    )

    response = calendar_validation_client.get(
        "/api/events",
        params={"start_time": 0, "end_time": 300, "key_word": "' OR 1=1 --", "source": "user;DROP TABLE"},
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_events_query_supports_camel_case_aliases_and_id_takes_precedence(calendar_validation_client):
    first = calendar_validation_client.post(
        "/api/events/create",
        json=[{"title": "Alias target", "start_time": 100, "end_time": 200}],
    )
    second = calendar_validation_client.post(
        "/api/events/create",
        json=[{"title": "Outside range", "start_time": 900, "end_time": 1000}],
    )

    alias_response = calendar_validation_client.get("/api/events", params={"startTime": 50, "endTime": 250})
    id_response = calendar_validation_client.get(
        "/api/events",
        params={"id": second.json()["ids"][0], "start_time": 0, "end_time": 250},
    )

    assert first.status_code == 200
    assert alias_response.status_code == 200
    assert [item["title"] for item in alias_response.json()["data"]] == ["Alias target"]
    assert id_response.status_code == 200
    assert id_response.json()["data"][0]["title"] == "Outside range"


def test_events_query_returns_large_unpaged_range_without_external_resources(calendar_validation_client):
    calendar_validation_client.post(
        "/api/events/create",
        json=[
            {"title": f"Bulk {index:02d}", "start_time": index * 10, "end_time": index * 10 + 5}
            for index in range(35)
        ],
    )

    response = calendar_validation_client.get("/api/events", params={"start_time": 0, "end_time": 400})

    assert response.status_code == 200
    assert len(response.json()["data"]) == 35
    assert response.json()["data"][0]["title"] == "Bulk 00"


@pytest.mark.parametrize(
    "payload",
    [
        {"id": 1},
        [{"title": "missing id"}],
        [{"id": "bad", "title": "x"}],
        [{"id": 1, "start_time": 200, "end_time": 100}],
        [{"id": 1, "color": "#GGGGGG"}],
    ],
)
def test_events_modify_rejects_non_list_missing_id_bad_range_and_color(calendar_validation_client, payload):
    response = calendar_validation_client.put("/api/events/modify", json=payload)

    assert response.status_code == 400


def test_events_modify_merges_partial_update_and_can_clear_color_to_null(calendar_validation_client):
    created = calendar_validation_client.post(
        "/api/events/create",
        json=[{"title": "Original", "start_time": 100, "end_time": 200, "color": "#123456"}],
    )
    event_id = created.json()["ids"][0]

    source_id = calendar_validation_client.get("/api/events/sources").json()[0]["id"]
    calendar_validation_client.patch(f"/api/events/sources/{source_id}", json={"color": "#abcdef"})
    partial = calendar_validation_client.put("/api/events/modify", json=[{"id": event_id, "title": "Renamed"}])
    cleared = calendar_validation_client.put("/api/events/modify", json=[{"id": event_id, "color": None}])
    by_id = calendar_validation_client.get("/api/events", params={"id": event_id})

    assert partial.status_code == 200
    assert cleared.status_code == 200
    assert by_id.json()["data"][0]["title"] == "Renamed"
    assert by_id.json()["data"][0]["start_time"] == 100
    assert by_id.json()["data"][0]["end_time"] == 200
    assert by_id.json()["data"][0]["color"] is None
    assert by_id.json()["data"][0]["source"]["color"] == "#abcdef"


@pytest.mark.parametrize("payload", [{"id": 1}, ["bad"], [999999]])
def test_events_delete_rejects_non_list_bad_types_and_missing_ids(calendar_validation_client, payload):
    response = calendar_validation_client.request("DELETE", "/api/events/delete", json=payload)

    assert response.status_code in {400, 404}


def test_events_delete_duplicate_ids_are_idempotent_for_existing_row(calendar_validation_client):
    created = calendar_validation_client.post(
        "/api/events/create",
        json=[{"title": "Delete me", "start_time": 100, "end_time": 200}],
    )
    event_id = created.json()["ids"][0]

    response = calendar_validation_client.request("DELETE", "/api/events/delete", json=[event_id, event_id])
    missing = calendar_validation_client.get("/api/events", params={"id": event_id})

    assert response.status_code == 200
    assert response.json()["ids"] == [event_id, event_id]
    assert missing.status_code == 400


@pytest.mark.xfail(reason="Known issue: pydantic bool coercion accepts strings such as 'yes'.", strict=True)
def test_events_source_visibility_should_reject_wrong_type(calendar_validation_client):
    calendar_validation_client.post(
        "/api/events/create",
        json=[{"title": "Source type", "start_time": 100, "end_time": 200}],
    )
    source_id = calendar_validation_client.get("/api/events/sources").json()[0]["id"]

    response = calendar_validation_client.patch(f"/api/events/sources/{source_id}", json={"is_visible": "yes"})

    assert response.status_code == 400


def test_events_managed_source_sync_surfaces_fake_failure(calendar_validation_client, monkeypatch):
    async def fake_sync_managed_source(source_id, db):
        raise HTTPException(status_code=400, detail=f"{source_id} fake sync failed")

    monkeypatch.setattr(routine_events_api, "sync_managed_source", fake_sync_managed_source)

    response = calendar_validation_client.patch("/api/events/update/tis")

    assert response.status_code == 400
    assert "fake sync failed" in response.text


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/events/create"),
        ("put", "/api/events/modify"),
        ("delete", "/api/events/delete"),
        ("patch", "/api/events/sources/not-an-int"),
    ],
)
@pytest.mark.xfail(
    reason="Spec declares 422 for request validation, but the app-level validation handler maps it to 400.",
    strict=True,
)
def test_calendar_validation_errors_should_match_spec_422(calendar_validation_client, method, path):
    response = getattr(calendar_validation_client, method)(path, json={})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        [{"title": "", "start_time": 100, "end_time": 100}],
        [{"title": "min negative", "start_time": -2_147_483_648, "end_time": -2_147_483_648}],
        [{"title": "max future", "start_time": 2_147_483_647, "end_time": 2_147_483_647}],
        [{"title": "x" * 1024, "start_time": 100, "end_time": 200, "description": "y" * 8192}],
        [{"title": "{\"$ne\":\"\"}", "start_time": 100, "end_time": 200, "location": "$(whoami)"}],
        [{"title": "<img src=x onerror=alert(1)>", "start_time": 100, "end_time": 200, "link": "javascript:alert(1)"}],
    ],
)
def test_events_create_boundary_and_security_strings_are_stored_as_data(calendar_validation_client, payload):
    response = calendar_validation_client.post("/api/events/create", json=payload)

    assert response.status_code == 200
    assert len(response.json()["ids"]) == 1


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"title": "object-not-array"},
        [None],
        [["nested"]],
        [{"title": "float", "start_time": 1.5, "end_time": 2.5}],
        [{"title": "bool", "start_time": True, "end_time": False}],
        [{"title": "bad-color", "start_time": 1, "end_time": 2, "color": "#12345"}],
    ],
)
def test_events_create_rejects_null_type_format_and_composite_invalid_inputs(calendar_validation_client, payload):
    response = calendar_validation_client.post("/api/events/create", json=payload)

    assert response.status_code == 400


@pytest.mark.xfail(
    reason="Known issue: event create accepts null start_time/end_time values and stores zero/default times.",
    strict=True,
)
def test_events_create_should_reject_null_time_boundary(calendar_validation_client):
    response = calendar_validation_client.post(
        "/api/events/create",
        json=[{"title": "bad-null-range", "start_time": None, "end_time": 1}],
    )

    assert response.status_code == 400


def test_events_query_filters_keyword_alias_source_visibility_and_boundary_overlap(calendar_validation_client):
    calendar_validation_client.post(
        "/api/events/create",
        json=[
            {"title": "Overlap A", "description": "alpha", "start_time": 100, "end_time": 200},
            {"title": "Overlap B", "description": "beta", "start_time": 200, "end_time": 300},
            {"title": "Outside", "description": "alpha", "start_time": 301, "end_time": 400},
        ],
    )
    source_id = calendar_validation_client.get("/api/events/sources").json()[0]["id"]
    hidden = calendar_validation_client.patch(f"/api/events/sources/{source_id}", json={"is_visible": False})
    response = calendar_validation_client.get(
        "/api/events",
        params={"startTime": 200, "endTime": 200, "keyWord": "alpha", "source": "user"},
    )

    assert hidden.status_code == 200
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["data"]] == ["Overlap A"]
    assert response.json()["data"][0]["source"]["is_visible"] is False


def test_events_modify_and_delete_reject_managed_or_missing_rows(calendar_validation_client, sqlite_session_factory, run_async):
    async def _seed_managed():
        async with sqlite_session_factory() as session:
            source = RoutineSource(title="bb", color="#2563eb", is_visible=True)
            session.add(source)
            await session.flush()
            routine = RoutineEvent(
                time_=100,
                end_time_=200,
                event_name="Managed",
                detail="",
                color=None,
                need_inform=False,
                inform_way=0,
                source_id=source.id,
            )
            session.add(routine)
            await session.commit()
            return routine.id

    event_id = run_async(_seed_managed())

    modified = calendar_validation_client.put("/api/events/modify", json=[{"id": event_id, "title": "Nope"}])
    deleted = calendar_validation_client.request("DELETE", "/api/events/delete", json=[event_id])
    missing_modify = calendar_validation_client.put("/api/events/modify", json=[{"id": 999999, "title": "Missing"}])

    assert modified.status_code == 400
    assert deleted.status_code == 400
    assert missing_modify.status_code == 404


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({}, 200),
        ({"color": None, "is_visible": None}, 200),
        ({"color": "#abc", "is_visible": True}, 200),
        ({"color": "#AABBCCDD", "is_visible": False}, 200),
        ({"color": "", "is_visible": True}, 400),
        ({"color": "url(javascript:alert(1))"}, 400),
        ({"color": {"$ne": ""}}, 400),
    ],
)
def test_events_source_patch_body_matrix(calendar_validation_client, payload, expected_status):
    calendar_validation_client.post(
        "/api/events/create",
        json=[{"title": "Source matrix", "start_time": 100, "end_time": 200}],
    )
    source_id = calendar_validation_client.get("/api/events/sources").json()[0]["id"]

    response = calendar_validation_client.patch(f"/api/events/sources/{source_id}", json=payload)

    assert response.status_code == expected_status


def test_events_source_patch_can_clear_color_to_null(calendar_validation_client):
    calendar_validation_client.post(
        "/api/events/create",
        json=[{"title": "Source clear", "start_time": 100, "end_time": 200}],
    )
    source_id = calendar_validation_client.get("/api/events/sources").json()[0]["id"]

    patched = calendar_validation_client.patch(f"/api/events/sources/{source_id}", json={"color": None})
    queried = calendar_validation_client.get("/api/events", params={"start_time": 0, "end_time": 300})

    assert patched.status_code == 200
    assert patched.json()["color"] is None
    assert queried.json()["data"][0]["source"]["color"] is None
    assert queried.json()["data"][0]["color"] is None


@pytest.mark.parametrize("source_id", ["", " ", "../1", "1;DROP TABLE source", '{"$ne":""}'])
def test_events_refresh_source_rejects_unsafe_or_missing_source_ids(calendar_validation_client, source_id):
    response = calendar_validation_client.patch(f"/api/events/update/{source_id}")

    assert response.status_code in {400, 404}


@pytest.mark.xfail(
    reason="Known issue: very large numeric source_id reaches SQLite integer conversion and returns 500.",
    strict=True,
)
def test_events_refresh_source_should_reject_extreme_numeric_source_id_without_500(calendar_validation_client):
    response = calendar_validation_client.patch("/api/events/update/" + "9" * 80)

    assert response.status_code in {400, 404, 422}


def test_events_refresh_numeric_ical_source_requires_configured_url(calendar_validation_client):
    calendar_validation_client.post(
        "/api/events/create",
        json=[{"title": "iCal source", "start_time": 100, "end_time": 200}],
    )
    source_id = calendar_validation_client.get("/api/events/sources").json()[0]["id"]

    response = calendar_validation_client.patch(f"/api/events/update/{source_id}")

    assert response.status_code == 400
    assert "ICAL url" in response.text


def test_events_runtime_dependency_failure_returns_500(app_factory, sqlite_session_factory):
    class BrokenDb:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("db unavailable")

    async def fake_get_db(_request=None):
        yield BrokenDb()

    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.dependency_overrides[routine_events_api.get_db] = fake_get_db
    app.include_router(routine_events_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/events/sources")

    assert response.status_code == 500
