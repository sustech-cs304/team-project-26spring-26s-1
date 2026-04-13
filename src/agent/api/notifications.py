from __future__ import annotations

from typing import Literal

import pydantic
from fastapi import APIRouter, HTTPException, Request

from agent.services.notification_service import (
    AppNotification,
    NotificationAction,
    NotificationLevel,
    NotificationService,
)

router = APIRouter(tags=["notifications"])


class NotificationActionRequest(pydantic.BaseModel):
    title: str = pydantic.Field(
        ...,
        description="Button label shown in the desktop notification.",
        examples=["打开任务"],
    )
    deeplink: str | None = pydantic.Field(
        None,
        description="Optional deeplink opened when the button is pressed.",
        examples=["opencrab://tasks/3b11e1a9-7c45-40cf-9dd6-bbfa6308b54e"],
    )


class NotificationDispatchRequest(pydantic.BaseModel):
    title: str = pydantic.Field(
        ...,
        description="Notification title shown by the OS notification center.",
        examples=["任务执行完成"],
    )
    message: str = pydantic.Field(
        ...,
        description="Main notification body text.",
        examples=["定时任务“同步课程表”已成功完成。"],
    )
    level: Literal["info", "success", "warning", "error"] = pydantic.Field(
        "info",
        description="Semantic notification level. `error` is mapped to a higher urgency.",
        examples=["success"],
    )
    deeplink: str | None = pydantic.Field(
        None,
        description="Optional deeplink opened when the user clicks the notification body.",
        examples=["opencrab://runs/0ccab874-8b91-49f8-b97c-b7309ab7a0df?tab=logs"],
    )
    actions: list[NotificationActionRequest] = pydantic.Field(
        default_factory=list,
        description="Optional notification action buttons.",
    )
    thread: str | None = pydantic.Field(
        None,
        description="Optional thread / group key. Some platforms use it for notification grouping.",
        examples=["task:3b11e1a9-7c45-40cf-9dd6-bbfa6308b54e"],
    )
    timeout_s: int | None = pydantic.Field(
        None,
        description="Optional timeout override in seconds. Falls back to config when omitted.",
        examples=[10],
    )


class NotificationDispatchResponse(pydantic.BaseModel):
    status: str = pydantic.Field(
        "scheduled",
        description="Dispatch result. `scheduled` means the backend accepted the notification request.",
    )
    notification_id: str | None = pydantic.Field(
        None,
        description="Backend/library notification id when provided by the platform, otherwise null.",
    )


class NotificationDeeplinkPreviewResponse(pydantic.BaseModel):
    deeplink: str = pydantic.Field(
        ...,
        description="Generated deeplink string.",
        examples=["opencrab://tasks/3b11e1a9-7c45-40cf-9dd6-bbfa6308b54e?action=history"],
    )


@router.post(
    "/notifications/dispatch",
    response_model=NotificationDispatchResponse,
    summary="Dispatch a desktop notification",
    description=(
        "Send one desktop notification through the backend notification layer. "
        "The request can include a body deeplink and optional action buttons. "
        "If the desktop notification backend is unavailable, the request is still accepted "
        "but `notification_id` may be null."
    ),
)
async def dispatch_notification(
    request: Request,
    body: NotificationDispatchRequest,
) -> NotificationDispatchResponse:
    service: NotificationService | None = getattr(
        request.app.state,
        "NotificationService",
        None,
    )
    if service is None:
        raise HTTPException(status_code=503, detail="Notification service unavailable")

    notification = AppNotification(
        title=body.title,
        message=body.message,
        level=NotificationLevel(body.level),
        deeplink=body.deeplink,
        actions=tuple(
            NotificationAction(title=item.title, deeplink=item.deeplink)
            for item in body.actions
        ),
        thread=body.thread,
        timeout_s=body.timeout_s,
    )
    notification_id = await service.send_async(notification)
    return NotificationDispatchResponse(notification_id=notification_id)


@router.get(
    "/notifications/deeplink-preview/{resource}",
    response_model=NotificationDeeplinkPreviewResponse,
    summary="Preview a generated deeplink",
    description=(
        "Build a normalized `opencrab://` deeplink using the backend convention. "
        "Use this endpoint to verify route structure before wiring a notification "
        "or frontend protocol handler."
    ),
)
async def preview_deeplink(
    request: Request,
    resource: str,
    entity_id: str | None = None,
    action: str | None = None,
    tab: str | None = None,
) -> NotificationDeeplinkPreviewResponse:
    service: NotificationService | None = getattr(
        request.app.state,
        "NotificationService",
        None,
    )
    if service is None:
        raise HTTPException(status_code=503, detail="Notification service unavailable")

    deeplink = service.build_deeplink(
        resource,
        entity_id,
        action=action,
        tab=tab,
    )
    return NotificationDeeplinkPreviewResponse(deeplink=deeplink.url)
