from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent.api.notifications import router as notifications_router
from agent.services.notification_service import Deeplink, NotificationLevel


pytestmark = pytest.mark.component


class FakeNotificationService:
    def __init__(self) -> None:
        self.sent = []

    async def send_async(self, notification):
        self.sent.append(notification)
        return "notification-1"

    def build_deeplink(self, resource, entity_id=None, *, action=None, tab=None, query=None):
        return Deeplink.route(
            resource,
            entity_id,
            scheme="opencrab",
            action=action,
            tab=tab,
            query=query,
        )


def test_notifications_router_dispatches_to_service_and_previews_deeplink(app_factory):
    service = FakeNotificationService()
    app = app_factory()
    app.state.NotificationService = service
    app.include_router(notifications_router, prefix="/api")
    client = TestClient(app)

    response = client.post(
        "/api/notifications/dispatch",
        json={
            "title": "Task finished",
            "message": "The run completed.",
            "level": "success",
            "deeplink": "opencrab://runs/run-1?tab=logs",
            "actions": [{"title": "Open", "deeplink": "opencrab://tasks/task-1"}],
            "thread": "task:task-1",
            "timeout_s": 5,
        },
    )
    preview = client.get(
        "/api/notifications/deeplink-preview/tasks",
        params={"entity_id": "task-1", "action": "history", "tab": "logs"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "scheduled", "notification_id": "notification-1"}
    assert service.sent[0].level is NotificationLevel.success
    assert service.sent[0].actions[0].title == "Open"
    assert preview.status_code == 200
    assert preview.json()["deeplink"] == "opencrab://tasks/task-1?action=history&tab=logs"


def test_notifications_router_returns_503_when_service_is_unavailable(app_factory):
    app = app_factory()
    app.include_router(notifications_router, prefix="/api")

    response = TestClient(app).post(
        "/api/notifications/dispatch",
        json={"title": "x", "message": "y"},
    )

    assert response.status_code == 503
