"""Tests for SPEC v2 features and API routes."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from backend import main, monitor, registry as registry_module
from _helpers import explain, http_server_cmd, sleep_cmd, wait_until


def test_browse_endpoint(client, tmp_path):
    sub1 = tmp_path / "app-one"
    sub1.mkdir()
    (sub1 / "server.py").write_text("print('hello')\n")

    sub2 = tmp_path / "plain-dir"
    sub2.mkdir()

    hidden = tmp_path / ".hidden"
    hidden.mkdir()

    res = client.get(f"/api/browse?path={tmp_path}")
    assert res.status_code == 200
    data = res.json()
    assert data["path"] == str(tmp_path)
    assert data["parent"] == str(tmp_path.parent)

    names = [e["name"] for e in data["entries"]]
    assert "app-one" in names
    assert "plain-dir" in names
    assert ".hidden" not in names

    app_one = next(e for e in data["entries"] if e["name"] == "app-one")
    assert app_one["looks_like_app"] is True

    plain = next(e for e in data["entries"] if e["name"] == "plain-dir")
    assert plain["looks_like_app"] is False


def test_browse_invalid_dir(client, tmp_path):
    res = client.get(f"/api/browse?path={tmp_path / 'nonexistent'}")
    assert res.status_code == 400


def _as_mac(monkeypatch):
    """The picker tests drive the macOS code path, whatever OS runs them."""
    from backend import osutil
    monkeypatch.setattr(osutil, "IS_MAC", True)
    monkeypatch.setattr(osutil, "IS_WINDOWS", False)


def test_pick_folder_endpoint(client, monkeypatch, tmp_path):
    _as_mac(monkeypatch)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 0, stdout=f"{tmp_path}\n", stderr=""),
    )
    res = client.post("/api/pick-folder")
    assert res.status_code == 200
    assert res.json() == {"path": str(tmp_path)}


def test_open_target_endpoint(client, demo_dir, long_command, monkeypatch):
    add_res = client.post(
        "/api/apps",
        json={"name": "OpenApp", "path": str(demo_dir), "command": long_command, "port": 8899},
    )
    app_id = add_res.json()["id"]

    from backend import osutil

    calls = []
    monkeypatch.setattr(osutil, "open_folder", lambda path: calls.append(("folder", path)))
    monkeypatch.setattr(osutil, "open_terminal", lambda path: calls.append(("terminal", path)))
    monkeypatch.setattr(osutil, "open_url", lambda url: calls.append(("url", url)))

    res_finder = client.post(f"/api/apps/{app_id}/open", json={"target": "finder"})
    assert res_finder.status_code == 200
    assert calls[-1] == ("folder", str(demo_dir))

    res_term = client.post(f"/api/apps/{app_id}/open", json={"target": "terminal"})
    assert res_term.status_code == 200
    assert calls[-1] == ("terminal", str(demo_dir))

    res_browser = client.post(f"/api/apps/{app_id}/open", json={"target": "browser"})
    assert res_browser.status_code == 200
    assert calls[-1] == ("url", "http://127.0.0.1:8899/")

    res_app = client.post(f"/api/apps/{app_id}/open", json={"target": "app"}, headers={"Host": "localhost:7777"})
    assert res_app.status_code == 200
    assert calls[-1] == ("url", f"http://{app_id}.localhost:7777/")

    res_bad = client.post(f"/api/apps/{app_id}/open", json={"target": "invalid"})
    assert res_bad.status_code == 400


def test_port_ready_only_when_port_answers(client, demo_dir):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.close()
    cmd = http_server_cmd(demo_dir, port)
    app_id = client.post("/api/apps", json={"name": "ReadyApp", "path": str(demo_dir), "command": cmd, "port": port}).json()["id"]
    assert client.post(f"/api/apps/{app_id}/start").status_code == 200
    try:
        assert wait_until(lambda: client.get(f"/api/apps/{app_id}").json()["port_ready"], timeout=20), \
            explain(client, app_id)
    finally:
        client.post(f"/api/apps/{app_id}/stop")
    assert client.get(f"/api/apps/{app_id}").json()["port_ready"] is False


def test_patch_running_returns_needs_restart(client, demo_dir, long_command):
    add_res = client.post(
        "/api/apps",
        json={"name": "RunningPatch", "path": str(demo_dir), "command": long_command},
    )
    app_id = add_res.json()["id"]

    client.post(f"/api/apps/{app_id}/start")
    assert wait_until(lambda: client.get("/api/apps").json()[0]["status"] == "running")

    patch_res = client.patch(
        f"/api/apps/{app_id}",
        json={"command": sleep_cmd(100), "autostart": True, "notify": False},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["needs_restart"] is True
    assert data["autostart"] is True
    assert data["notify"] is False

    client.post(f"/api/apps/{app_id}/stop")


def test_start_all_and_stop_all(client, demo_dir, long_command):
    client.post("/api/apps", json={"name": "App1", "path": str(demo_dir), "command": long_command})
    client.post("/api/apps", json={"name": "App2", "path": str(demo_dir), "command": long_command})

    res_start = client.post("/api/apps/start-all")
    assert res_start.status_code == 200
    assert wait_until(lambda: all(a["status"] == "running" for a in client.get("/api/apps").json()))

    res_stop = client.post("/api/apps/stop-all")
    assert res_stop.status_code == 200
    assert wait_until(lambda: all(a["status"] == "stopped" for a in client.get("/api/apps").json()))


def test_port_conflict_and_kill(client, demo_dir):
    # Bind a temporary socket on a free port
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    conflict_port = sock.getsockname()[1]

    # Spawn a separate background process holding the port
    script = (
        f"import socket, time\n"
        f"s = socket.socket()\n"
        f"s.bind(('127.0.0.1', {conflict_port}))\n"
        f"s.listen(16)\n"
        f"s.settimeout(30)\n"
        f"end = time.time() + 30\n"
        f"while time.time() < end:\n"
        f"    try:\n"
        f"        c, _ = s.accept(); c.close()\n"
        f"    except OSError:\n"
        f"        break\n"
    )
    sock.close()
    proc = subprocess.Popen([sys.executable, "-c", script])
    try:
        assert wait_until(lambda: monitor.port_open(conflict_port), timeout=5)

        # The app itself also holds that port, from a script file (no shell quoting)
        (demo_dir / "holder.py").write_text(script)

        # Register an app with that port
        reg_res = client.post(
            "/api/apps",
            json={
                "name": "Conflicted",
                "path": str(demo_dir),
                "command": f'"{sys.executable}" holder.py',  # same command in sh and cmd.exe
                "port": conflict_port,
            },
        )
        app_id = reg_res.json()["id"]

        # Starting without kill_conflict should fail with 409 port_in_use
        start_res = client.post(f"/api/apps/{app_id}/start")
        assert start_res.status_code == 409
        detail = start_res.json()["detail"]
        assert detail["error"] == "port_in_use"
        assert detail["pid"] == proc.pid

        # Starting with kill_conflict=1 kills the conflicting process and starts
        kill_start_res = client.post(f"/api/apps/{app_id}/start?kill_conflict=1")
        assert kill_start_res.status_code == 200
        assert wait_until(lambda: client.get("/api/apps").json()[0]["status"] == "running", timeout=20), \
            explain(client, app_id)

        client.post(f"/api/apps/{app_id}/stop")
    finally:
        try:
            proc.kill()
        except OSError:
            pass


def test_logs_delete_and_download(client, demo_dir, long_command):
    reg_res = client.post(
        "/api/apps",
        json={"name": "LogDownloadApp", "path": str(demo_dir), "command": long_command},
    )
    app_id = reg_res.json()["id"]
    client.post(f"/api/apps/{app_id}/start")
    assert wait_until(lambda: len(client.get(f"/api/apps/{app_id}/logs").json()["lines"]) > 0)
    client.post(f"/api/apps/{app_id}/stop")

    # Download logs
    dl_res = client.get(f"/api/apps/{app_id}/logs/download")
    assert dl_res.status_code == 200
    assert "started pid=" in dl_res.text

    # Clear logs
    del_res = client.delete(f"/api/apps/{app_id}/logs")
    assert del_res.status_code == 200
    assert del_res.json() == {"ok": True}

    after_logs = client.get(f"/api/apps/{app_id}/logs").json()
    assert after_logs["lines"] == []


def test_app_description_and_timestamps(client, demo_dir, long_command):
    add_res = client.post(
        "/api/apps",
        json={
            "name": "MetaApp",
            "path": str(demo_dir),
            "command": long_command,
            "description": "A very useful test application",
        },
    )
    assert add_res.status_code == 200
    data = add_res.json()
    assert data["description"] == "A very useful test application"
    assert data["created_at"] is not None
    assert data["updated_at"] is not None

    app_id = data["id"]
    get_res = client.get(f"/api/apps/{app_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "MetaApp"

    patch_res = client.patch(
        f"/api/apps/{app_id}",
        json={"description": "Updated description"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["description"] == "Updated description"


def test_pick_folder_cancel_and_unavailable(client, monkeypatch):
    _as_mac(monkeypatch)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 1, stdout="", stderr="execution error: User canceled. (-128)"),
    )
    res = client.post("/api/pick-folder")
    assert res.status_code == 200
    assert res.json() == {"path": None}

    def missing(*a, **k):
        raise FileNotFoundError("osascript")

    monkeypatch.setattr(subprocess, "run", missing)
    res = client.post("/api/pick-folder")
    assert res.status_code == 501
    assert "detail" in res.json()


def test_category_create_patch_and_reorder(client, demo_dir, long_command):
    ids = []
    for name, category in (("Alpha", "Work"), ("Beta", ""), ("Gamma", "Tools")):
        res = client.post(
            "/api/apps",
            json={"name": name, "path": str(demo_dir), "command": long_command, "category": f"  {category} "},
        )
        assert res.status_code == 200
        assert res.json()["category"] == category
        ids.append(res.json()["id"])

    res = client.patch(f"/api/apps/{ids[1]}", json={"category": "Work"})
    assert res.status_code == 200
    assert res.json()["category"] == "Work"
    assert client.patch(f"/api/apps/{ids[1]}", json={"category": 5}).status_code == 400

    # Unknown ids are ignored; unlisted apps keep their order after listed ones.
    res = client.post("/api/apps/reorder", json={"ids": [ids[2], "nope", ids[0]]})
    assert res.status_code == 200
    assert [a["id"] for a in res.json()] == [ids[2], ids[0], ids[1]]
    assert [a["id"] for a in client.get("/api/apps").json()] == [ids[2], ids[0], ids[1]]
    assert [a["id"] for a in main.registry.list()] == [ids[2], ids[0], ids[1]]

    assert client.post("/api/apps/reorder", json={"ids": "x"}).status_code == 400


def test_color_create_patch_and_validation(client, demo_dir, long_command):
    res = client.post(
        "/api/apps",
        json={"name": "Tinted", "path": str(demo_dir), "command": long_command, "color": " Red "},
    )
    assert res.status_code == 200
    app_id = res.json()["id"]
    assert res.json()["color"] == "red"

    res = client.patch(f"/api/apps/{app_id}", json={"color": "blue"})
    assert res.status_code == 200
    assert res.json()["color"] == "blue"
    assert main.registry.get(app_id)["color"] == "blue"

    assert client.patch(f"/api/apps/{app_id}", json={"color": "purple"}).status_code == 400
    assert client.patch(f"/api/apps/{app_id}", json={"color": 3}).status_code == 400
    assert main.registry.get(app_id)["color"] == "blue"

    res = client.patch(f"/api/apps/{app_id}", json={"color": ""})
    assert res.status_code == 200
    assert res.json()["color"] == ""

    res = client.post("/api/apps", json={"name": "Plain", "path": str(demo_dir), "command": long_command})
    assert res.json()["color"] == ""
