from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks

from agent.api import profile


pytestmark = pytest.mark.api


@pytest.fixture(autouse=True)
def reset_profile_update_state():
    profile._profile_update_underway = False
    yield
    profile._profile_update_underway = False


def _request(store=object(), session_factory=object()):
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                agent_store=store,
                async_session=session_factory,
            ),
        ),
    )


def test_profile_update_schedules_one_background_task_while_underway(
    monkeypatch,
    run_async,
):
    calls = []

    async def fake_delete(_store, _key):
        calls.append("delete")

    async def fake_get(_session_factory, _key):
        calls.append("get")
        return ""

    async def exercise():
        monkeypatch.setattr(profile, "_delete_core_memory_entry_if_exists", fake_delete)
        monkeypatch.setattr(profile, "_get_kv_string", fake_get)

        first_tasks = BackgroundTasks()
        first_response = await profile.update_profile(_request(), first_tasks)

        second_tasks = BackgroundTasks()
        second_response = await profile.update_profile(_request(), second_tasks)

        assert first_response == {}
        assert second_response == {}
        assert len(first_tasks.tasks) == 1
        assert len(second_tasks.tasks) == 0
        assert profile._profile_update_underway is True

        await first_tasks()

    run_async(exercise())

    assert calls == ["delete", "get"]
    assert profile._profile_update_underway is False


def test_profile_update_background_failure_resets_underway_flag(
    monkeypatch,
    run_async,
):
    async def fake_delete(_store, _key):
        raise RuntimeError("profile store unavailable")

    async def exercise():
        monkeypatch.setattr(profile, "_delete_core_memory_entry_if_exists", fake_delete)
        profile._profile_update_underway = True

        await profile._update_profile_background(object(), object())

    run_async(exercise())

    assert profile._profile_update_underway is False
