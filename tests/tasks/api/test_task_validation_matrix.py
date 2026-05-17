from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import agent.api.task as task_api
from agent.api.task import router as task_router


pytestmark = pytest.mark.api


class ValidationTaskRuntime:
    def __init__(self):
        self.created_payloads = []
        self.trigger_calls = []
        self.tasks = {
            "task-1": {
                "id": "task-1",
                "name": "Daily sync",
                "description": "Sync calendar",
                "cron_expression": "* * * * *",
                "execution_mode": "script",
                "payload": "print('ok')",
                "env_var_refs": [],
                "status": "enabled",
                "created_at": "2026-05-14T00:00:00+00:00",
                "updated_at": "2026-05-14T00:00:00+00:00",
                "last_run_at": None,
                "last_run_status": None,
                "last_run_trigger": None,
                "started_at": None,
            }
        }
        self.runs = {
            "run-1": {
                "id": "run-1",
                "task_id": "task-1",
                "status": "running",
                "trigger": "manual",
                "started_at": "2026-05-14T00:01:00+00:00",
                "finished_at": None,
                "message": None,
                "override_prompt": None,
                "logs": [{"id": "log-1", "content": "ok", "metadata": {}}],
            },
            "terminal-run": {
                "id": "terminal-run",
                "task_id": "task-1",
                "status": "succeeded",
                "trigger": "manual",
                "started_at": "2026-05-14T00:01:00+00:00",
                "finished_at": "2026-05-14T00:02:00+00:00",
                "message": None,
                "override_prompt": None,
                "logs": [],
            },
        }

    async def create_task(self, **kwargs):
        task = {
            **self.tasks["task-1"],
            "id": f"task-{len(self.tasks) + 1}",
            **kwargs,
        }
        self.created_payloads.append(kwargs)
        self.tasks[task["id"]] = task
        return task

    async def list_tasks(self, *, status=None, page=1, page_size=20):
        rows = [t for t in self.tasks.values() if status is None or t["status"] == status]
        return rows[(page - 1) * page_size : page * page_size], len(rows)

    async def get_task(self, task_id):
        return self.tasks.get(task_id)

    async def update_task(self, task_id, updates):
        if task_id not in self.tasks:
            return None
        self.tasks[task_id].update(updates)
        return self.tasks[task_id]

    async def set_task_enabled(self, task_id, enabled):
        if task_id not in self.tasks:
            return None
        self.tasks[task_id]["status"] = "enabled" if enabled else "disabled"
        return self.tasks[task_id]

    async def trigger_task(self, task_id, *, trigger, override_prompt=None):
        if task_id not in self.tasks:
            return None
        self.trigger_calls.append({"trigger": trigger, "override_prompt": override_prompt})
        self.runs["run-1"]["trigger"] = trigger
        self.runs["run-1"]["override_prompt"] = override_prompt
        return self.runs["run-1"]

    async def list_runs_for_task(self, task_id):
        return [r for r in self.runs.values() if r["task_id"] == task_id]

    async def get_run(self, run_id):
        return self.runs.get(run_id)

    async def cancel_run(self, run_id):
        run = self.runs.get(run_id)
        if run:
            run["status"] = "cancelled"
        return run

    async def complete_run(self, run_id, status, error_message):
        run = self.runs.get(run_id)
        if run:
            run["status"] = "succeeded" if status == "success" else "failed"
            run["message"] = error_message
        return run

    async def delete_task(self, task_id):
        return self.tasks.pop(task_id, None) is not None


@pytest.fixture
def task_validation_client(app_factory, monkeypatch):
    runtime = ValidationTaskRuntime()
    monkeypatch.setattr(task_api, "get_task_runtime", lambda: runtime)
    app = app_factory()
    app.include_router(task_router, prefix="/api")
    return TestClient(app), runtime


