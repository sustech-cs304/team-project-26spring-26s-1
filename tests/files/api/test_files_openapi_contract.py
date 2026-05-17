from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from openapi_spec_validator import validate

from agent.api.file import router as file_router


pytestmark = pytest.mark.api


SPEC_PATH = Path("spec/modules/files.openapi.yaml")


def _load_spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("path", "method", "statuses"),
    [
        ("/api/files/upload", "post", {"200", "400", "413", "417", "422", "500"}),
        ("/api/file/{file_id}", "get", {"200", "400", "404", "422", "500"}),
        ("/api/files/{message_id}/{file_id}/info", "get", {"200", "400", "404", "422", "500"}),
    ],
)
def test_files_openapi_declares_operation_status_codes(path, method, statuses):
    spec = _load_spec()
    validate(spec)

    operation = spec["paths"][path][method]

    assert statuses <= set(operation["responses"])
    assert operation["operationId"]


def test_files_openapi_request_and_path_shapes():
    spec = _load_spec()

    upload_body = spec["paths"]["/api/files/upload"]["post"]["requestBody"]
    assert upload_body["required"] is True
    assert "multipart/form-data" in upload_body["content"]
    upload_file_schema = spec["components"]["schemas"]["Body_upload_file_api_files_upload_post"]["properties"]["file"]
    assert upload_file_schema["format"] == "binary"
    assert "10 MiB" in upload_file_schema["description"]
    assert ".pdf" in upload_file_schema["description"]

    download_params = spec["paths"]["/api/file/{file_id}"]["get"]["parameters"]
    info_params = spec["paths"]["/api/files/{message_id}/{file_id}/info"]["get"]["parameters"]

    assert [param["name"] for param in download_params] == ["file_id"]
    assert {param["name"] for param in info_params} == {"message_id", "file_id"}
    assert all(param["in"] == "path" and param["required"] is True for param in download_params + info_params)
    assert all(param["schema"]["format"] == "uuid" for param in download_params + info_params)
    assert all(param["schema"]["minLength"] == 36 for param in download_params + info_params)
    assert all(param["schema"]["maxLength"] == 36 for param in download_params + info_params)
    assert all("pattern" in param["schema"] for param in download_params + info_params)

    upload_response = spec["components"]["schemas"]["FileUploadResponse"]["properties"]
    info_response = spec["components"]["schemas"]["FileInfoResponse"]["properties"]
    assert upload_response["file_id"]["format"] == "uuid"
    assert upload_response["file_name"]["maxLength"] == 512
    assert "text/plain" in upload_response["mime_type"]["anyOf"][0]["enum"]
    assert info_response["file_type"]["enum"] == ["image", "pdf", "markdown", "text", "other"]


def test_files_runtime_openapi_contains_spec_operations(app_factory, sqlite_session_factory):
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.include_router(file_router, prefix="/api")
    client = TestClient(app)

    runtime_spec = client.get("/openapi.json").json()
    expected = _load_spec()["paths"]

    for path, methods in expected.items():
        assert path in runtime_spec["paths"]
        for method in methods:
            assert method in runtime_spec["paths"][path]
