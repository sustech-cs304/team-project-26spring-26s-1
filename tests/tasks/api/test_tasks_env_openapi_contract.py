from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from openapi_spec_validator import validate


pytestmark = pytest.mark.api


SPEC_PATH = Path("spec/modules/tasks_env.openapi.yaml")

EXPECTED_OPERATIONS = {
    ("post", "/api/tasks/create"): {"200", "400", "422", "500"},
    ("post", "/api/tasks"): {"200", "400", "422", "500"},
    ("get", "/api/tasks"): {"200", "400", "422", "500"},
    ("get", "/api/tasks/{task_id}"): {"200", "400", "404", "422", "500"},
    ("post", "/api/tasks/{task_id}"): {"200", "400", "404", "422", "500"},
    ("put", "/api/tasks/{task_id}"): {"200", "400", "404", "422", "500"},
    ("patch", "/api/tasks/{task_id}"): {"200", "400", "404", "422", "500"},
    ("delete", "/api/tasks/{task_id}"): {"200", "400", "401", "404", "422", "500"},
    ("post", "/api/tasks/{task_id}/enable"): {"200", "400", "404", "422", "500"},
    ("post", "/api/tasks/{task_id}/disable"): {"200", "400", "404", "422", "500"},
    ("post", "/api/tasks/{task_id}/trigger"): {"200", "400", "404", "422", "500"},
    ("get", "/api/tasks/{task_id}/runs"): {"200", "400", "404", "422", "500"},
    ("post", "/api/tasks/{task_id}/runs"): {"200", "400", "404", "422", "500"},
    ("post", "/api/runs/{run_id}/cancel"): {"200", "400", "404", "422", "500"},
    ("post", "/api/runs/{run_id}/complete"): {"200", "400", "404", "422", "500"},
    ("get", "/api/runs/{run_id}"): {"200", "400", "404", "422", "500"},
    ("get", "/api/runs/{run_id}/logs"): {"200", "400", "404", "422", "500"},
    ("get", "/api/runs/{run_id}/stream"): {"200", "400", "404", "422", "500"},
    ("get", "/api/env-vars"): {"200", "400", "422", "500"},
    ("post", "/api/env-vars"): {"200", "400", "422", "500"},
    ("delete", "/api/env-vars/{key}"): {"200", "400", "401", "404", "409", "422", "500"},
}


@pytest.fixture(scope="module")
def tasks_env_spec() -> dict:
    with SPEC_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_tasks_env_openapi_spec_is_valid(tasks_env_spec):
    validate(tasks_env_spec)
    assert tasks_env_spec["openapi"] == "3.1.0"


def test_tasks_env_spec_operation_and_response_matrix_is_complete(tasks_env_spec):
    operations = {
        (method, path): set(operation["responses"])
        for path, methods in tasks_env_spec["paths"].items()
        for method, operation in methods.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }

    assert operations.keys() == EXPECTED_OPERATIONS.keys()
    for operation, expected_statuses in EXPECTED_OPERATIONS.items():
        assert expected_statuses <= operations[operation]


def test_deprecated_run_stream_is_marked_outside_normal_api_surface(tasks_env_spec):
    stream_operation = tasks_env_spec["paths"]["/api/runs/{run_id}/stream"]["get"]

    assert stream_operation["deprecated"] is True
    assert "text/event-stream" in stream_operation["responses"]["200"]["content"]


def test_tasks_env_spec_documents_implemented_task_field_constraints(tasks_env_spec):
    schemas = tasks_env_spec["components"]["schemas"]
    create = schemas["TaskCreateRequest"]
    update = schemas["TaskUpdateRequest"]
    task_response = schemas["TaskResponse"]
    run_response = schemas["RunExecutionResponse"]
    run_list_response = schemas["TaskRunListResponse"]
    log_entry = schemas["LogEntryResponse"]

    assert create["properties"]["name"]["maxLength"] == 1024
    assert create["properties"]["description"]["maxLength"] == 1024
    cron_pattern = r"^\s*(?:\S+\s+\S+\s+\S+\s+\S+\s+\S+)?\s*$"
    assert create["properties"]["cron_expression"]["anyOf"][0]["pattern"] == cron_pattern
    assert create["properties"]["cron_expression"]["anyOf"][1]["type"] == "null"
    assert create["properties"]["payload"]["examples"] == ["print('hello from task')"]
    assert create["properties"]["started_at"]["examples"] == ["2026-05-15T09:00:00+08:00"]

    assert update["additionalProperties"] is False
    assert update["properties"]["name"]["anyOf"][0]["maxLength"] == 1024
    assert update["properties"]["description"]["anyOf"][0]["maxLength"] == 1024
    assert update["properties"]["cron_expression"]["anyOf"][0]["pattern"] == cron_pattern

    assert task_response["properties"]["id"]["format"] == "uuid"
    assert task_response["properties"]["id"]["minLength"] == 36
    assert task_response["properties"]["id"]["maxLength"] == 36
    assert task_response["properties"]["created_at"]["format"] == "date-time"
    assert task_response["properties"]["updated_at"]["format"] == "date-time"
    assert task_response["properties"]["last_run_at"]["anyOf"][0]["format"] == "date-time"
    assert schemas["TaskListResponse"]["properties"]["total"]["minimum"] == 0

    assert run_response["properties"]["id"]["format"] == "uuid"
    assert run_response["properties"]["task_id"]["format"] == "uuid"
    assert run_response["properties"]["started_at"]["format"] == "date-time"
    assert run_response["properties"]["finished_at"]["anyOf"][0]["format"] == "date-time"
    assert run_list_response["properties"]["total"]["minimum"] == 0
    assert run_list_response["properties"]["page"]["minimum"] == 1
    assert run_list_response["properties"]["page_size"]["maximum"] == 200

    assert log_entry["properties"]["duration_ms"]["minimum"] == 0
    assert log_entry["properties"]["step_index"]["minimum"] == 0
    assert log_entry["properties"]["timestamp"]["format"] == "date-time"


def test_tasks_env_spec_documents_implemented_env_var_constraints(tasks_env_spec):
    schemas = tasks_env_spec["components"]["schemas"]
    key_item = schemas["EnvVarKeyItem"]["properties"]["key"]
    env_ref_key = schemas["EnvVarRef"]["properties"]["key"]
    upsert_key = schemas["EnvVarUpsertRequest"]["properties"]["key"]

    assert key_item["minLength"] == 1
    assert key_item["maxLength"] == 1024
    assert key_item["pattern"] == r"^[A-Za-z0-9_]+$"
    assert key_item["examples"] == ["OPENCRAB_TOKEN"]

    assert env_ref_key["minLength"] == 1
    assert env_ref_key["x-trimmedPattern"] == r"^[A-Za-z0-9_]+$"
    assert env_ref_key["x-trimmedMaxLength"] == 1024

    assert schemas["EnvVarUpsertRequest"]["additionalProperties"] is False
    assert upsert_key["minLength"] == 1
    assert upsert_key["x-trimmedPattern"] == r"^[A-Za-z0-9_]+$"
    assert upsert_key["x-trimmedMaxLength"] == 1024
    assert schemas["EnvVarUpsertRequest"]["properties"]["value"]["examples"] == ["sk-example"]