class ExplodingTaskRuntime:
    async def create_task(self, **_kwargs):
        raise RuntimeError("runtime unavailable")

    async def list_tasks(self, **_kwargs):
        raise RuntimeError("runtime unavailable")

    async def get_task(self, _task_id):
        raise RuntimeError("runtime unavailable")

    async def update_task(self, _task_id, _updates):
        raise RuntimeError("runtime unavailable")

    async def set_task_enabled(self, _task_id, _enabled):
        raise RuntimeError("runtime unavailable")

    async def trigger_task(self, _task_id, **_kwargs):
        raise RuntimeError("runtime unavailable")

    async def list_runs_for_task(self, _task_id):
        raise RuntimeError("runtime unavailable")

    async def get_run(self, _run_id):
        raise RuntimeError("runtime unavailable")

    async def cancel_run(self, _run_id):
        raise RuntimeError("runtime unavailable")

    async def complete_run(self, _run_id, _status, _error_message):
        raise RuntimeError("runtime unavailable")

    async def delete_task(self, _task_id):
        raise RuntimeError("runtime unavailable")


@pytest.fixture
def exploding_task_client(app_factory, monkeypatch):
    monkeypatch.setattr(task_api, "get_task_runtime", lambda: ExplodingTaskRuntime())
    app = app_factory()
    app.include_router(task_router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "payload",
    [
        {"description": "missing name", "cron_expression": "* * * * *", "execution_mode": "script"},
        {"name": "x", "cron_expression": "* * * * *", "execution_mode": "script"},
        {"name": "x", "description": "bad mode", "cron_expression": "* * * * *", "execution_mode": "binary"},
        {"name": "x", "description": "short cron", "cron_expression": "* * * *", "execution_mode": "script"},
        {"name": "x", "description": "bad env", "cron_expression": "* * * * *", "execution_mode": "script", "env_var_refs": ["TOKEN;DROP"]},
        {"name": "x", "description": "missing env key", "cron_expression": "* * * * *", "execution_mode": "script", "env_var_refs": [{}]},
        {"name": "x", "description": "null env key", "cron_expression": "* * * * *", "execution_mode": "script", "env_var_refs": [{"key": None}]},
        {"name": "x" * 1025, "description": "too long", "cron_expression": "* * * * *", "execution_mode": "script"},
        {"name": "x", "description": "x" * 1025, "cron_expression": "* * * * *", "execution_mode": "script"},
    ],
)
def test_task_create_rejects_missing_invalid_boundary_and_security_inputs(task_validation_client, payload):
    client, _runtime = task_validation_client

    response = client.post("/api/tasks/create", json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "not-an-object",
        {"name": None, "description": "d", "cron_expression": "* * * * *", "execution_mode": "script"},
        {"name": "x", "description": None, "cron_expression": "* * * * *", "execution_mode": "script"},
        {"name": "x", "description": "d", "execution_mode": "script"},
        {"name": "x", "description": "d", "cron_expression": "* * * * *", "execution_mode": None},
        {"name": 0, "description": "d", "cron_expression": "* * * * *", "execution_mode": "script"},
        {"name": "x", "description": 0, "cron_expression": "* * * * *", "execution_mode": "script"},
        {"name": "x", "description": "d", "cron_expression": 0, "execution_mode": "script"},
        {"name": "x", "description": "d", "cron_expression": "* * * * *", "execution_mode": 0},
        {"name": "x", "description": "d", "cron_expression": "* * * * *", "execution_mode": "SCRIPT"},
        {"name": "x", "description": "d", "cron_expression": "* * * * *", "execution_mode": "script", "payload": {}},
        {"name": "x", "description": "d", "cron_expression": "* * * * *", "execution_mode": "script", "started_at": {}},
        {"name": "x", "description": "d", "cron_expression": "* * * * *", "execution_mode": "script", "env_var_refs": {}},
        {"name": "x", "description": "d", "cron_expression": "* * * * *", "execution_mode": "script", "env_var_refs": [{"key": []}]},
    ],
)
def test_task_create_rejects_openapi_request_body_shape_errors(task_validation_client, payload):
    client, _runtime = task_validation_client

    response = client.post("/api/tasks/create", json=payload)

    assert response.status_code == 400


