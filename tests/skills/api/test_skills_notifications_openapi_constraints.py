from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from openapi_spec_validator import validate


pytestmark = pytest.mark.api


def _load_spec(name: str) -> dict:
    spec = yaml.safe_load(Path("spec/modules", name).read_text(encoding="utf-8"))
    validate(spec)
    return spec


def _schema(spec: dict, name: str) -> dict:
    return spec["components"]["schemas"][name]


def _param(spec: dict, path: str, method: str, name: str) -> dict:
    for param in spec["paths"][path][method]["parameters"]:
        if param["name"] == name:
            return param["schema"]
    raise AssertionError(f"Missing parameter {name!r} on {method.upper()} {path}")


def test_skills_auth_spec_records_implemented_pagination_and_field_metadata():
    spec = _load_spec("skills_auth.openapi.yaml")

    assert _param(spec, "/api/skills", "get", "page")["minimum"] == 1
    assert _param(spec, "/api/skills", "get", "page_size")["minimum"] == 1
    assert _param(spec, "/api/skills", "get", "page_size")["maximum"] == 100
    assert _param(spec, "/api/skills", "get", "search")["examples"] == ["writer"]

    login = _schema(spec, "LoginRequest")
    assert login["required"] == ["email", "password"]
    assert login["properties"]["email"]["type"] == "string"
    assert login["properties"]["email"]["examples"] == ["user@example.edu"]

    upload = _schema(spec, "Body_upload_skill_api_skills_post")
    assert upload["required"] == ["file"]
    assert upload["properties"]["file"]["contentMediaType"] == "application/octet-stream"
    assert upload["properties"]["tag_ids"]["examples"] == ["1,2"]


def test_notifications_rag_config_spec_records_implemented_constraints():
    spec = _load_spec("notifications_rag_config.openapi.yaml")

    dispatch = _schema(spec, "NotificationDispatchRequest")
    assert dispatch["properties"]["level"]["enum"] == ["info", "success", "warning", "error"]
    assert dispatch["properties"]["level"]["default"] == "info"
    assert dispatch["properties"]["actions"]["default"] == []

    dispatch_response = _schema(spec, "NotificationDispatchResponse")
    assert dispatch_response["properties"]["status"]["enum"] == ["scheduled"]
    assert dispatch_response["properties"]["status"]["default"] == "scheduled"

    for path, method in [
        ("/api/notifications/dispatch", "post"),
        ("/api/notifications/deeplink-preview/{resource}", "get"),
    ]:
        assert "503" in spec["paths"][path][method]["responses"]

    rag_status = _schema(spec, "RagCloudSyncStatusResponse")
    assert rag_status["properties"]["status"]["enum"] == ["idle", "running", "success", "failed"]
    assert rag_status["properties"]["stage"]["enum"] == [
        "idle",
        "manifest",
        "download",
        "import",
        "completed",
        "failed",
    ]
    assert rag_status["properties"]["progress"]["minimum"] == 0
    assert rag_status["properties"]["progress"]["maximum"] == 100
    assert rag_status["properties"]["embedded_added"]["minimum"] == 0
    assert rag_status["properties"]["embedded_overwritten"]["minimum"] == 0
    assert rag_status["properties"]["embedded_failed"]["minimum"] == 0


def test_config_spec_uses_app_config_schema_and_known_partial_patch_shape():
    spec = _load_spec("notifications_rag_config.openapi.yaml")

    assert (
        spec["paths"]["/api/get_config"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/AppConfig"
    )
    assert (
        spec["paths"]["/api/patch_config"]["patch"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/AppConfigPatchRequest"
    )
    assert (
        spec["paths"]["/api/patch_config"]["patch"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/AppConfig"
    )

    llm = _schema(spec, "LLMEndpointConfig")
    assert llm["properties"]["type"]["enum"] == ["OpenAI", "Qwen", "Anthropic"]
    assert llm["properties"]["max_token_count"]["minimum"] == 1

    code_interpreter = _schema(spec, "CodeInterpreterConfig")
    assert code_interpreter["properties"]["default_timeout_s"]["exclusiveMinimum"] == 0
    assert code_interpreter["properties"]["auto_approve_max_risk_level"]["enum"] == ["Low", "Medium", "High"]

    patch = _schema(spec, "AppConfigPatchRequest")
    assert patch["additionalProperties"] is True
    assert patch["properties"]["notification"]["$ref"] == "#/components/schemas/NotificationConfigPatch"
