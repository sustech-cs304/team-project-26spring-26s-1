from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import logging
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from importlib import import_module
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode, urlparse, urlunparse

from agent.config import NotificationConfig, get_config, get_config_path
from agent.notification_assets import (
    DEFAULT_NOTIFICATION_ICON_RELATIVE_PATH,
    ensure_default_notification_icon,
)

log = logging.getLogger(__name__)


class NotificationLevel(str, Enum):
    info = "info"
    success = "success"
    warning = "warning"
    error = "error"


@dataclass(frozen=True, slots=True)
class Deeplink:
    url: str

    @classmethod
    def route(
        cls,
        resource: str,
        entity_id: str | int | None = None,
        *,
        scheme: str = "opencrab",
        action: str | None = None,
        tab: str | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> "Deeplink":
        host = resource.strip().strip("/")
        if not host:
            raise ValueError("resource must not be empty")

        params: dict[str, Any] = {}
        if query:
            params.update(query)
        if action:
            params["action"] = action
        if tab:
            params["tab"] = tab

        path = ""
        if entity_id is not None:
            path = f"/{entity_id}"

        return cls(
            url=urlunparse(
                (scheme, host, path, "", urlencode(params, doseq=True), "")
            )
        )


@dataclass(frozen=True, slots=True)
class NotificationAction:
    title: str
    deeplink: str | Deeplink | None = None


@dataclass(frozen=True, slots=True)
class AppNotification:
    title: str
    message: str
    level: NotificationLevel = NotificationLevel.info
    deeplink: str | Deeplink | None = None
    actions: tuple[NotificationAction, ...] = field(default_factory=tuple)
    thread: str | None = None
    timeout_s: int | None = None
    icon_path: str | None = None
    attachment_path: str | None = None


class NotificationService:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._loop = loop
        self._default_icon_path = ensure_default_notification_icon()
        self._notifier: Any | None = None
        self._notifier_signature: tuple[Any, ...] | None = None
        self._backend_loaded = False
        self._backend_available = False
        self._desktop_notifier: Any | None = None
        self._desktop_button: Any | None = None
        self._desktop_attachment: Any | None = None
        self._desktop_icon: Any | None = None
        self._desktop_urgency: Any | None = None

    @property
    def _config(self) -> NotificationConfig:
        return get_config_path(get_config(), "notification")

    def _build_notifier_signature(self, config: NotificationConfig | None = None) -> tuple[Any, ...]:
        config = config if config is not None else self._config
        return (
            config.app_name,
            config.app_icon,
            config.notification_limit,
        )

    def _resolve_path(self, raw_path: str | None) -> Path | None:
        if not raw_path:
            return None
        if Path(raw_path) == DEFAULT_NOTIFICATION_ICON_RELATIVE_PATH:
            return self._default_icon_path
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = path.resolve()
        if not path.exists():
            log.warning("Notification asset not found: %s", path)
            return None
        return path

    def _stage_windows_notification_asset(self, path: Path) -> Path:
        if platform.system() != "Windows" and str(path).isascii():
            return path
        if platform.system() != "Windows":
            return path
        if str(path).isascii():
            return path

        digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
        cache_dir = Path(tempfile.gettempdir()) / "agent_notify_assets"
        cache_dir.mkdir(parents=True, exist_ok=True)
        staged = cache_dir / f"{path.stem}-{digest}{path.suffix.lower()}"
        try:
            if not staged.exists() or path.stat().st_mtime > staged.stat().st_mtime:
                shutil.copy2(path, staged)
        except OSError:
            log.exception("Failed to stage notification asset at ASCII-safe path: %s", path)
            return path
        return staged

    async def send_async(self, notification: AppNotification) -> str | None:
        config = self._config
        notifier = self._get_notifier(config)
        if notifier is None:
            return None

        payload = self._to_backend_payload(notification, config)
        try:
            return await notifier.send(**payload)
        except Exception:
            log.exception("Failed to dispatch desktop notification")
            return None

    def send(
        self,
        notification: AppNotification,
    ) -> asyncio.Task[str | None] | concurrent.futures.Future[str | None]:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self._loop:
            return asyncio.create_task(self.send_async(notification))

        return asyncio.run_coroutine_threadsafe(
            self.send_async(notification),
            self._loop,
        )

    async def request_authorisation(self) -> bool:
        notifier = self._get_notifier()
        if notifier is None:
            return False
        try:
            return await notifier.request_authorisation()
        except Exception:
            log.exception("Failed to request notification authorisation")
            return False

    def build_deeplink(
        self,
        resource: str,
        entity_id: str | int | None = None,
        *,
        action: str | None = None,
        tab: str | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Deeplink:
        config = self._config
        return Deeplink.route(
            resource,
            entity_id,
            scheme=config.deeplink_scheme,
            action=action,
            tab=tab,
            query=query,
        )

    def _get_notifier(self, config: NotificationConfig | None = None) -> Any | None:
        config = config if config is not None else self._config
        if not config.enabled:
            return None

        if not self._backend_loaded:
            self._load_backend()

        if not self._backend_available or self._desktop_notifier is None:
            return None

        notifier_signature = self._build_notifier_signature(config)
        if self._notifier is None or self._notifier_signature != notifier_signature:
            app_icon = None
            if config.app_icon and self._desktop_icon is not None:
                resolved_icon = self._resolve_path(config.app_icon)
                if resolved_icon is not None:
                    app_icon = self._desktop_icon(
                        self._stage_windows_notification_asset(resolved_icon)
                    )

            self._notifier = self._desktop_notifier(
                app_name=config.app_name,
                app_icon=app_icon,
                notification_limit=config.notification_limit,
            )
            self._notifier_signature = notifier_signature

        return self._notifier

    def _load_backend(self) -> None:
        self._backend_loaded = True
        try:
            module = import_module("desktop_notifier")
        except ImportError:
            log.warning(
                "desktop-notifier is not installed. Desktop notifications are disabled.",
            )
            return

        self._desktop_notifier = getattr(module, "DesktopNotifier", None)
        self._desktop_button = getattr(module, "Button", None)
        self._desktop_attachment = getattr(module, "Attachment", None)
        self._desktop_icon = getattr(module, "Icon", None)
        self._desktop_urgency = getattr(module, "Urgency", None)
        self._backend_available = self._desktop_notifier is not None

    def _to_backend_payload(
        self,
        notification: AppNotification,
        config: NotificationConfig | None = None,
    ) -> dict[str, Any]:
        config = config if config is not None else self._config
        urgency = None
        if self._desktop_urgency is not None:
            urgency_map = {
                NotificationLevel.info: self._desktop_urgency.Normal,
                NotificationLevel.success: self._desktop_urgency.Normal,
                NotificationLevel.warning: self._desktop_urgency.Normal,
                NotificationLevel.error: self._desktop_urgency.Critical,
            }
            urgency = urgency_map[notification.level]

        payload: dict[str, Any] = {
            "title": notification.title,
            "message": notification.message,
            "urgency": urgency,
            "thread": notification.thread,
            "timeout": notification.timeout_s or config.default_timeout_s,
        }

        deeplink_url = self._normalize_deeplink(notification.deeplink)
        if deeplink_url:
            payload["on_clicked"] = lambda url=deeplink_url: self._open_deeplink(url)

        buttons: list[Any] = []
        if self._desktop_button is not None:
            for action in notification.actions:
                action_url = self._normalize_deeplink(action.deeplink)
                buttons.append(
                    self._desktop_button(
                        title=action.title,
                        on_pressed=(
                            None
                            if not action_url
                            else lambda url=action_url: self._open_deeplink(url)
                        ),
                    )
                )
        if buttons:
            payload["buttons"] = buttons

        default_icon_path = notification.icon_path or config.app_icon
        if default_icon_path and self._desktop_icon is not None:
            resolved_icon = self._resolve_path(default_icon_path)
            if resolved_icon is not None:
                payload["icon"] = self._desktop_icon(
                    self._stage_windows_notification_asset(resolved_icon)
                )

        if notification.attachment_path and self._desktop_attachment is not None:
            resolved_attachment = self._resolve_path(notification.attachment_path)
            if resolved_attachment is not None:
                payload["attachment"] = self._desktop_attachment(
                    resolved_attachment
                )

        return payload

    def _normalize_deeplink(self, deeplink: str | Deeplink | None) -> str | None:
        if deeplink is None:
            return None
        if isinstance(deeplink, Deeplink):
            return deeplink.url

        parsed = urlparse(deeplink)
        if not parsed.scheme:
            raise ValueError(f"Invalid deeplink: {deeplink}")
        return deeplink

    def _open_deeplink(self, deeplink: str) -> None:
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(deeplink)  # type: ignore[attr-defined]
                return
            if system == "Darwin":
                subprocess.Popen(["open", deeplink])
                return
            subprocess.Popen(["xdg-open", deeplink])
        except Exception:
            log.exception("Failed to open deeplink: %s", deeplink)
