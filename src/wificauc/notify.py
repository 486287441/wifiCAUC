from __future__ import annotations

import subprocess
import sys

_FAILURE_REASON_MAX_LEN = 120


def _applescript_string(value: str) -> str:
    """Escape for AppleScript double-quoted string literals."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _display_notification(title: str, *, message: str = "", subtitle: str = "") -> bool:
    # AppleScript requires double-quoted strings; shlex.quote uses single quotes
    # and osascript fails silently (exit 1) on Chinese-locale macOS.
    parts = [f'display notification "{_applescript_string(message)}"']
    parts.append(f'with title "{_applescript_string(title)}"')
    if subtitle:
        parts.append(f'subtitle "{_applescript_string(subtitle)}"')
    script = " ".join(parts)
    result = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or "").strip()
        print(
            f"notify: osascript failed (exit {result.returncode})"
            + (f": {err}" if err else ""),
            file=sys.stderr,
        )
        print(
            "notify: 请在「系统设置 → 通知」中允许终端 App 的通知；"
            "或执行: osascript -e 'display notification \"test\" with title \"test\"'",
            file=sys.stderr,
        )
        return False
    return True


def notify_success() -> None:
    _display_notification("CAUC 校园网", message="已成功登录")


def notify_failure(reason: str) -> None:
    trimmed = reason.strip()
    if len(trimmed) > _FAILURE_REASON_MAX_LEN:
        trimmed = trimmed[: _FAILURE_REASON_MAX_LEN - 1] + "…"
    _display_notification("登录失败", subtitle=trimmed)


def notify_test() -> bool:
    """Send a test notification; returns False if osascript failed."""
    return _display_notification("CAUC 校园网", message="通知测试")
