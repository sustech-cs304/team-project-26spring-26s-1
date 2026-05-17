from __future__ import annotations

import pytest

from agent.services.notification_service import Deeplink


pytestmark = pytest.mark.unit


def test_deeplink_builder_encodes_query_parameters():
    deeplink = Deeplink.route(
        "tasks",
        "task-1",
        action="view history",
        tab="logs",
        query={"tag": ["a", "b"]},
    )

    assert deeplink.url == "opencrab://tasks/task-1?tag=a&tag=b&action=view+history&tab=logs"

    with pytest.raises(ValueError):
        Deeplink.route("   ")


@pytest.mark.xfail(strict=True, reason="Known issue: deeplink entity_id is interpolated without path encoding.")
def test_deeplink_builder_encodes_route_entity_id():
    deeplink = Deeplink.route(
        "tasks",
        "task 1",
        action="view history",
        tab="logs",
        query={"tag": ["a", "b"]},
    )

    assert deeplink.url == "opencrab://tasks/task%201?tag=a&tag=b&action=view+history&tab=logs"
