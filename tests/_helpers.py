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
        probes = []
        port = st.get("port") or st.get("detected_port")
        if port:
            import socket
            for host in ("127.0.0.1", "localhost", "::1"):
                try:
                    with socket.create_connection((host, int(port)), timeout=2):
                        probes.append(f"{host}: ok")
                except OSError as exc:
                    probes.append(f"{host}: {type(exc).__name__} {exc}")
        procs = []
        if st.get("pid"):
            import psutil
            try:
                root = psutil.Process(st["pid"])
                for p in [root] + root.children(recursive=True):
                    try:
                        conns = [(c.laddr, c.status) for c in p.net_connections(kind="inet")]
                    except Exception as exc:  # noqa: BLE001
                        conns = f"{type(exc).__name__}"
                    procs.append(f"pid={p.pid} name={p.name()} status={p.status()} conns={conns}")
            except Exception as exc:  # noqa: BLE001
                procs.append(f"{type(exc).__name__} {exc}")
        return f"\nstate={keep}\nprobes={probes}\nprocs={procs}\nlogs:\n{logs[-3000:]}"
    except Exception as exc:  # pragma: no cover - diagnostics only
        return f"(couldn't explain: {exc})"