@pytest.mark.xfail(strict=True, reason="Known issue: task create/update accepts empty name and description.")
@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "description": "empty name", "cron_expression": "* * * * *", "execution_mode": "script"},
        {"name": "x", "description": "", "cron_expression": "* * * * *", "execution_mode": "script"},
    ],
)
def test_task_create_should_reject_empty_name_and_description(task_validation_client, payload):
    client, _runtime = task_validation_client

    response = client.post("/api/tasks/create", json=payload)

    assert response.status_code == 400


@pytest.mark.xfail(strict=True, reason="Known issue: task create ignores unexpected extra fields.")
def test_task_create_should_reject_extra_fields(task_validation_client):
    client, _runtime = task_validation_client

    response = client.post(
        "/api/tasks/create",
        json={
            "name": "Extra",
            "description": "d",
            "cron_expression": "* * * * *",
            "execution_mode": "script",
            "unexpected": "ignored",
        },
    )

    assert response.status_code == 400


@pytest.mark.xfail(strict=True, reason="Known issue: duplicate task env refs are accepted instead of rejected or deduplicated.")
def test_task_create_should_reject_duplicate_env_refs_after_normalization(task_validation_client):
    client, _runtime = task_validation_client

    response = client.post(
        "/api/tasks/create",
        json={
            "name": "Duplicate env refs",
            "description": "d",
            "cron_expression": "* * * * *",
            "execution_mode": "script",
            "env_var_refs": [{"key": "TOKEN"}, {"key": " TOKEN "}],
        },
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"name": "Min", "description": "d", "cron_expression": "* * * * *", "execution_mode": "script"}, []),
        ({"name": "With nulls", "description": "d", "cron_expression": "* * * * *", "execution_mode": "prompt", "payload": None, "env_var_refs": None, "started_at": None}, []),
        ({"name": "Trim refs", "description": "d", "cron_expression": "* * * * *", "execution_mode": "script", "env_var_refs": [{"key": " TOKEN_A "}, {"key": "TOKEN_B"}]}, [{"key": "TOKEN_A"}, {"key": "TOKEN_B"}]),
    ],
)
def test_task_create_accepts_positive_and_null_boundary_inputs(task_validation_client, payload, expected):
    client, runtime = task_validation_client

    response = client.post("/api/tasks/create", json=payload)

    assert response.status_code == 200
    assert response.json()["name"] == payload["name"]
    assert runtime.created_payloads[-1]["env_var_refs"] == expected


@pytest.mark.parametrize("cron_expression", [None, "", "   "])
def test_task_create_accepts_empty_cron_as_manual_only(task_validation_client, cron_expression):
    client, runtime = task_validation_client

    response = client.post(
        "/api/tasks/create",
        json={
            "name": "Manual only",
            "description": "Run on demand",
            "cron_expression": cron_expression,
            "execution_mode": "script",
        },
    )

    assert response.status_code == 200
    assert runtime.created_payloads[-1]["cron_expression"] is None


def test_task_create_accepts_implemented_text_length_boundaries(task_validation_client):
    client, _runtime = task_validation_client

    response = client.post(
        "/api/tasks/create",
        json={
            "name": "n" * 1024,
            "description": "d" * 1024,
            "cron_expression": "  */5 * * * *  ",
            "execution_mode": "script",
        },
    )

    assert response.status_code == 200
    assert response.json()["cron_expression"] == "*/5 * * * *"


