from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from openapi_spec_validator import validate

from agent.main import app


pytestmark = pytest.mark.api


def _path_methods(spec: dict, path: str) -> set[str]:
    return {
        method.upper()
        for method in spec["paths"][path]
        if method != "parameters" and not method.startswith("x-")
    }


def test_current_fastapi_entrypoints_expose_key_backend_surfaces():
    spec = app.openapi()

    expected = {
        "/api/auth/login": {"POST"},
        "/api/auth/me": {"GET"},
        "/api/conversation": {"POST"},
        "/api/conversation/completion": {"POST"},
        "/api/conversations/": {"GET"},
        "/api/env-vars": {"GET", "POST"},
        "/api/events": {"GET"},
        "/api/events/create": {"POST"},
        "/api/file/{file_id}": {"GET"},
        "/api/files/{message_id}/{file_id}/info": {"GET"},
        "/api/notifications/dispatch": {"POST"},
        "/api/tasks": {"GET", "POST"},
        "/api/tasks/create": {"POST"},
        "/api/tasks/{task_id}": {"GET", "POST", "PUT", "PATCH", "DELETE"},
        "/api/tasks/{task_id}/trigger": {"POST"},
        "/api/runs/{run_id}": {"GET"},
        "/api/runs/{run_id}/logs": {"GET"},
    }

    assert spec["openapi"].startswith("3.")
    for path, methods in expected.items():
        assert path in spec["paths"]
        assert methods <= _path_methods(spec, path)


@pytest.mark.parametrize("spec_path", sorted(Path("spec/modules").glob("*.openapi.yaml")))
def test_module_openapi_specs_are_valid_openapi_31_documents(spec_path):
    module_spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))

    validate(module_spec)

    assert module_spec["openapi"] == "3.1.0"
    assert module_spec["paths"]


def test_supplied_markdown_spec_stale_endpoints_are_not_current_fastapi_entrypoints():
    spec = app.openapi()

    stale_or_external = {
        "/api/auth/password/reset": "Spec lists password reset, current backend router does not expose it.",
        "/api/auth/password/captcha": "Spec lists password captcha, current backend router does not expose it.",
        "/api/chat/icebreakers": "Spec lists icebreakers, current backend router does not expose it.",
    }

    for path, reason in stale_or_external.items():
        assert path not in spec["paths"], reason


def test_current_fastapi_entrypoints_not_present_or_different_in_supplied_spec_are_documented():
    spec = app.openapi()

    current_code_surfaces = {
        "/api/notifications/dispatch",
        "/api/notifications/deeplink-preview/{resource}",
        "/api/rag/sync",
        "/api/rag/sync/status",
        "/api/settings/tis/credentials",
        "/api/settings/bb/credentials",
        "/api/skills/downloaded",
        "/api/skills/downloaded/{skill_id}",
    }

    for path in current_code_surfaces:
        assert path in spec["paths"]


def test_main_app_converts_fastapi_validation_errors_to_400_response():
    client = TestClient(app)

    response = client.get("/api/tasks", params={"page": 0})

    assert response.status_code == 400
    assert response.json() == {"message": "Invalid request parameters"}


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("POST", "/api/auth/login", b'{"email": "user@example.edu",'),
        ("POST", "/api/tasks/create", b'{"name": "x",'),
        ("PATCH", "/api/patch_config", b'{"notification":'),
    ],
)
def test_main_app_converts_malformed_json_to_400_response(method, url, body):
    client = TestClient(app)

    response = client.request(method, url, content=body, headers={"content-type": "application/json"})

    assert response.status_code == 400
    assert response.json() == {"message": "Invalid request parameters"}


def test_internal_shutdown_requires_uvicorn_server_state():
    client = TestClient(app)

    response = client.post("/internal/shutdown")

    assert response.status_code == 503
