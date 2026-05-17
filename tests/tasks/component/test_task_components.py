from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import agent.api.task as task_api
from agent.api.task import router as task_router


pytestmark = pytest.mark.component


class FakeTaskRuntime:
    def __init__(self) -> None:
        self.created_tasks: list[dict] = []
        self.trigger_calls: list[dict] = []

    async def create_task(self, **kwargs):
        task = {
            "id": f"task-{len(self.created_tasks) + 1}",
            "created_at": "2026-05-14T00:00:00+00:00",
            "updated_at": "2026-05-14T00:00:00+00:00",
            "started_at": kwargs.get("started_at"),
            "last_run_at": None,
            "last_run_status": None,
            "last_run_trigger": None,
            "status": "enabled",
            **kwargs,
        }
        self.created_tasks.append(task)
        return task

    async def trigger_task(self, task_id: str, *, trigger: str, override_prompt: str | None = None):
        self.trigger_calls.append(
            {
                "task_id": task_id,
                "trigger": trigger,
                "override_prompt": override_prompt,
            }
        )
        return {"id": "run-1", "task_id": task_id, "status": "running"}


def _client(app_factory, monkeypatch):
    runtime = FakeTaskRuntime()
    monkeypatch.setattr(task_api, "get_task_runtime", lambda: runtime)
    app = app_factory()
    app.include_router(task_router, prefix="/api")
    return TestClient(app), runtime


def test_task_router_accepts_create_payload_and_rejects_unsafe_env_key(app_factory, monkeypatch):
    client, runtime = _client(app_factory, monkeypatch)

    response = client.post(
        "/api/tasks/create",
        json={
            "name": "Nightly sync",
            "description": "Pull school events",
            "cron_expression": "*/15 * * * *",
            "execution_mode": "script",
            "payload": "print('ok')",
            "env_var_refs": [{"key": "OPENCRAB_TOKEN"}, {"key": " OPENCRAB_TOKEN "}],
        },
    )
    bad_response = client.post(
        "/api/tasks/create",
        json={
            "name": "x",
            "description": "x",
            "cron_expression": "* * * * *",
            "execution_mode": "script",
            "env_var_refs": [{"key": "OPENCRAB_TOKEN;DROP TABLE credentials"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["env_var_refs"] == [{"key": "OPENCRAB_TOKEN"}, {"key": "OPENCRAB_TOKEN"}]
    assert runtime.created_tasks[0]["payload"] == "print('ok')"
    assert bad_response.status_code == 400


@pytest.mark.xfail(strict=True, reason="Known issue: duplicate task env_var_refs are not deduplicated.")
def test_task_router_deduplicates_env_var_refs(app_factory, monkeypatch):
    client, _ = _client(app_factory, monkeypatch)

    response = client.post(
        "/api/tasks/create",
        json={
            "name": "Nightly sync",
            "description": "Pull school events",
            "cron_expression": "*/15 * * * *",
            "execution_mode": "script",
            "env_var_refs": [{"key": "OPENCRAB_TOKEN"}, {"key": " OPENCRAB_TOKEN "}],
        },
    )

    assert response.json()["env_var_refs"] == [{"key": "OPENCRAB_TOKEN"}]


@pytest.mark.xfail(strict=True, reason="Known issue: task API only checks cron field count, not semantic ranges.")
def test_task_router_rejects_semantically_invalid_cron(app_factory, monkeypatch):
    client, _ = _client(app_factory, monkeypatch)

    bad_cron = client.post(
        "/api/tasks/create",
        json={
            "name": "x",
            "description": "x",
            "cron_expression": "61 * * * *",
            "execution_mode": "script",
        },
    )

    assert bad_cron.status_code == 400


def test_task_trigger_marks_agent_trigger_only_when_override_prompt_is_present(app_factory, monkeypatch):
    client, runtime = _client(app_factory, monkeypatch)

    manual_response = client.post("/api/tasks/task-1/trigger", json={})
    agent_response = client.post("/api/tasks/task-1/trigger", json={"override_prompt": "run now"})

    assert manual_response.status_code == 200
    assert agent_response.status_code == 200
    assert runtime.trigger_calls[0]["trigger"] == "manual"
    assert runtime.trigger_calls[1]["trigger"] == "agent"
    assert runtime.trigger_calls[1]["override_prompt"] == "run now"
