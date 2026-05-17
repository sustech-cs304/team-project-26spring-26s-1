from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from openapi_spec_validator import validate

from agent.api.routine_events import router as routine_events_router
from agent.api.school_settings import router as school_settings_router


pytestmark = pytest.mark.api


SPEC_PATH = Path("spec/modules/calendar_settings.openapi.yaml")


def _load_spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("path", "method", "statuses"),
    [
        ("/api/settings/tis/credentials", "get", {"200", "400", "422", "500"}),
        ("/api/settings/tis/credentials", "put", {"200", "400", "422", "500"}),
        ("/api/settings/tis/credentials", "delete", {"200", "400", "401", "422", "500"}),
        ("/api/patch_cas", "patch", {"200", "400", "422", "500"}),
        ("/api/settings/bb/credentials", "get", {"200", "400", "422", "500"}),
        ("/api/settings/bb/credentials", "put", {"200", "400", "422", "500"}),
        ("/api/settings/bb/credentials", "delete", {"200", "400", "401", "422", "500"}),
        ("/api/events/create", "post", {"200", "400", "422", "500"}),
        ("/api/events/modify", "put", {"200", "400", "422", "500"}),
        ("/api/events", "get", {"200", "400", "422", "500"}),
        ("/api/events/delete", "delete", {"200", "400", "401", "422", "500"}),
        ("/api/events/sources", "get", {"200", "400", "422", "500"}),
        ("/api/events/sources/{source_id}", "patch", {"200", "400", "404", "422", "500"}),
        ("/api/events/update/{source_id}", "patch", {"200", "400", "404", "422", "500"}),
    ],
)
def test_calendar_openapi_declares_operation_status_codes(path, method, statuses):
    spec = _load_spec()
    validate(spec)

    operation = spec["paths"][path][method]

    assert statuses <= set(operation["responses"])
    assert operation["operationId"]


def test_calendar_openapi_request_shapes_for_body_and_query_operations():
    spec = _load_spec()

    assert spec["paths"]["/api/events/create"]["post"]["requestBody"]["required"] is True
    assert spec["paths"]["/api/events/modify"]["put"]["requestBody"]["required"] is True
    assert spec["paths"]["/api/events/delete"]["delete"]["requestBody"]["required"] is True
    assert spec["paths"]["/api/settings/tis/credentials"]["put"]["requestBody"]["required"] is True
    assert spec["paths"]["/api/settings/bb/credentials"]["put"]["requestBody"]["required"] is True

    query_names = {
        param["name"]
        for param in spec["paths"]["/api/events"]["get"]["parameters"]
    }
    assert query_names == {
        "id",
        "start_time",
        "startTime",
        "end_time",
        "endTime",
        "key_word",
        "keyWord",
        "source",
    }
    query_params = {
        param["name"]: param["schema"]
        for param in spec["paths"]["/api/events"]["get"]["parameters"]
    }
    assert query_params["id"]["anyOf"][0]["format"] == "int64"
    assert query_params["start_time"]["anyOf"][0]["format"] == "int64"
    assert query_params["end_time"]["anyOf"][0]["format"] == "int64"


def test_calendar_openapi_declares_implemented_field_constraints():
    spec = _load_spec()
    schemas = spec["components"]["schemas"]

    create_props = schemas["RoutineCreateRequest"]["properties"]
    update_props = schemas["RoutineUpdateRequest"]["properties"]
    source_props = schemas["SourceUpdateRequest"]["properties"]

    assert create_props["start_time"]["anyOf"][0]["format"] == "int64"
    assert create_props["end_time"]["anyOf"][0]["format"] == "int64"
    assert create_props["color"]["anyOf"][0]["pattern"] == r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$"
    assert update_props["id"]["format"] == "int64"
    assert update_props["color"]["anyOf"][0]["pattern"] == create_props["color"]["anyOf"][0]["pattern"]
    assert source_props["color"]["anyOf"][0]["pattern"] == create_props["color"]["anyOf"][0]["pattern"]
    assert create_props["inform_type"]["anyOf"][0]["enum"] == [
        "none",
        "at_start",
        "5_minutes_before",
        "10_minutes_before",
        "30_minutes_before",
        "1_hour_before",
    ]

    mutation_schema = spec["paths"]["/api/events/create"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    query_schema = spec["paths"]["/api/events"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    sources_schema = spec["paths"]["/api/events/sources"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert mutation_schema == {"$ref": "#/components/schemas/RoutineMutationResponse"}
    assert query_schema == {"$ref": "#/components/schemas/RoutineQueryResponse"}
    assert sources_schema["items"] == {"$ref": "#/components/schemas/RoutineSourceResponse"}


def test_calendar_runtime_openapi_contains_spec_operations(app_factory):
    app = app_factory()
    app.state.async_session = object()
    app.include_router(school_settings_router, prefix="/api")
    app.include_router(routine_events_router, prefix="/api")
    client = TestClient(app)

    runtime_spec = client.get("/openapi.json").json()
    expected = _load_spec()["paths"]

    for path, methods in expected.items():
        assert path in runtime_spec["paths"]
        for method in methods:
            assert method in runtime_spec["paths"][path]