@pytest.mark.parametrize("mode", ["prompt", "script"])
@pytest.mark.parametrize("cron_expression", ["* * * * *", "*/5 0 1 1 1"])
def test_task_create_accepts_declared_execution_modes_and_cron_boundaries(
    task_validation_client,
    mode,
    cron_expression,
):
    client, _runtime = task_validation_client

    response = client.post(
        "/api/tasks/create",
        json={
            "name": f"{mode}-{cron_expression}",
            "description": "d",
            "cron_expression": cron_expression,
            "execution_mode": mode,
            "payload": "",
            "env_var_refs": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["execution_mode"] == mode
    assert response.json()["cron_expression"] == cron_expression


@pytest.mark.xfail(strict=True, reason="Known issue: task API only checks cron field count, not semantic ranges.")
@pytest.mark.parametrize("cron_expression", ["61 * * * *", "0 24 * * *", "0 0 32 13 8"])
def test_task_create_should_reject_semantically_invalid_cron_ranges(task_validation_client, cron_expression):
    client, _runtime = task_validation_client

    response = client.post(
        "/api/tasks/create",
        json={"name": "Bad cron", "description": "d", "cron_expression": cron_expression, "execution_mode": "script"},
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        ("get", "/api/tasks", {"params": {"page": 0}}),
        ("get", "/api/tasks", {"params": {"page_size": 201}}),
        ("post", "/api/tasks", {"json": {"page": 0, "page_size": 20}}),
        ("post", "/api/tasks", {"json": {"page": 1, "page_size": 201}}),
        ("post", "/api/tasks/task-1", {"json": {}}),
        ("put", "/api/tasks/task-1", {"json": {"env_var_refs": ["KEY;rm -rf /"]}}),
        ("patch", "/api/tasks/task-1", {"json": {"extra": "forbidden"}}),
        ("patch", "/api/tasks/task-1", {"json": {"cron_expression": "* * * *"}}),
        ("post", "/api/tasks/task-1/runs", {"json": {"status": "done"}}),
        ("post", "/api/tasks/task-1/runs", {"json": {"trigger": "webhook"}}),
        ("get", "/api/tasks/task-1/runs", {"params": {"page": 0}}),
        ("get", "/api/runs/run-1/logs", {"params": {"page_size": 201}}),
        ("post", "/api/runs/run-1/complete", {"json": {"status": "done"}}),
        ("post", "/api/runs/run-1/complete", {"json": None}),
        ("post", "/api/runs/run-1/complete", {"json": {"status": "failed", "extra": "forbidden"}}),
    ],
)
def test_task_routes_reject_invalid_filters_updates_and_run_inputs(task_validation_client, method, url, kwargs):
    client, _runtime = task_validation_client

    response = getattr(client, method)(url, **kwargs)

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        ("get", "/api/tasks", {"params": {"page": "zero"}}),
        ("get", "/api/tasks", {"params": {"page_size": 0}}),
        ("get", "/api/tasks", {"params": {"status": "deleted"}}),
        ("post", "/api/tasks", {"json": None}),
        ("post", "/api/tasks", {"json": []}),
        ("post", "/api/tasks", {"json": {"page": "first"}}),
        ("post", "/api/tasks", {"json": {"page_size": 0}}),
        ("post", "/api/tasks", {"json": {"status": "archived"}}),
        ("get", "/api/tasks/task-1/runs", {"params": {"page": "first"}}),
        ("get", "/api/tasks/task-1/runs", {"params": {"page_size": 0}}),
        ("get", "/api/tasks/task-1/runs", {"params": {"status": "succeeded"}}),
        ("get", "/api/tasks/task-1/runs", {"params": {"trigger": "web"}}),
        ("post", "/api/tasks/task-1/runs", {"json": None}),
        ("post", "/api/tasks/task-1/runs", {"json": []}),
        ("post", "/api/tasks/task-1/runs", {"json": {"page": "first"}}),
        ("post", "/api/tasks/task-1/runs", {"json": {"page_size": 0}}),
        ("get", "/api/runs/run-1/logs", {"params": {"page": "first"}}),
        ("get", "/api/runs/run-1/logs", {"params": {"page_size": 0}}),
    ],
)
def test_task_list_run_list_and_logs_reject_openapi_query_and_body_shape_errors(
    task_validation_client,
    method,
    url,
    kwargs,
):
    client, _runtime = task_validation_client

    response = getattr(client, method)(url, **kwargs)

    assert response.status_code == 400


@pytest.mark.parametrize("status_filter", [None, "disabled", "enabled", "running"])
def test_task_list_accepts_declared_status_filters_and_extra_post_fields(task_validation_client, status_filter):
    client, _runtime = task_validation_client

    get_response = client.get("/api/tasks", params={"status": status_filter} if status_filter else {})
    post_response = client.post(
        "/api/tasks",
        json={"status": status_filter, "page": 1, "page_size": 200, "ignored_by_spec": {"safe": True}},
    )

    assert get_response.status_code == 200
    assert post_response.status_code == 200
    assert set(post_response.json()) == {"items", "total"}


