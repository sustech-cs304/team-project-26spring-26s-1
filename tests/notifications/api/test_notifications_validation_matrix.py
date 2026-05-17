from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent.api.notifications import router as notifications_router
from agent.services.notification_service import Deeplink


pytestmark = pytest.mark.api


class RecordingNotificationService:
    def __init__(self):
        self.sent = []

    async def send_async(self, notification):
        self.sent.append(notification)
        return "notification-1"

    def build_deeplink(self, resource, entity_id=None, **query):
        return Deeplink.route(resource, entity_id, **query)


class RaisingNotificationService(RecordingNotificationService):
    async def send_async(self, notification):
        raise RuntimeError("notification backend failed")

    def build_deeplink(self, resource, entity_id=None, **query):
        raise RuntimeError("deeplink backend failed")


@pytest.fixture
def notification_validation_client(app_factory):
    service = RecordingNotificationService()
    app = app_factory()
    app.state.NotificationService = service
    app.include_router(notifications_router, prefix="/api")
    return TestClient(app), service


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "x"},
        {"message": "x"},
        {"title": "x", "message": "y", "level": "critical"},
        {"title": "x", "message": "y", "actions": [{"deeplink": "opencrab://tasks/1"}]},
        {"title": "x", "message": "y", "actions": "open"},
        {"title": "x", "message": "y", "timeout_s": "later"},
    ],
)
def test_notification_dispatch_rejects_missing_type_and_enum_errors(notification_validation_client, payload):
    client, _service = notification_validation_client

    response = client.post("/api/notifications/dispatch", json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "not-an-object",
        {"title": None, "message": "y"},
        {"title": "x", "message": None},
        {"title": "x", "message": "y", "actions": [{"title": "Open", "deeplink": 123}]},
        {"title": "x", "message": "y", "actions": [{"title": 123, "deeplink": "opencrab://tasks/1"}]},
        {"title": "x", "message": "y", "thread": {"$ne": None}},
    ],
)
def test_notification_dispatch_rejects_null_non_object_and_nested_type_errors(
    notification_validation_client,
    payload,
):
    client, _service = notification_validation_client

    response = client.post("/api/notifications/dispatch", json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "x", "message": "y"},
        {"title": "x", "message": "y", "level": "success", "actions": [], "deeplink": None, "timeout_s": None},
        {"title": "<script>alert(1)</script>", "message": "' OR 1=1 --", "thread": "task:1"},
        {"title": "x" * 512, "message": "y" * 2048, "timeout_s": 1},
    ],
)
def test_notification_dispatch_accepts_current_positive_boundary_and_injection_as_data(
    notification_validation_client,
    payload,
):
    client, service = notification_validation_client

    response = client.post("/api/notifications/dispatch", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "scheduled"
    assert service.sent[-1].title == payload["title"]


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "x", "message": "y", "unknown": "field"},
        {"title": "x", "message": "y", "actions": [{"title": "Open", "unknown": "field"}]},
    ],
)
@pytest.mark.xfail(strict=True, reason="Known issue: notification request models silently ignore unknown fields.")
def test_notification_dispatch_should_reject_unknown_fields(notification_validation_client, payload):
    client, _service = notification_validation_client

    response = client.post("/api/notifications/dispatch", json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize("payload", [{"title": "", "message": "x"}, {"title": "x", "message": ""}, {"title": "x", "message": "y", "timeout_s": 0}])
@pytest.mark.xfail(strict=True, reason="Known issue: notification request accepts empty text and non-positive timeout_s.")
def test_notification_dispatch_should_reject_empty_text_and_non_positive_timeout(notification_validation_client, payload):
    client, _service = notification_validation_client

    response = client.post("/api/notifications/dispatch", json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "x", "message": "y", "deeplink": "tasks/1"},
        {"title": "x", "message": "y", "deeplink": "javascript:alert(1)"},
        {"title": "x", "message": "y", "actions": [{"title": "Open", "deeplink": "tasks/1"}]},
    ],
)
@pytest.mark.xfail(strict=True, reason="Known issue: notification API does not validate unsafe or scheme-less deeplinks.")
def test_notification_dispatch_should_reject_unsafe_deeplinks(notification_validation_client, payload):
    client, _service = notification_validation_client

    response = client.post("/api/notifications/dispatch", json=payload)

    assert response.status_code == 400


def test_notification_dispatch_returns_500_when_service_raises(app_factory):
    app = app_factory()
    app.state.NotificationService = RaisingNotificationService()
    app.include_router(notifications_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/notifications/dispatch", json={"title": "x", "message": "y"})

    assert response.status_code == 500


def test_notification_dispatch_returns_503_when_service_is_missing(app_factory):
    app = app_factory()
    app.include_router(notifications_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/notifications/dispatch", json={"title": "x", "message": "y"})

    assert response.status_code == 503


def test_deeplink_preview_returns_500_when_service_raises(app_factory):
    app = app_factory()
    app.state.NotificationService = RaisingNotificationService()
    app.include_router(notifications_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/notifications/deeplink-preview/tasks")

    assert response.status_code == 500


def test_deeplink_preview_returns_503_when_service_is_missing(app_factory):
    app = app_factory()
    app.include_router(notifications_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/notifications/deeplink-preview/tasks")

    assert response.status_code == 503


@pytest.mark.parametrize(
    ("params", "expected_suffix"),
    [
        ({}, "opencrab://tasks"),
        ({"entity_id": "42"}, "opencrab://tasks/42"),
        ({"entity_id": "42", "action": "history"}, "opencrab://tasks/42?action=history"),
        ({"entity_id": "42", "tab": "logs"}, "opencrab://tasks/42?tab=logs"),
        ({"entity_id": "42", "action": "history", "tab": "logs"}, "opencrab://tasks/42?action=history&tab=logs"),
    ],
)
def test_deeplink_preview_builds_specified_query_combinations(notification_validation_client, params, expected_suffix):
    client, _service = notification_validation_client

    response = client.get("/api/notifications/deeplink-preview/tasks", params=params)

    assert response.status_code == 200
    assert response.json()["deeplink"] == expected_suffix


@pytest.mark.parametrize(
    "params",
    [
        {"entity_id": "<script>alert(1)</script>"},
        {"action": "' OR 1=1 --"},
        {"tab": "$(touch /tmp/pwned)"},
        {"entity_id": "{\"$ne\": null}", "action": "{{7*7}}"},
        {"entity_id": "x" * 4096},
    ],
)
@pytest.mark.xfail(strict=True, reason="Known issue: deeplink preview accepts unbounded/security query payloads.")
def test_deeplink_preview_should_reject_security_and_extreme_query_values(notification_validation_client, params):
    client, _service = notification_validation_client

    response = client.get("/api/notifications/deeplink-preview/tasks", params=params)

    assert response.status_code == 400


@pytest.mark.xfail(strict=True, reason="Known issue: deeplink preview accepts javascript-looking resources.")
def test_deeplink_preview_should_reject_javascript_resource(notification_validation_client):
    client, _service = notification_validation_client

    response = client.get("/api/notifications/deeplink-preview/javascript:alert(1)")

    assert response.status_code == 400


@pytest.mark.xfail(strict=True, reason="Known issue: deeplink entity_id is interpolated without path encoding.")
def test_deeplink_preview_should_encode_entity_path_segment(notification_validation_client):
    client, _service = notification_validation_client

    response = client.get("/api/notifications/deeplink-preview/tasks", params={"entity_id": "task 1"})

    assert response.status_code == 200
    assert response.json()["deeplink"] == "opencrab://tasks/task%201"
