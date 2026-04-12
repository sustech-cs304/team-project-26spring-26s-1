from __future__ import annotations

import logging
from typing import Any

from agent.services.notification_service import AppNotification, NotificationService

log = logging.getLogger(__name__)

_notification_service: NotificationService | None = None


def configure_notification_service(service: NotificationService | None) -> None:
    global _notification_service
    _notification_service = service


def get_notification_service() -> NotificationService | None:
    return _notification_service


def notify(
    notification: AppNotification,
) -> Any | None:
    if _notification_service is None:
        log.warning("NotificationService is not configured")
        return None
    return _notification_service.send(notification)