@pytest.mark.parametrize("status_filter", [None, "pending", "running", "success", "failed", "cancelled"])
@pytest.mark.parametrize("trigger_filter", [None, "agent", "cron", "manual", "telegram"])
def test_task_runs_accept_declared_status_trigger_filters_and_extra_post_fields(
    task_validation_client,
    status_filter,
    trigger_filter,
):
    client, runtime = task_validation_client
    runtime.runs["agent-run"] = {
        **runtime.runs["run-1"],
        "id": "agent-run",
        "status": "failed",
        "trigger": "agent",
        "message": "boom",
    }
    params = {}
    if status_filter is not None:
        params["status"] = status_filter
    if trigger_filter is not None:
        params["trigger"] = trigger_filter

    get_response = client.get("/api/tasks/task-1/runs", params=params)
    post_response = client.post(
        "/api/tasks/task-1/runs",
        json={**params, "page": 1, "page_size": 200, "ignored_by_spec": ["safe"]},
    )

    assert get_response.status_code == 200
    assert post_response.status_code == 200
    assert get_response.json()["page_size"] == 20
    assert post_response.json()["page_size"] == 200


@pytest.mark.xfail(strict=True, reason="Known issue: task update accepts an empty name.")
def test_task_update_should_reject_empty_name(task_validation_client):
    client, _runtime = task_validation_client

    response = client.patch("/api/tasks/task-1", json={"name": ""})

    assert response.status_code == 400


def test_task_update_accepts_nullable_clear_fields_and_env_ref_arrays(task_validation_client):
    client, runtime = task_validation_client

    response = client.patch(
        "/api/tasks/task-1",
        json={
            "payload": None,
            "cron_expression": None,
            "env_var_refs": [],
            "started_at": None,
            "description": None,
        },
    )

    assert response.status_code == 200
    assert runtime.tasks["task-1"]["payload"] is None
    assert runtime.tasks["task-1"]["cron_expression"] is None
    assert runtime.tasks["task-1"]["env_var_refs"] == []
    assert runtime.tasks["task-1"]["started_at"] is None
    assert runtime.tasks["task-1"]["description"] is None


@pytest.mark.parametrize("cron_expression", ["", "   "])
def test_task_update_accepts_empty_cron_as_manual_only(task_validation_client, cron_expression):
    client, runtime = task_validation_client

    response = client.patch("/api/tasks/task-1", json={"cron_expression": cron_expression})

    assert response.status_code == 200
    assert runtime.tasks["task-1"]["cron_expression"] is None


def test_task_update_accepts_implemented_text_length_and_cron_trim_boundaries(task_validation_client):
    client, runtime = task_validation_client

    response = client.patch(
        "/api/tasks/task-1",
        json={
            "name": "n" * 1024,
            "description": "d" * 1024,
            "cron_expression": "  0 0 * * *  ",
        },
    )

    assert response.status_code == 200
    assert runtime.tasks["task-1"]["name"] == "n" * 1024
    assert runtime.tasks["task-1"]["description"] == "d" * 1024
    assert runtime.tasks["task-1"]["cron_expression"] == "0 0 * * *"


@pytest.mark.parametrize("method", ["post", "put", "patch"])
@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Renamed"},
        {"description": "Updated"},
        {"execution_mode": "prompt"},
        {"execution_mode": "script"},
        {"payload": ""},
        {"cron_expression": "*/10 * * * *"},
        {"env_var_refs": [{"key": "TOKEN_A"}]},
        {"started_at": "2026-05-14T00:00:00+00:00"},
    ],
)
def test_task_update_aliases_accept_each_declared_field(task_validation_client, method, payload):
    client, _runtime = task_validation_client

    response = getattr(client, method)("/api/tasks/task-1", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch"])
@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"name": []},
        {"description": {}},
        {"execution_mode": "binary"},
        {"payload": []},
        {"cron_expression": "* * * *"},
        {"env_var_refs": {}},
        {"env_var_refs": [{"key": "../TOKEN"}]},
        {"started_at": {}},
        {"unexpected": "forbidden"},
    ],
)
def test_task_update_aliases_reject_invalid_type_enum_null_and_security_inputs(
    task_validation_client,
    method,
    payload,
):
    client, _runtime = task_validation_client

    response = getattr(client, method)("/api/tasks/task-1", json=payload)

    assert response.status_code == 400


