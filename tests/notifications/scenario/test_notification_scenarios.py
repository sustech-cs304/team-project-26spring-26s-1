from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent.api.notifications import router as notifications_router
from agent.services.notification_service import Deeplink, NotificationLevel


pytestmark = pytest.mark.scenario


class ScenarioNotificationService:
    def __init__(self):
        self.sent = []

    async def send_async(self, notification):
        self.sent.append(notification)
        return f"notification-{len(self.sent)}"

    def build_deeplink(self, resource, entity_id=None, *, action=None, tab=None, query=None):
        return Deeplink.route(
            resource,
            entity_id,
            scheme="opencrab",
            action=action,
            tab=tab,
            query=query,
        )


def test_notification_preview_to_dispatch_with_action_scenario(app_factory):
    service = ScenarioNotificationService()
    app = app_factory()
    app.state.NotificationService = service
    app.include_router(notifications_router, prefix="/api")
    client = TestClient(app)

    preview = client.get(
        "/api/notifications/deeplink-preview/tasks",
        params={"entity_id": "task-1", "action": "history", "tab": "logs"},
    )
    deeplink = preview.json()["deeplink"]
    dispatched = client.post(
        "/api/notifications/dispatch",
        json={
            "title": "Task finished",
            "message": "Scenario task completed.",
            "level": "success",
            "deeplink": deeplink,
            "actions": [{"title": "Open logs", "deeplink": deeplink}],
            "thread": "task:task-1",
            "timeout_s": 10,
        },
    )

    assert preview.status_code == 200
    assert deeplink == "opencrab://tasks/task-1?action=history&tab=logs"
    assert dispatched.status_code == 200
    assert dispatched.json() == {"status": "scheduled", "notification_id": "notification-1"}
    assert service.sent[0].title == "Task finished"
    assert service.sent[0].level is NotificationLevel.success
    assert service.sent[0].deeplink == deeplink
    assert service.sent[0].actions[0].deeplink == deeplink
