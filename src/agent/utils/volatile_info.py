from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import locale
import os
import platform


@dataclass(frozen=True, slots=True)
class VolatileSystemInfo:
    os_name: str
    os_release: str
    platform_name: str
    machine: str
    python_version: str
    locale_name: str
    preferred_encoding: str
    path_separator: str


def _safe_text(value: object, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or fallback


def collect_volatile_system_info() -> VolatileSystemInfo:
    locale_parts = [part for part in locale.getlocale() if part]
    locale_name = ".".join(locale_parts) if locale_parts else "unknown"

    return VolatileSystemInfo(
        os_name=_safe_text(platform.system()),
        os_release=_safe_text(platform.release()),
        platform_name=_safe_text(platform.platform(terse=True)),
        machine=_safe_text(platform.machine()),
        python_version=_safe_text(platform.python_version()),
        locale_name=locale_name,
        preferred_encoding=_safe_text(locale.getpreferredencoding(False)),
        path_separator=os.sep,
    )


def _format_utc_offset(now: datetime) -> str:
    offset = now.utcoffset()
    if offset is None:
        return "unknown"

    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def build_volatile_info() -> str:
    now = datetime.now().astimezone()
    tz_name = now.strftime("%Z") or "unknown"
    system_info = collect_volatile_system_info()
    return (
        "<system-reminder>\n"
        "This context is volatile and may change between turns.\n"
        f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} {tz_name} ({_format_utc_offset(now)})\n"
        f"Host OS: {system_info.os_name} {system_info.os_release} ({system_info.platform_name})\n"
        f"System architecture: {system_info.machine}\n"
        f"Python runtime: {system_info.python_version}\n"
        f"Locale: {system_info.locale_name}; preferred encoding: {system_info.preferred_encoding}\n"
        f"Path separator: {system_info.path_separator}\n"
        "</system-reminder>"
    )
