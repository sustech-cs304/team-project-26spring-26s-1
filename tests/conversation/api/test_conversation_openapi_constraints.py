from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from openapi_spec_validator import validate


pytestmark = pytest.mark.api


SPEC_PATH = Path("spec/modules/conversation.openapi.yaml")


@pytest.fixture(scope="module")
def conversation_spec() -> dict:
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    validate(spec)
    return spec


def _schema(spec: dict, name: str) -> dict:
    return spec["components"]["schemas"][name]


def _query_param(spec: dict, path: str, method: str, name: str) -> dict:
    for parameter in spec["paths"][path][method]["parameters"]:
        if parameter["name"] == name and parameter["in"] == "query":
            return parameter
    raise AssertionError(f"{method.upper()} {path} query parameter {name!r} not found")


def _path_param(spec: dict, path: str, method: str, name: str) -> dict:
    for parameter in spec["paths"][path][method]["parameters"]:
        if parameter["name"] == name and parameter["in"] == "path":
            return parameter
    raise AssertionError(f"{method.upper()} {path} path parameter {name!r} not found")


def test_conversation_completion_request_documents_current_model_constraints(conversation_spec):
    request = _schema(conversation_spec, "ConversationCompletionRequest")

    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

    assert request["required"] == ["conversation_id", "request_id", "need_history"]
    assert request["properties"]["conversation_id"]["type"] == "string"
    assert request["properties"]["conversation_id"]["maxLength"] == 36
    assert request["properties"]["conversation_id"]["pattern"] == uuid_pattern
    assert request["properties"]["request_id"]["type"] == "string"
    assert request["properties"]["request_id"]["pattern"] == uuid_pattern
    assert request["properties"]["content"]["anyOf"][0]["maxLength"] == 20_000
    assert {"type": "null"} in request["properties"]["content"]["anyOf"]
    assert "created_at" not in request["properties"]
    assert request["properties"]["attachments"]["type"] == "array"
    assert request["properties"]["attachments"]["maxItems"] == 20
    assert request["properties"]["attachments"]["items"]["type"] == "string"
    assert request["properties"]["attachments"]["items"]["pattern"] == uuid_pattern
    assert request["properties"]["need_history"]["type"] == "boolean"
    assert {"type": "null"} in request["properties"]["restart_message_id"]["anyOf"]
    assert request["properties"]["restart_message_id"]["anyOf"][0]["pattern"] == uuid_pattern


def test_conversation_create_and_state_change_responses_are_explicit(conversation_spec):
    create_response = conversation_spec["paths"]["/api/conversation"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    cancel_response = conversation_spec["paths"]["/api/conversation/cancelchat"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    patch_response = conversation_spec["paths"]["/api/conversation/{conversation_id}"]["patch"]["responses"]["200"]["content"]["application/json"]["schema"]
    delete_response = conversation_spec["paths"]["/api/conversation/{conversation_id}"]["delete"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert create_response == {"$ref": "#/components/schemas/ConversationCreateResponse"}
    assert cancel_response == {"$ref": "#/components/schemas/ConversationStatusResponse"}
    assert patch_response == {"$ref": "#/components/schemas/ConversationStatusResponse"}
    assert delete_response == {"type": "null"}

    assert _schema(conversation_spec, "ConversationCreateResponse")["properties"]["conversation_id"]["maxLength"] == 36
    assert _schema(conversation_spec, "ConversationStatusResponse")["properties"]["status"]["enum"] == ["cancelled", "updated"]


def test_conversation_search_query_documents_implemented_runtime_validation(conversation_spec):
    keywords = _query_param(conversation_spec, "/api/conversations/search", "get", "keywords")["schema"]
    page = _query_param(conversation_spec, "/api/conversations/search", "get", "page")["schema"]
    page_size = _query_param(conversation_spec, "/api/conversations/search", "get", "page_size")["schema"]

    assert keywords["type"] == "string"
    assert keywords["minLength"] == 1
    assert keywords["maxLength"] == 200
    assert page["minimum"] == 1
    assert page_size["minimum"] == 1
    assert page_size["maximum"] == 100


def test_conversation_persistent_fields_document_database_backed_lengths(conversation_spec):
    item = _schema(conversation_spec, "ConversationListItem")
    update = _schema(conversation_spec, "ConversationUpdateRequest")

    assert item["properties"]["conversation_id"]["maxLength"] == 36
    assert item["properties"]["title"]["maxLength"] == 255
    assert update["properties"]["title"]["anyOf"][0]["maxLength"] == 64
    assert update["properties"]["title"]["anyOf"][0]["minLength"] == 1
    assert update["additionalProperties"] is False
    assert _path_param(conversation_spec, "/api/conversation/{conversation_id}", "delete", "conversation_id")["schema"]["maxLength"] == 36
    assert _path_param(conversation_spec, "/api/conversation/{conversation_id}", "patch", "conversation_id")["schema"]["maxLength"] == 36


def test_conversation_asr_websocket_is_documented_as_openapi_extension(conversation_spec):
    websocket_specs = conversation_spec["x-websocketEndpoints"]

    assert websocket_specs[0]["path"] == "/api/conversation/asr"
    assert websocket_specs[0]["clientMessages"]["anyOf"][0]["type"] == "string"
    assert websocket_specs[0]["serverMessages"]["anyOf"][1]["required"] == ["error"]
