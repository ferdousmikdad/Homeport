"""API tests via FastAPI TestClient against an isolated registry file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import psutil
import pytest

from _helpers import wait_until, sleep_cmd


def _script(directory, name: str, body: str):
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


def _register(client, name: str, path, command: str | None = None, **extra):
    body = {"name": name, "path": str(path), **extra}
    if command is not None:
        body["command"] = command
    response = client.post("/api/apps", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _state(client, app_id: str) -> dict:
    apps = client.get("/api/apps").json()
    return next(app for app in apps if app["id"] == app_id)


def _alive(pid: int) -> bool:
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


# ---------------------------------------------------------------------------
# basics
# ---------------------------------------------------------------------------
def test_health(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["platform"] in ("mac", "windows", "linux")


def test_empty_registry(client):
    assert client.get("/api/apps").json() == []


def test_unknown_routes_are_404(client):
    for method, url in [
        ("post", "/api/apps/ghost/start"),
        ("post", "/api/apps/ghost/stop"),
        ("post", "/api/apps/ghost/restart"),
        ("get", "/api/apps/ghost/logs"),
        ("patch", "/api/apps/ghost"),
        ("delete", "/api/apps/ghost"),
    ]:
        response = getattr(client, method)(url, json={}) if method == "patch" else getattr(client, method)(url)
        assert response.status_code == 404, (method, url, response.text)


# ---------------------------------------------------------------------------
# create / list / registry persistence
# ---------------------------------------------------------------------------
def test_create_app_defaults_and_slug(client, demo_dir, isolated_registry):
    state = _register(client, "My Demo App!", demo_dir)

    assert state["id"] == "my-demo-app"
    assert state["name"] == "My Demo App!"
    assert state["status"] == "stopped"
    assert state["pid"] is None
    assert state["started_at"] is None
    assert state["uptime_s"] is None
    assert state["cpu_percent"] is None
    assert state["mem_mb"] is None
    assert state["detected_port"] is None
    assert state["healthy"] is None
    assert state["restarts"] == 0
    assert state["last_exit_code"] is None
    assert state["last_error"] is None
    assert state["auto_restart"] is False
    assert "env" not in state  # AppState excludes env per SPEC

    # command was detected from run.py
    assert state["command"] == "python3 run.py"

    listed = client.get("/api/apps").json()
    assert [app["id"] for app in listed] == ["my-demo-app"]

    on_disk = json.loads(Path(isolated_registry.path).read_text(encoding="utf-8"))
    assert on_disk[0]["id"] == "my-demo-app"
    assert on_disk[0]["command"] == "python3 run.py"


def test_create_app_with_all_fields(client, demo_dir):
    command = f"{sys.executable} -u {demo_dir / 'script.py'}"
    state = _register(
        client,
        "Full App",
        demo_dir,
        command,
        port=8123,
        health_url="http://127.0.0.1:8123/health",
        auto_restart=True,
        env={"A": "1", "B": 2},
    )
    assert state["command"] == command
    assert state["port"] == 8123
    assert state["health_url"] == "http://127.0.0.1:8123/health"
    assert state["auto_restart"] is True


def test_create_app_duplicate_name_is_400(client, demo_dir):
    _register(client, "Twice", demo_dir, sleep_cmd(30))
    response = client.post("/api/apps", json={"name": "twice", "path": str(demo_dir)})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.parametrize(
    "body, fragment",
    [
        ({"path": "/tmp"}, "name"),
        ({"name": "x"}, "path"),
        ({"name": "x", "path": "/definitely/not/here"}, "not a directory"),
    ],
)
def test_create_app_validation(client, body, fragment):
    response = client.post("/api/apps", json=body)
    assert response.status_code == 400
    assert fragment in response.json()["detail"]


def test_create_app_rejects_bad_json(client):
    response = client.post(
        "/api/apps", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400

    response = client.post("/api/apps", json=["not", "an", "object"])
    assert response.status_code == 400


def test_create_app_field_types(client, demo_dir):
    base = {"name": "types", "path": str(demo_dir)}
    cases = [
        ({"command": 5}, "command"),
        ({"port": "abc"}, "port"),
        ({"port": 70000}, "port out of range"),
        ({"health_url": 5}, "health_url"),
        ({"env": "nope"}, "env"),
    ]
    for extra, fragment in cases:
        response = client.post("/api/apps", json={**base, **extra})
        assert response.status_code == 400, (extra, response.text)
        assert fragment in response.json()["detail"]


def test_detect_endpoint(client, demo_dir):
    response = client.get("/api/detect", params={"path": str(demo_dir)})
    assert response.status_code == 200
    assert response.json()["command"] == "python3 run.py"

    assert client.get("/api/detect").status_code == 400
    assert client.get("/api/detect", params={"path": "  "}).status_code == 400

    missing = client.get("/api/detect", params={"path": str(demo_dir / "missing")})
    assert missing.status_code == 200
    assert missing.json()["command"] is None


# ---------------------------------------------------------------------------
# start / stop / restart / logs
# ---------------------------------------------------------------------------
def test_start_stop_restart_lifecycle(client, demo_dir):
    command = f"{sys.executable} -u {demo_dir / 'script.py'}"
    app = _register(client, "Runner", demo_dir, command)
    app_id = app["id"]

    started = client.post(f"/api/apps/{app_id}/start").json()
    assert started["status"] == "running"
    assert isinstance(started["pid"], int)
    pid = started["pid"]
    assert _alive(pid)
    assert started["started_at"] is not None
    assert started["uptime_s"] is not None

    # Logs appear as the child runs.
    assert wait_until(
        lambda: any("hello from demo" in line for line in client.get(
            f"/api/apps/{app_id}/logs").json()["lines"])
    )

    again = client.post(f"/api/apps/{app_id}/start")
    assert again.status_code == 409

    current = _state(client, app_id)
    assert current["status"] == "running"
    assert current["pid"] == pid

    stopped = client.post(f"/api/apps/{app_id}/stop").json()
    assert stopped["status"] == "stopped"
    assert stopped["pid"] is None
    assert stopped["uptime_s"] is None
    assert wait_until(lambda: not _alive(pid))

    restarted = client.post(f"/api/apps/{app_id}/restart").json()
    assert restarted["status"] == "running"
    assert isinstance(restarted["pid"], int)
    assert restarted["pid"] != pid
    new_pid = restarted["pid"]

    client.post(f"/api/apps/{app_id}/stop")
    assert wait_until(lambda: not _alive(new_pid))


def test_restart_starts_a_stopped_app(client, demo_dir):
    app = _register(client, "Restart Me", demo_dir, sleep_cmd(30))
    response = client.post(f"/api/apps/{app['id']}/restart")
    assert response.status_code == 200
    assert response.json()["pid"]
    client.post(f"/api/apps/{app['id']}/stop")


def test_stop_when_not_running_is_ok(client, demo_dir):
    app = _register(client, "Idle", demo_dir, sleep_cmd(30))
    response = client.post(f"/api/apps/{app['id']}/stop")
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"


def test_start_without_command_is_400(client, tmp_path):
    empty = tmp_path / "empty-app"
    empty.mkdir()
    app = _register(client, "No Command", empty)
    assert app["command"] == ""
    response = client.post(f"/api/apps/{app['id']}/start")
    assert response.status_code == 400
    assert "command" in response.json()["detail"]


def test_logs_tail_parameter(client, demo_dir):
    command = f"{sys.executable} -u {demo_dir / 'script.py'}"
    app = _register(client, "Loggy", demo_dir, command)
    client.post(f"/api/apps/{app['id']}/start")
    assert wait_until(
        lambda: len(client.get(f"/api/apps/{app['id']}/logs?tail=10").json()["lines"]) >= 3
    )
    lines = client.get(f"/api/apps/{app['id']}/logs?tail=2").json()["lines"]
    assert len(lines) == 2
    assert client.get(f"/api/apps/{app['id']}/logs?tail=0").json()["lines"] == []
    assert client.get(f"/api/apps/{app['id']}/logs?tail=-1").status_code == 422
    client.post(f"/api/apps/{app['id']}/stop")


def test_env_reaches_the_process(client, demo_dir):
    command = f"{sys.executable} -u {demo_dir / 'script.py'}"
    app = _register(client, "Env App", demo_dir, command, env={"FOO": "bar-baz"})
    client.post(f"/api/apps/{app['id']}/start")
    assert wait_until(
        lambda: any(
            "FOO=bar-baz" in line
            for line in client.get(f"/api/apps/{app['id']}/logs").json()["lines"]
        )
    )
    client.post(f"/api/apps/{app['id']}/stop")


def test_crash_is_reported(client, tmp_path):
    directory = tmp_path / "crashy"
    directory.mkdir()
    _script(
        directory,
        "crash.py",
        "print('about to die', flush=True)\n"
        "import time; time.sleep(0.3)\n"
        "raise SystemExit(7)\n",
    )
    app = _register(client, "Crashy", directory, f"{sys.executable} -u {directory / 'crash.py'}")
    client.post(f"/api/apps/{app['id']}/start")

    assert wait_until(lambda: _state(client, app["id"])["status"] == "crashed", timeout=10)
    state = _state(client, app["id"])
    assert state["pid"] is None
    assert state["last_exit_code"] == 7
    assert state["last_error"]
    assert "about to die" in state["last_error"] or "7" in state["last_error"]


def test_auto_restart_brings_back_a_crashed_app(client, tmp_path):
    directory = tmp_path / "autorestart"
    directory.mkdir()
    _script(
        directory,
        "crash.py",
        "import time; time.sleep(0.2); raise SystemExit(5)\n",
    )
    app = _register(
        client,
        "Auto Restart",
        directory,
        f"{sys.executable} -u {directory / 'crash.py'}",
        auto_restart=True,
    )
    client.post(f"/api/apps/{app['id']}/start")

    assert wait_until(lambda: _state(client, app["id"])["restarts"] >= 1, timeout=10)
    # Stop (and suppress further restarts) before teardown.
    client.post(f"/api/apps/{app['id']}/stop")
    state = _state(client, app["id"])
    assert state["status"] in {"stopped", "crashed"}


def test_user_stop_is_not_auto_restarted(client, demo_dir):
    app = _register(
        client,
        "No Restart",
        demo_dir,
        f"{sys.executable} -u {demo_dir / 'script.py'}",
        auto_restart=True,
    )
    client.post(f"/api/apps/{app['id']}/start")
    stopped = client.post(f"/api/apps/{app['id']}/stop").json()
    assert stopped["status"] == "stopped"

    # Give the ticker a couple of chances to (incorrectly) restart it.
    import time as _time

    _time.sleep(1.5)
    state = _state(client, app["id"])
    assert state["status"] == "stopped"
    assert state["restarts"] == 0


# ---------------------------------------------------------------------------
# patch / delete
# ---------------------------------------------------------------------------
def test_patch_app(client, demo_dir):
    app = _register(client, "Patchable", demo_dir, sleep_cmd(30))
    response = client.patch(
        f"/api/apps/{app['id']}",
        json={
            "name": "Patched Name",
            "command": sleep_cmd(31),
            "port": 9000,
            "health_url": "http://127.0.0.1:9000/",
            "auto_restart": True,
            "env": {"X": "y"},
        },
    )
    assert response.status_code == 200
    state = response.json()
    assert state["name"] == "Patched Name"
    assert state["id"] == app["id"]  # id never changes on rename
    assert state["command"] == sleep_cmd(31)
    assert state["port"] == 9000
    assert state["health_url"] == "http://127.0.0.1:9000/"
    assert state["auto_restart"] is True

    # Partial patch leaves everything else alone.
    only_port = client.patch(f"/api/apps/{app['id']}", json={"port": None}).json()
    assert only_port["port"] is None
    assert only_port["command"] == sleep_cmd(31)


@pytest.mark.parametrize(
    "patch, fragment",
    [
        ({"name": "   "}, "name"),
        ({"name": None}, "name"),
        ({"path": "/no/such/dir"}, "not a directory"),
        ({"command": 5}, "command"),
        ({"port": "nope"}, "port"),
        ({"port": 99999}, "port out of range"),
        ({"health_url": 5}, "health_url"),
        ({"env": []}, "env"),
    ],
)
def test_patch_validation(client, demo_dir, patch, fragment):
    app = _register(client, "Validations", demo_dir, sleep_cmd(30))
    response = client.patch(f"/api/apps/{app['id']}", json=patch)
    assert response.status_code == 400, (patch, response.text)
    assert fragment in response.json()["detail"]


def test_patch_duplicate_name_is_400(client, demo_dir):
    _register(client, "First App", demo_dir, sleep_cmd(1))
    second = _register(client, "Second App", demo_dir, sleep_cmd(1))
    response = client.patch(f"/api/apps/{second['id']}", json={"name": "first app"})
    assert response.status_code == 400


def test_delete_stops_process_and_removes_app(client, demo_dir, isolated_registry):
    command = f"{sys.executable} -u {demo_dir / 'script.py'}"
    app = _register(client, "Deletable", demo_dir, command)
    pid = client.post(f"/api/apps/{app['id']}/start").json()["pid"]

    response = client.delete(f"/api/apps/{app['id']}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert wait_until(lambda: not _alive(pid))
    assert client.get("/api/apps").json() == []
    assert json.loads(Path(isolated_registry.path).read_text(encoding="utf-8")) == []


# ---------------------------------------------------------------------------
# SSE
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="TestClient blocks on endless SSE streams; covered manually in the browser")
def test_events_stream_sends_json_snapshot(client, demo_dir):
    _register(client, "SSE App", demo_dir, sleep_cmd(30))

    with client.stream("GET", "/api/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        data_line = None
        for line in response.iter_lines():
            if line.startswith("data: "):
                data_line = line
                break
    assert data_line is not None
    payload = json.loads(data_line[len("data: "):])
    assert isinstance(payload, list)
    assert payload and payload[0]["id"] == "sse-app"
    assert payload[0]["status"] == "stopped"
