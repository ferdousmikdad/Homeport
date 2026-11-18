"""Ports in use: list every listening port and stop what holds one."""
import socket
import subprocess
import sys

import psutil
from fastapi.testclient import TestClient

from tests._helpers import wait_until

LOCAL = {"Origin": "http://localhost:7777"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _outside_server(port: int) -> psutil.Process:
    """A program Homeport didn't start, listening on ``port``: a launcher starts
    it and exits, so it isn't one of this (test) Homeport's child processes."""
    code = ("import socket, time; s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); "
            f"s.bind(('127.0.0.1', {port})); s.listen(); time.sleep(60)")
    launcher = ("import subprocess, sys; "
                f"print(subprocess.Popen([sys.executable, '-c', {code!r}], stdin=subprocess.DEVNULL, "
                "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).pid)")
    pid = int(subprocess.check_output([sys.executable, "-c", launcher], text=True))
    return psutil.Process(pid)


def _row(client, port, pid=None):
    rows = client.get("/api/ports").json()["ports"]
    return next((r for r in rows if r["port"] == port and (pid is None or r["pid"] == pid)), None)


def test_lists_and_stops_an_outside_program(monkeypatch):
    from backend import main
    monkeypatch.setattr(main.registry, "list", lambda: [{"id": "web", "name": "Web", "port": port}])
    port = _free_port()
    proc = _outside_server(port)
    try:
        client = TestClient(main.app)
        assert wait_until(lambda: _row(client, port, proc.pid) is not None)
        row = _row(client, port, proc.pid)
        assert row["owner"] == "outside"
        assert row["wanted_by"] == [{"id": "web", "name": "Web"}]  # it's in Web's way
        assert "127.0.0.1" in row["address"]

        # only from this computer's own pages, and only the program the list showed
        assert client.post(f"/api/ports/{port}/stop?pid={proc.pid}",
                           headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post(f"/api/ports/{port}/stop?pid={proc.pid + 100000}", headers=LOCAL).status_code == 409
        assert proc.is_running()

        res = client.post(f"/api/ports/{port}/stop?pid={proc.pid}", headers=LOCAL)
        assert res.json() == {"ok": True, "stopped": "program"}
        proc.wait(timeout=10)
        assert _row(client, port) is None
    finally:
        if proc.is_running():
            proc.kill()


def test_homeport_itself_is_never_stopped(monkeypatch):
    import os
    from backend import main, osutil
    monkeypatch.setattr(osutil, "listening_sockets",
                        lambda: [{"port": 7777, "pid": os.getpid(), "address": ["127.0.0.1"]}])
    client = TestClient(main.app)
    assert _row(client, 7777)["owner"] == "homeport"
    assert client.post(f"/api/ports/7777/stop?pid={os.getpid()}", headers=LOCAL).status_code == 400


def test_an_apps_port_stops_the_app(monkeypatch):
    import os
    from backend import main, osutil
    stopped = []
    monkeypatch.setattr(osutil, "listening_sockets",
                        lambda: [{"port": 3000, "pid": 4242, "address": ["127.0.0.1"]}])
    monkeypatch.setattr(main.registry, "list", lambda: [{"id": "web", "name": "Web", "port": 3000}])
    monkeypatch.setattr(main.pm, "pid", lambda app_id: 4242 if app_id == "web" else None)
    monkeypatch.setattr(main.monitor, "_tree_pids", lambda pid: [pid] if pid == 4242 else [os.getpid()])

    async def fake_stop(app_id):
        stopped.append(app_id)
        return {}
    monkeypatch.setattr(main, "stop_app", fake_stop)
    client = TestClient(main.app)
    row = _row(client, 3000)
    assert (row["owner"], row["app_id"], row["app_name"], row["wanted_by"]) == ("app", "web", "Web", [])
    assert client.post("/api/ports/3000/stop?pid=4242", headers=LOCAL).json()["stopped"] == "app"
    assert stopped == ["web"]
