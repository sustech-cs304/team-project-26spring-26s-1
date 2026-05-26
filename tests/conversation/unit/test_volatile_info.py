from __future__ import annotations

from agent.utils import volatile_info


def test_collect_volatile_system_info_uses_host_runtime(monkeypatch):
    monkeypatch.setattr(volatile_info.platform, "system", lambda: "Windows")
    monkeypatch.setattr(volatile_info.platform, "release", lambda: "11")
    monkeypatch.setattr(volatile_info.platform, "platform", lambda terse=True: "Windows-11")
    monkeypatch.setattr(volatile_info.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(volatile_info.platform, "python_version", lambda: "3.13.9")
    monkeypatch.setattr(volatile_info.locale, "getlocale", lambda: ("zh_CN", "UTF-8"))
    monkeypatch.setattr(volatile_info.locale, "getpreferredencoding", lambda do_setlocale=False: "utf-8")

    info = volatile_info.collect_volatile_system_info()

    assert info.os_name == "Windows"
    assert info.os_release == "11"
    assert info.platform_name == "Windows-11"
    assert info.machine == "AMD64"
    assert info.python_version == "3.13.9"
    assert info.locale_name == "zh_CN.UTF-8"
    assert info.preferred_encoding == "utf-8"


def test_build_volatile_info_includes_platform_context(monkeypatch):
    monkeypatch.setattr(
        volatile_info,
        "collect_volatile_system_info",
        lambda: volatile_info.VolatileSystemInfo(
            os_name="Windows",
            os_release="11",
            platform_name="Windows-11",
            machine="AMD64",
            python_version="3.13.9",
            locale_name="zh_CN.UTF-8",
            preferred_encoding="utf-8",
            path_separator="\\",
        ),
    )

    message = volatile_info.build_volatile_info()

    assert message.startswith("<system-reminder>")
    assert "Current time:" in message
    assert "Host OS: Windows 11 (Windows-11)" in message
    assert "System architecture: AMD64" in message
    assert "Python runtime: 3.13.9" in message
    assert "Locale: zh_CN.UTF-8; preferred encoding: utf-8" in message
    assert "Path separator: \\" in message
