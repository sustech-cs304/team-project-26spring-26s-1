from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import agent.services.task_runtime as task_runtime_module
from agent.services.task_runtime import CronMatcher


pytestmark = pytest.mark.unit


def test_cron_matcher_matches_valid_expression():
    matcher = CronMatcher("*/15 9-17 * * 1-5")

    assert matcher.matches(datetime(2026, 5, 14, 9, 30))
    assert not matcher.matches(datetime(2026, 5, 14, 9, 31))


def test_task_timestamps_serialize_in_user_timezone(monkeypatch):
    monkeypatch.setattr(task_runtime_module, "_user_timezone", lambda: timezone(timedelta(hours=8)))

    assert (
        task_runtime_module._dt_to_iso(datetime(2026, 5, 14, 0, 30, tzinfo=timezone.utc))
        == "2026-05-14T08:30:00+08:00"
    )
    assert task_runtime_module._dt_to_iso(datetime(2026, 5, 14, 0, 30)) == "2026-05-14T08:30:00+08:00"


def test_task_started_at_inputs_are_normalized_to_utc_storage(monkeypatch):
    monkeypatch.setattr(task_runtime_module, "_user_timezone", lambda: timezone(timedelta(hours=8)))

    assert task_runtime_module._parse_dt("2026-05-15T09:00:00+08:00") == datetime(
        2026,
        5,
        15,
        1,
        0,
        tzinfo=timezone.utc,
    )
    assert task_runtime_module._parse_dt("2026-05-15T09:00:00") == datetime(
        2026,
        5,
        15,
        1,
        0,
        tzinfo=timezone.utc,
    )


@pytest.mark.xfail(strict=True, reason="Known issue: CronMatcher accepts out-of-range fields and zero steps.")
def test_cron_matcher_rejects_malformed_ranges():
    for expression in ["61 * * * *", "*/0 * * * *", "5-1 * * * *", "* * * * 8", "* * *"]:
        with pytest.raises(ValueError):
            CronMatcher(expression)
