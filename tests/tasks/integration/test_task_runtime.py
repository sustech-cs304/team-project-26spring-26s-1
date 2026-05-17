from __future__ import annotations

import asyncio
from datetime import timedelta, timezone

import pytest

import agent.services.task_runtime as task_runtime_module
from agent.services.task_runtime import TaskRuntimeService


pytestmark = pytest.mark.integration


def test_task_runtime_executes_script_and_persists_run_logs(
    sqlite_session_factory,
    monkeypatch,
    run_async,
):
    async def fake_read_credential_values(credential_type: str):
        assert credential_type == "env_var"
        return {"OPENCRAB_TEST_TOKEN": "secret-value"}

    monkeypatch.setattr(
        task_runtime_module,
        "read_credential_values",
        fake_read_credential_values,
    )
    monkeypatch.setattr(task_runtime_module, "_user_timezone", lambda: timezone(timedelta(hours=8)))

    async def _scenario():
        runtime = TaskRuntimeService(
            sqlite_session_factory,
            default_timeout_s=5,
            max_concurrent=1,
        )
        try:
            task = await runtime.create_task(
                name="Script task",
                description="Runs a small script",
                cron_expression="* * * * *",
                execution_mode="script",
                payload=(
                    "import os\n"
                    "print('stdout:' + os.environ['OPENCRAB_TEST_TOKEN'])\n"
                ),
                env_var_refs=[{"key": "OPENCRAB_TEST_TOKEN"}],
                started_at=None,
            )
            manual_time_task = await runtime.create_task(
                name="Manual time task",
                description="Preserves user timezone on output",
                cron_expression=None,
                execution_mode="script",
                payload="print('ok')",
                env_var_refs=[],
                started_at="2026-05-15T09:00:00+08:00",
            )
            manual_time_task_after = await runtime.get_task(manual_time_task["id"])

            assert task["created_at"].endswith("+08:00")
            assert manual_time_task["started_at"] == "2026-05-15T09:00:00+08:00"
            assert manual_time_task_after is not None
            assert manual_time_task_after["started_at"] == "2026-05-15T09:00:00+08:00"

            run = await runtime.trigger_task(task["id"], trigger="manual", timeout_s=5)
            assert run is not None

            detail = None
            for _ in range(100):
                detail = await runtime.get_run(run["id"])
                if detail and detail["status"] != "running":
                    break
                await asyncio.sleep(0.05)
            else:
                pytest.fail("Timed out waiting for task run to finish")

            assert detail is not None
            assert detail["status"] == "succeeded"
            assert detail["trigger"] == "manual"
            assert detail["started_at"].endswith("+08:00")
            assert detail["logs"][0]["timestamp"].endswith("+08:00")
            assert any(
                log.get("log_type") == "script_stdout"
                and log.get("content") == "stdout:secret-value"
                for log in detail["logs"]
            )
            assert detail["logs"][0]["metadata"]["injected_env_keys"] == ["OPENCRAB_TEST_TOKEN"]

            task_after = None
            for _ in range(100):
                task_after = await runtime.get_task(task["id"])
                if task_after and task_after["status"] != "running":
                    break
                await asyncio.sleep(0.05)
            assert task_after is not None
            assert task_after["status"] == "enabled"
            assert task_after["last_run_status"] == "success"
            assert task_after["last_run_at"].endswith("+08:00")

            history = await runtime.list_runs_for_task(task["id"])
            assert len(history) == 1
            assert history[0]["id"] == run["id"]
            assert history[0]["started_at"].endswith("+08:00")
        finally:
            await runtime.aclose()

    run_async(_scenario())