def test_task_list_and_run_filters_page_beyond_total_return_empty_items(task_validation_client):
    client, runtime = task_validation_client
    runtime.tasks["task-disabled"] = {
        **runtime.tasks["task-1"],
        "id": "task-disabled",
        "name": "Disabled",
        "status": "disabled",
    }
    runtime.runs["failed-agent"] = {
        **runtime.runs["run-1"],
        "id": "failed-agent",
        "status": "failed",
        "trigger": "agent",
        "message": "boom",
        "override_prompt": "agent override",
    }

    disabled_tasks = client.get("/api/tasks", params={"status": "disabled"})
    missing_page = client.get("/api/tasks", params={"page": 99, "page_size": 20})
    failed_agent_runs = client.get(
        "/api/tasks/task-1/runs",
        params={"status": "failed", "trigger": "agent"},
    )
    empty_runs_page = client.post("/api/tasks/task-1/runs", json={"page": 99, "page_size": 10})

    assert disabled_tasks.status_code == 200
    assert disabled_tasks.json()["items"][0]["id"] == "task-disabled"
    assert missing_page.status_code == 200
    assert missing_page.json()["items"] == []
    assert missing_page.json()["total"] == 2
    assert failed_agent_runs.status_code == 200
    assert failed_agent_runs.json()["items"][0]["id"] == "failed-agent"
    assert failed_agent_runs.json()["items"][0]["error_message"] == "boom"
    assert empty_runs_page.status_code == 200
    assert empty_runs_page.json()["items"] == []


def test_task_trigger_trims_override_prompt_and_selects_agent_or_manual(task_validation_client):
    client, runtime = task_validation_client

    manual = client.post("/api/tasks/task-1/trigger", json={"override_prompt": "   "})
    agent = client.post("/api/tasks/task-1/trigger", json={"override_prompt": "  run this instead  "})

    assert manual.status_code == 200
    assert agent.status_code == 200
    assert runtime.trigger_calls[0] == {"trigger": "manual", "override_prompt": None}
    assert runtime.trigger_calls[1] == {"trigger": "agent", "override_prompt": "run this instead"}
    assert runtime.runs["run-1"]["trigger"] == "agent"
    assert runtime.runs["run-1"]["override_prompt"] == "run this instead"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"override_prompt": None},
        {"override_prompt": ""},
        {"override_prompt": "  "},
        {"override_prompt": "manual override"},
        {"override_prompt": "<script>alert(1)</script>", "extra": {"allowed": True}},
    ],
)
def test_task_trigger_accepts_spec_nullable_and_extra_body_fields(task_validation_client, payload):
    client, _runtime = task_validation_client

    response = client.post("/api/tasks/task-1/trigger", json=payload)

    assert response.status_code == 200
    assert set(response.json()) == {"id", "run_id", "message", "status"}


def test_run_complete_status_and_error_message_visibility(task_validation_client):
    client, runtime = task_validation_client
    runtime.runs["success-run"] = {**runtime.runs["run-1"], "id": "success-run", "status": "running"}
    runtime.runs["failed-run"] = {**runtime.runs["run-1"], "id": "failed-run", "status": "running"}

    success = client.post("/api/runs/success-run/complete", json={"status": "success", "error_message": "hidden"})
    failed = client.post("/api/runs/failed-run/complete", json={"status": "failed", "error_message": "visible failure"})

    assert success.status_code == 200
    assert success.json()["status"] == "success"
    assert success.json()["error_message"] is None
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["error_message"] == "visible failure"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"status": None},
        {"status": "cancelled"},
        {"status": "succeeded"},
        {"status": "success", "error_message": []},
        {"status": "failed", "error_message": {}},
        {"status": "failed", "unexpected": "forbidden"},
    ],
)
def test_run_complete_rejects_missing_enum_type_and_extra_fields(task_validation_client, payload):
    client, _runtime = task_validation_client

    response = client.post("/api/runs/run-1/complete", json=payload)

    assert response.status_code == 400


