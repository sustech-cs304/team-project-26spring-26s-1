from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import agent.api.task as task_api
from agent.api.env_vars import router as env_vars_router
from agent.api.task import router as task_router
from agent.services.task_runtime import TaskRuntimeService


pytestmark = pytest.mark.integration


def test_env_vars_api_round_trip_uses_encrypted_temp_database(app_factory, temp_default_db):
    app = app_factory()
    app.include_router(env_vars_router, prefix="/api")
    client = TestClient(app)

    create = client.post(
        "/api/env-vars",
        json={"key": " OPENCRAB_TOKEN ", "value": "super-secret"},
    )
    listed = client.get("/api/env-vars")
    bad = client.post(
        "/api/env-vars",
        json={"key": "OPENCRAB_TOKEN;DROP TABLE credentials", "value": "x"},
    )
    deleted = client.delete("/api/env-vars/OPENCRAB_TOKEN")
    missing = client.delete("/api/env-vars/OPENCRAB_TOKEN")

    assert create.status_code == 200
    assert create.json() == {"key": "OPENCRAB_TOKEN"}
    assert listed.status_code == 200
    assert listed.json() == [{"key": "OPENCRAB_TOKEN"}]
    assert "super-secret" not in listed.text
    assert bad.status_code == 400
    assert deleted.status_code == 200
    assert missing.status_code == 404


@pytest.mark.xfail(strict=True, reason="Known issue: env var delete does not check whether tasks still reference the key.")
def test_env_var_delete_should_conflict_when_referenced_by_task(
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
            created_env = client.post("/api/env-vars", json={"key": "REFERENCED_TOKEN", "value": "secret"})
            created_task = client.post(
                "/api/tasks/create",
                json={
                    "name": "References env",
                    "description": "Keeps env var referenced",
                    "cron_expression": "* * * * *",
                    "execution_mode": "script",
                    "payload": "print('ok')",
                    "env_var_refs": [{"key": "REFERENCED_TOKEN"}],
                },
            )
            deleted_env = client.delete("/api/env-vars/REFERENCED_TOKEN")

        assert created_env.status_code == 200
        assert created_task.status_code == 200
        assert deleted_env.status_code == 409
        assert deleted_env.json()["referenced_by"][0]["task_name"] == "References env"
    finally:
        run_async(runtime.aclose())
