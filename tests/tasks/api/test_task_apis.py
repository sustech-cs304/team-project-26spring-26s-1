from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import agent.api.task as task_api
from agent.api.task import router as task_router


pytestmark = pytest.mark.api


class FakeFullTaskRuntime:
    def __init__(self):
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
                "started_at": None,
                "last_run_at": None,
                "last_run_status": None,
                "last_run_trigger": None,
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
                "logs": [
                    {
                        "id": "log-1",
                        "run_id": "run-1",
                        "step_index": 1,
                        "log_type": "script_start",
                        "duration_ms": 0,
                        "status": "success",
                        "timestamp": "2026-05-14T00:01:00+00:00",
                        "metadata": {"platform": "test"},
                    },
                    {
                        "id": "log-2",
                        "run_id": "run-1",
                        "step_index": 2,
                        "log_type": "script_stdout",
                        "duration_ms": 0,
                        "status": "success",
                        "timestamp": "2026-05-14T00:01:01+00:00",
                        "content": "hello",
                        "metadata": {},
                    },
                ],
            }
        }

    async def list_tasks(self, *, status=None, page=1, page_size=20):
        rows = [task for task in self.tasks.values() if status is None or task["status"] == status]
        return rows[(page - 1) * page_size : page * page_size], len(rows)

    async def get_task(self, task_id):
        return self.tasks.get(task_id)

    async def update_task(self, task_id, updates):
        task = self.tasks.get(task_id)
        if task is None:
            return None
        task.update(updates)
        task["updated_at"] = "2026-05-14T00:02:00+00:00"
        return task

    async def set_task_enabled(self, task_id, enabled):
        task = self.tasks.get(task_id)
        if task is None:
            return None
        task["status"] = "enabled" if enabled else "disabled"
        return task

    async def trigger_task(self, task_id, *, trigger, override_prompt=None):
        if task_id not in self.tasks:
            return None
        run = {
            **self.runs["run-1"],
            "id": "run-2",
            "trigger": trigger,
            "override_prompt": override_prompt,
        }
        self.runs["run-2"] = run
        return run

    async def list_runs_for_task(self, task_id):
        return [run for run in self.runs.values() if run["task_id"] == task_id]

    async def get_run(self, run_id):
        return self.runs.get(run_id)

    async def cancel_run(self, run_id):
        run = self.runs.get(run_id)
        if run is None:
            return None
        run["status"] = "cancelled"
        run["finished_at"] = "2026-05-14T00:03:00+00:00"
        run["message"] = "Cancelled by user."
        return run

    async def complete_run(self, run_id, status, error_message):
        run = self.runs.get(run_id)
        if run is None:
            return None
        run["status"] = "succeeded" if status == "success" else "failed"
        run["finished_at"] = "2026-05-14T00:03:00+00:00"
        run["message"] = error_message
        return run

    async def delete_task(self, task_id):
        return self.tasks.pop(task_id, None) is not None


def test_task_api_full_management_surface(app_factory, monkeypatch):
    runtime = FakeFullTaskRuntime()
    monkeypatch.setattr(task_api, "get_task_runtime", lambda: runtime)
    app = app_factory()
    app.include_router(task_router, prefix="/api")
    client = TestClient(app)

    listed_get = client.get("/api/tasks")
    listed_post = client.post("/api/tasks", json={"status": "enabled", "page": 1, "page_size": 10})
    detail = client.get("/api/tasks/task-1")
    updated = client.patch("/api/tasks/task-1", json={"name": "Renamed", "env_var_refs": [{"key": "TOKEN"}]})
    updated_put = client.put("/api/tasks/task-1", json={"description": "Updated by PUT"})
    updated_post = client.post("/api/tasks/task-1", json={"payload": "print('post alias')"})
    empty_update = client.patch("/api/tasks/task-1", json={})
    disabled = client.post("/api/tasks/task-1/disable")
    enabled = client.post("/api/tasks/task-1/enable")
    triggered = client.post("/api/tasks/task-1/trigger", json={"override_prompt": "agent says run"})
    runs_get = client.get("/api/tasks/task-1/runs")
    runs_post = client.post("/api/tasks/task-1/runs", json={"trigger": "manual"})
    run_detail = client.get("/api/runs/run-1")
    run_logs = client.get("/api/runs/run-1/logs", params={"page": 1, "page_size": 1})
    completed = client.post("/api/runs/run-1/complete", json={"status": "success"})
    cancelled = client.post("/api/runs/run-2/cancel")
    deleted = client.delete("/api/tasks/task-1")
    missing_detail = client.get("/api/tasks/task-1")

    assert listed_get.status_code == 200
    assert listed_get.json()["total"] == 1
    assert listed_post.status_code == 200
    assert detail.json()["name"] == "Daily sync"
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["env_var_refs"] == [{"key": "TOKEN"}]
    assert updated_put.json()["description"] == "Updated by PUT"
    assert updated_post.json()["payload"] == "print('post alias')"
    assert empty_update.status_code == 400
    assert disabled.json() == {"id": "task-1", "status": "disabled", "message": "Task disabled."}
    assert enabled.json() == {"id": "task-1", "status": "enabled", "message": "Task enabled."}
    assert triggered.status_code == 200
    assert triggered.json()["run_id"] == "run-2"
    assert runs_get.json()["total"] >= 1
    assert runs_post.json()["items"][0]["trigger"] == "manual"
    assert run_detail.json()["logs"][1]["content"] == "hello"
    assert run_logs.json()[0]["log_type"] == "script_start"
    assert completed.json()["status"] == "success"
    assert cancelled.json()["status"] == "cancelled"
    assert deleted.status_code == 200
    assert missing_detail.status_code == 404


def test_task_run_terminal_and_missing_states_return_errors(app_factory, monkeypatch):
    runtime = FakeFullTaskRuntime()
    runtime.runs["terminal"] = {**runtime.runs["run-1"], "id": "terminal", "status": "succeeded"}
    monkeypatch.setattr(task_api, "get_task_runtime", lambda: runtime)
    app = app_factory()
    app.include_router(task_router, prefix="/api")
    client = TestClient(app)

    missing_task_runs = client.get("/api/tasks/missing/runs")
    missing_run = client.get("/api/runs/missing")
    terminal_cancel = client.post("/api/runs/terminal/cancel")
    bad_complete_payload = client.post("/api/runs/run-1/complete", json={"status": "cancelled"})

    assert missing_task_runs.status_code == 400
    assert missing_run.status_code == 404
    assert terminal_cancel.status_code == 404
    assert bad_complete_payload.status_code == 400
