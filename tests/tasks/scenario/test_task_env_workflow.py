from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

import agent.api.task as task_api
from agent.api.env_vars import router as env_vars_router
from agent.api.task import router as task_router
from agent.services.task_runtime import TaskRuntimeService


pytestmark = pytest.mark.scenario


def test_env_var_to_task_run_to_logs_scenario(
    app_factory,
    temp_default_db,
    monkeypatch,
    run_async,
):
    runtime = TaskRuntimeService(temp_default_db, default_timeout_s=5, max_concurrent=1)
    monkeypatch.setattr(task_api, "get_task_runtime", lambda: runtime)

    app = app_factory()
    app.include_router(env_vars_router, prefix="/api")
    app.include_router(task_router, prefix="/api")

    try:
        with TestClient(app) as client:
            env_response = client.post(
                "/api/env-vars",
                json={"key": "OPENCRAB_SCENARIO_TOKEN", "value": "scenario-secret"},
            )
            create_response = client.post(
                "/api/tasks/create",
                json={
                    "name": "Scenario task",
                    "description": "Reads an env var and prints it",
                    "cron_expression": "* * * * *",
                    "execution_mode": "script",
                    "payload": (
                        "import os\n"
                        "print('token=' + os.environ['OPENCRAB_SCENARIO_TOKEN'])\n"
                    ),
                    "env_var_refs": [{"key": "OPENCRAB_SCENARIO_TOKEN"}],
                },
            )
            task_id = create_response.json()["id"]
            trigger_response = client.post(f"/api/tasks/{task_id}/trigger", json={})
            run_id = trigger_response.json()["run_id"]

            detail = None
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                detail_response = client.get(f"/api/runs/{run_id}")
                assert detail_response.status_code == 200
                detail = detail_response.json()
                if detail["status"] != "running":
                    break
                time.sleep(0.05)

            logs_response = client.get(f"/api/runs/{run_id}/logs")
            runs_response = client.get(f"/api/tasks/{task_id}/runs")
            delete_response = client.delete(f"/api/tasks/{task_id}")
            env_delete_response = client.delete("/api/env-vars/OPENCRAB_SCENARIO_TOKEN")

        assert env_response.status_code == 200
        assert create_response.status_code == 200
        assert trigger_response.status_code == 200
        assert detail is not None
        assert detail["status"] == "success"
        assert any(log.get("content") == "token=scenario-secret" for log in detail["logs"])
        assert logs_response.status_code == 200
        assert any(log.get("content") == "token=scenario-secret" for log in logs_response.json())
        assert runs_response.json()["total"] == 1
        assert runs_response.json()["items"][0]["id"] == run_id
        assert delete_response.status_code == 200
        assert env_delete_response.status_code == 200
    finally:
        run_async(runtime.aclose())
