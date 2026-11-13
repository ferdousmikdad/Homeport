"""Shared helpers for the localhost-manager test-suite."""

from __future__ import annotations

import sys
import time
from typing import Callable


def wait_until(predicate: Callable[[], bool], timeout: float = 8.0, interval: float = 0.05) -> bool:
    """Poll ``predicate`` until it returns truthy or ``timeout`` expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def wait_value(getter: Callable[[], object], expected, timeout: float = 8.0, interval: float = 0.05):
    """Poll ``getter`` until it equals ``expected``; return the last value."""
    deadline = time.monotonic() + timeout
    value = getter()
    while value != expected and time.monotonic() < deadline:
        time.sleep(interval)
        value = getter()
    return value


def sleep_cmd(seconds: float) -> str:
    """A shell command that just waits — works in sh and cmd.exe alike."""
    return f'"{sys.executable}" -c "import time; time.sleep({seconds})"'


def explain(client, app_id: str) -> str:
    """Why an app isn't where a test expected: its state and last log lines."""
    try:
        st = client.get(f"/api/apps/{app_id}").json()
        keep = {k: st.get(k) for k in ("status", "pid", "port", "detected_port", "port_ready",
                                         "last_exit_code", "last_error", "command")}
        logs = client.get(f"/api/apps/{app_id}/logs", params={"tail": 30}).text
        return f"\nstate={keep}\nlogs:\n{logs[-3000:]}"
    except Exception as exc:  # pragma: no cover - diagnostics only
        return f"(couldn't explain: {exc})"