def test_run_logs_pagination_and_malformed_log_coercion(task_validation_client):
    client, runtime = task_validation_client
    runtime.runs["run-1"]["logs"] = [
        "not-a-dict",
        {
            "id": "bad-log",
            "log_type": "not_real",
            "status": "weird",
            "metadata": "not-a-dict",
            "content": "coerced",
        },
        {"id": "stderr-log", "log_type": "script_stderr", "status": "failed", "content": "err", "metadata": {}},
    ]

    first_page = client.get("/api/runs/run-1/logs", params={"page": 1, "page_size": 2})
    second_page = client.get("/api/runs/run-1/logs", params={"page": 2, "page_size": 2})
    beyond_total = client.get("/api/runs/run-1/logs", params={"page": 99, "page_size": 20})

    assert first_page.status_code == 200
    assert first_page.json()[0]["id"] == "bad-log"
    assert first_page.json()[0]["log_type"] == "script_stdout"
    assert first_page.json()[0]["status"] == "success"
    assert first_page.json()[0]["metadata"] == {}
    assert second_page.status_code == 200
    assert second_page.json()[0]["id"] == "stderr-log"
    assert second_page.json()[0]["status"] == "failed"
    assert beyond_total.status_code == 200
    assert beyond_total.json() == []


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        ("get", "/api/tasks/missing", {}),
        ("post", "/api/tasks/missing/trigger", {"json": {}}),
        ("post", "/api/tasks/missing/enable", {}),
        ("post", "/api/tasks/missing/disable", {}),
        ("delete", "/api/tasks/missing", {}),
        ("get", "/api/runs/missing", {}),
        ("get", "/api/runs/missing/logs", {}),
        ("post", "/api/runs/missing/cancel", {}),
        ("post", "/api/runs/missing/complete", {"json": {"status": "success"}}),
    ],
)
def test_task_routes_report_missing_resources(task_validation_client, method, url, kwargs):
    client, _runtime = task_validation_client

    response = getattr(client, method)(url, **kwargs)

    assert response.status_code in {400, 404}


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        ("post", "/api/runs/terminal-run/cancel", {}),
        ("post", "/api/runs/terminal-run/complete", {"json": {"status": "success"}}),
    ],
)
def test_task_routes_reject_terminal_run_mutation(task_validation_client, method, url, kwargs):
    client, _runtime = task_validation_client

    response = getattr(client, method)(url, **kwargs)

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        (
            "post",
            "/api/tasks/create",
            {"json": {"name": "x", "description": "d", "cron_expression": "* * * * *", "execution_mode": "script"}},
        ),
        ("post", "/api/tasks", {"json": {}}),
        ("get", "/api/tasks", {}),
        ("get", "/api/tasks/task-1", {}),
        ("post", "/api/tasks/task-1", {"json": {"name": "x"}}),
        ("put", "/api/tasks/task-1", {"json": {"name": "x"}}),
        ("patch", "/api/tasks/task-1", {"json": {"name": "x"}}),
        ("delete", "/api/tasks/task-1", {}),
        ("post", "/api/tasks/task-1/enable", {}),
        ("post", "/api/tasks/task-1/disable", {}),
        ("post", "/api/tasks/task-1/trigger", {"json": {}}),
        ("get", "/api/tasks/task-1/runs", {}),
        ("post", "/api/tasks/task-1/runs", {"json": {}}),
        ("post", "/api/runs/run-1/cancel", {}),
        ("post", "/api/runs/run-1/complete", {"json": {"status": "success"}}),
        ("get", "/api/runs/run-1", {}),
        ("get", "/api/runs/run-1/logs", {}),
    ],
)
def test_task_operations_return_declared_500_when_runtime_raises(exploding_task_client, method, url, kwargs):
    response = getattr(exploding_task_client, method)(url, **kwargs)

    assert response.status_code == 500
