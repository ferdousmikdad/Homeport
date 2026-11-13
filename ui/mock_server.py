#!/usr/bin/env python3
"""Stdlib-only mock of the Homeport API for UI development.

The real backend (backend/main.py) needs workers A/B/C to be finished.  This
script lets the UI be built and tested independently, per SPEC.md:

    .venv/bin/python ui/mock_server.py            # http://localhost:7778

It serves the static files in this directory at `/` as a convenience, so the
dashboard can be opened directly at http://localhost:7778/ (no ?api= needed).
Any other UI server may point at it with ?api=http://localhost:7778.

Endpoints (same contract as the real API):
    GET    /api/health
    GET    /api/apps
    POST   /api/apps
    GET    /api/apps/{id}
    PATCH  /api/apps/{id}
    DELETE /api/apps/{id}
    POST   /api/apps/{id}/start|stop|restart
    GET    /api/apps/{id}/logs?tail=200
    GET    /api/detect?path=...
    GET    /api/events            (SSE, one event per second)

CORS is wide open so the UI can also be served from file:// or another port.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import random
import re
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

UI_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(UI_DIR)
SAMPLE_BASE = os.path.join(os.path.dirname(PROJECT_DIR), "Test app directorey")

STATIC_TYPES = {
    ".html",
    ".js",
    ".mjs",
    ".css",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".json",
    ".map",
    ".woff",
    ".woff2",
    ".ttf",
}

PY_ENTRYPOINTS = ("run.py", "launch.py", "server.py", "app.py", "main.py")
PORT_PATTERNS = (
    re.compile(r"localhost:(\d{2,5})", re.IGNORECASE),
    re.compile(r"\bport\b\s*[:=]?\s*(\d{2,5})", re.IGNORECASE),
    re.compile(r"\bPORT\s*=\s*(\d{2,5})"),
)

RUNNING_LOG_LINES = (
    "INFO  GET / 200 4ms",
    "INFO  GET /api/status 200 2ms",
    "INFO  heartbeat ok",
    "INFO  GET /static/app.js 304 0ms",
    "INFO  POST /api/refresh 202 12ms",
    "DEBUG worker tick: 3 jobs, 0 failed",
    "INFO  GET /api/items?limit=20 200 7ms",
)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "app"


def _safe_port(value):
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if 0 < port < 65536:
        return port
    return None


def detect_command(path: str) -> dict:
    """Small stdlib imitation of backend.monitor.detect_command."""
    command = None
    port = None

    if os.path.isdir(path):
        for filename in PY_ENTRYPOINTS:
            if os.path.isfile(os.path.join(path, filename)):
                command = "python3 " + filename
                break

        if command is None:
            package_json = os.path.join(path, "package.json")
            if os.path.isfile(package_json):
                try:
                    with open(package_json, "r", encoding="utf-8", errors="replace") as fh:
                        pkg = json.load(fh)
                    scripts = pkg.get("scripts") or {}
                    for script in ("dev", "start"):
                        if isinstance(scripts, dict) and script in scripts:
                            command = "npm run " + script
                            break
                except (OSError, ValueError):
                    pass

        if command is None:
            try:
                names = sorted(os.listdir(path))
            except OSError:
                names = []
            for filename in names:
                if filename.endswith(".command"):
                    command = "bash '" + filename + "'"
                    break

        port = _scan_port(path)

    return {"command": command, "port": port}


def _scan_port(path: str):
    try:
        names = sorted(os.listdir(path))
    except OSError:
        return None

    readme = [n for n in names if n.lower().startswith("readme")]
    others = [
        n
        for n in names
        if n not in readme
        and os.path.splitext(n)[1].lower()
        in {".py", ".js", ".mjs", ".json", ".sh", ".command", ".md", ".env", ".toml", ".yaml", ".yml"}
    ]

    for filename in readme + others:
        full = os.path.join(path, filename)
        if not os.path.isfile(full):
            continue
        try:
            if os.path.getsize(full) > 400_000:
                continue
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        for pattern in PORT_PATTERNS:
            for match in pattern.finditer(text):
                port = _safe_port(match.group(1))
                if port:
                    return port
    return None


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _mock_color(value) -> str:
    text = value.strip().lower() if isinstance(value, str) else value
    if text in (None, ""):
        return ""
    if text not in ("red", "green", "blue"):
        raise ApiError(400, "color must be one of: red, green, blue")
    return text


class MockState:
    """In-memory apps + fake runtime, guarded by one lock."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.apps: dict[str, dict] = {}
        self.order: list[str] = []
        self.logs: dict[str, list[str]] = {}
        self._stop = threading.Event()
        self._seed()
        self._thread = threading.Thread(target=self._tick_loop, name="mock-tick", daemon=True)
        self._thread.start()

    # -- seeding ------------------------------------------------------

    def _sample_path(self, name: str) -> str:
        candidate = os.path.join(SAMPLE_BASE, name)
        return candidate if os.path.isdir(candidate) else "/tmp"

    def _seed(self) -> None:
        now = time.time()

        insight = self._insert(
            name="insight-studio",
            path=self._sample_path("insight-studio"),
            command="python3 run.py",
            port=8795,
            health_url="http://localhost:8795/",
            auto_restart=True,
            status="running",
            pid=48213,
            started_at=now - 3725.0,
            restarts=0,
            cpu_percent=2.4,
            mem_mb=118.7,
        )
        insight["detected_port"] = 8795
        insight["healthy"] = True
        self._append_log(
            insight["id"],
            [
                "INFO  starting insight-studio (cwd=" + insight["path"] + ")",
                "INFO  loaded 14 plugins from ./server/plugins",
                "INFO  database ready: ./data/insight.db",
                "INFO  listening on http://localhost:8795",
                "INFO  GET / 200 6ms",
                "INFO  GET /api/projects 200 11ms",
            ],
        )

        opus = self._insert(
            name="opus-watch",
            path=self._sample_path("opus-watch"),
            command="python3 launch.py",
            port=8791,
            health_url="http://localhost:8791/",
            auto_restart=False,
            status="stopped",
            pid=None,
            started_at=None,
            restarts=1,
            last_exit_code=0,
        )
        self._append_log(
            opus["id"],
            [
                "INFO  starting opus-watch (cwd=" + opus["path"] + ")",
                "INFO  loaded providers: anthropic, openai",
                "INFO  listening on http://localhost:8791",
                "INFO  received SIGTERM — shutting down",
                "INFO  bye",
            ],
        )

        prompt = self._insert(
            name="prompt-scheduler",
            path=self._sample_path("prompt-scheduler"),
            command="python3 server.py",
            port=8790,
            health_url="http://localhost:8790/",
            auto_restart=False,
            status="crashed",
            pid=None,
            started_at=None,
            restarts=3,
            last_exit_code=1,
            last_error="ModuleNotFoundError: No module named 'apscheduler'",
        )
        self._append_log(
            prompt["id"],
            [
                "INFO  starting prompt-scheduler (cwd=" + prompt["path"] + ")",
                "Traceback (most recent call last):",
                '  File "server.py", line 12, in <module>',
                "    from apscheduler.schedulers.background import BackgroundScheduler",
                "ModuleNotFoundError: No module named 'apscheduler'",
                "ERROR process exited with code 1",
            ],
        )

    def _insert(self, *, name, path, command, port, health_url, auto_restart, **runtime) -> dict:
        app_id = self._unique_slug(name)
        app = {
            "id": app_id,
            "name": name,
            "path": path,
            "command": command,
            "port": port,
            "health_url": health_url,
            "auto_restart": bool(auto_restart),
            "autostart": bool(runtime.get("autostart", False)),
            "notify": bool(runtime.get("notify", True)),
            "description": str(runtime.get("description", "")),
            "category": str(runtime.get("category", "")),
            "color": str(runtime.get("color", "")),
            "created_at": runtime.get("created_at"),
            "updated_at": runtime.get("updated_at"),
            "env": {},
            "status": "stopped",
            "pid": None,
            "started_at": None,
            "restarts": 0,
            "last_exit_code": None,
            "last_error": None,
            "detected_port": None,
            "healthy": None,
            "cpu_percent": None,
            "mem_mb": None,
            "_started_ts": None,
            "_log_at": 0.0,
        }
        app.update(runtime)
        if app["started_at"] is not None:
            app["_started_ts"] = app["started_at"]
        self.apps[app_id] = app
        self.order.append(app_id)
        self.logs[app_id] = []
        return app

    def reorder(self, ids: list[str]) -> list[dict]:
        with self.lock:
            listed = [i for i in dict.fromkeys(ids) if i in self.apps]
            self.order = listed + [i for i in self.order if i not in listed]
        return self.snapshot()

    def _unique_slug(self, name: str) -> str:
        base = slugify(name)
        candidate = base
        index = 2
        while candidate in self.apps:
            candidate = base + "-" + str(index)
            index += 1
        return candidate

    # -- state views --------------------------------------------------

    def _state(self, app: dict, now: float) -> dict:
        started = app.get("started_at")
        uptime = None
        if app["status"] in ("running", "starting") and isinstance(started, (int, float)):
            uptime = round(max(0.0, now - started), 1)
        return {
            "id": app["id"],
            "name": app["name"],
            "path": app["path"],
            "command": app["command"],
            "port": app["port"],
            "health_url": app["health_url"],
            "description": app.get("description", ""),
            "category": app.get("category", ""),
            "color": app.get("color", ""),
            "created_at": app.get("created_at"),
            "updated_at": app.get("updated_at"),
            "auto_restart": app["auto_restart"],
            "autostart": bool(app.get("autostart", False)),
            "notify": bool(app.get("notify", True)),
            "status": app["status"],
            "pid": app["pid"],
            "started_at": started,
            "uptime_s": uptime,
            "cpu_percent": app["cpu_percent"],
            "mem_mb": app["mem_mb"],
            "detected_port": app["detected_port"],
            "healthy": app["healthy"],
            "restarts": app["restarts"],
            "last_exit_code": app["last_exit_code"],
            "last_error": app["last_error"],
            "port_conflict": app.get("port_conflict"),
        }

    def snapshot(self) -> list[dict]:
        with self.lock:
            now = time.time()
            return [self._state(self.apps[app_id], now) for app_id in self.order]

    def get(self, app_id: str) -> dict:
        with self.lock:
            app = self.apps.get(app_id)
            if app is None:
                raise ApiError(404, "unknown app id")
            return self._state(app, time.time())

    # -- mutations ----------------------------------------------------

    def create(self, body: dict) -> dict:
        name = body.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ApiError(400, "name is required")
        name = name.strip()

        path = body.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ApiError(400, "path is required")
        path = os.path.abspath(os.path.expanduser(path.strip()))
        if not os.path.isdir(path):
            raise ApiError(400, "path is not a directory")

        with self.lock:
            for app in self.apps.values():
                if app["name"].casefold() == name.casefold():
                    raise ApiError(400, "an app with this name already exists")

            command = body.get("command")
            if command is not None and not isinstance(command, str):
                raise ApiError(400, "command must be a string")
            command = (command or "").strip() or detect_command(path)["command"]

            port = _safe_port(body.get("port")) if body.get("port") not in (None, "") else None
            if body.get("port") not in (None, "") and port is None:
                raise ApiError(400, "port must be an integer between 1 and 65535")
            if port is None:
                port = detect_command(path)["port"]

            health_url = body.get("health_url")
            if health_url is not None and not isinstance(health_url, str):
                raise ApiError(400, "health_url must be a string")
            health_url = (health_url or "").strip() or None

            env = body.get("env") or {}
            if not isinstance(env, dict):
                raise ApiError(400, "env must be an object")
            env = {str(k): str(v) for k, v in env.items()}

            app = self._insert(
                name=name,
                path=path,
                command=command,
                port=port,
                health_url=health_url,
                auto_restart=bool(body.get("auto_restart", False)),
                autostart=bool(body.get("autostart", False)),
                notify=bool(body.get("notify", True)),
                description=str(body.get("description", "")),
                category=str(body.get("category") or "").strip(),
                color=_mock_color(body.get("color")),
                created_at=body.get("created_at") or time.time(),
                updated_at=body.get("updated_at") or time.time(),
            )
            app["env"] = env
            self._append_log(app["id"], ["INFO  registered via mock API"])
            return self._state(app, time.time())

    def update(self, app_id: str, patch: dict) -> dict:
        with self.lock:
            app = self.apps.get(app_id)
            if app is None:
                raise ApiError(404, "unknown app id")

            if "name" in patch:
                name = patch["name"]
                if not isinstance(name, str) or not name.strip():
                    raise ApiError(400, "name must be a non-empty string")
                name = name.strip()
                for other in self.apps.values():
                    if other["id"] != app_id and other["name"].casefold() == name.casefold():
                        raise ApiError(400, "an app with this name already exists")
                app["name"] = name

            if "path" in patch:
                path = patch["path"]
                if not isinstance(path, str) or not path.strip():
                    raise ApiError(400, "path must be a non-empty string")
                path = os.path.abspath(os.path.expanduser(path.strip()))
                if not os.path.isdir(path):
                    raise ApiError(400, "path is not a directory")
                app["path"] = path

            if "command" in patch:
                if not isinstance(patch["command"], str):
                    raise ApiError(400, "command must be a string")
                app["command"] = patch["command"]

            if "port" in patch:
                if patch["port"] in (None, ""):
                    app["port"] = None
                else:
                    port = _safe_port(patch["port"])
                    if port is None:
                        raise ApiError(400, "port must be an integer between 1 and 65535")
                    app["port"] = port

            if "health_url" in patch:
                value = patch["health_url"]
                if value is not None and not isinstance(value, str):
                    raise ApiError(400, "health_url must be a string or null")
                app["health_url"] = (value or "").strip() or None

            if "description" in patch:
                desc = patch["description"]
                if desc is not None and not isinstance(desc, str):
                    raise ApiError(400, "description must be a string")
                app["description"] = (desc or "").strip()

            if "category" in patch:
                category = patch["category"]
                if category is not None and not isinstance(category, str):
                    raise ApiError(400, "category must be a string")
                app["category"] = (category or "").strip()

            if "color" in patch:
                app["color"] = _mock_color(patch["color"])

            if "created_at" in patch:
                app["created_at"] = patch["created_at"]

            if "updated_at" in patch:
                app["updated_at"] = patch["updated_at"]

            if "auto_restart" in patch:
                app["auto_restart"] = bool(patch["auto_restart"])

            if "autostart" in patch:
                app["autostart"] = bool(patch["autostart"])

            if "notify" in patch:
                app["notify"] = bool(patch["notify"])

            if "env" in patch:
                env = patch["env"] or {}
                if not isinstance(env, dict):
                    raise ApiError(400, "env must be an object")
                app["env"] = {str(k): str(v) for k, v in env.items()}

            was_running = app["status"] in ("running", "starting")
            st = self._state(app, time.time())
            if was_running:
                st["needs_restart"] = True
            return st

    def remove(self, app_id: str) -> dict:
        with self.lock:
            if app_id not in self.apps:
                raise ApiError(404, "unknown app id")
            app = self.apps[app_id]
            app["status"] = "stopped"
            app["pid"] = None
            del self.apps[app_id]
            self.order = [a for a in self.order if a != app_id]
            self.logs.pop(app_id, None)
            return {"ok": True}

    def start_all(self) -> list[dict]:
        with self.lock:
            for app in self.apps.values():
                if app["status"] not in ("running", "starting") and app.get("command"):
                    self._spawn(app, restart=False)
            return self.snapshot()

    def stop_all(self) -> list[dict]:
        with self.lock:
            for app in self.apps.values():
                if app["status"] in ("running", "starting"):
                    self._halt(app, user_stopped=True)
            return self.snapshot()

    def clear_logs(self, app_id: str) -> dict:
        with self.lock:
            if app_id not in self.apps:
                raise ApiError(404, "unknown app id")
            self.logs[app_id] = []
            return {"ok": True}

    def action(self, app_id: str, action: str) -> dict:
        with self.lock:
            app = self.apps.get(app_id)
            if app is None:
                raise ApiError(404, "unknown app id")

            if action == "start":
                if app["status"] in ("running", "starting"):
                    raise ApiError(409, "app is already running")
                self._spawn(app, restart=False)
            elif action == "restart":
                self._spawn(app, restart=True)
            elif action == "stop":
                self._halt(app, user_stopped=True)
            else:
                raise ApiError(404, "unknown action")

            return self._state(app, time.time())

    def _spawn(self, app: dict, restart: bool) -> None:
        if not os.path.isdir(app["path"]):
            raise ApiError(400, "path is not a directory")
        now = time.time()
        app["status"] = "starting"
        app["pid"] = random.randint(20000, 64000)
        app["started_at"] = now
        app["_started_ts"] = now
        app["detected_port"] = None
        app["healthy"] = None
        app["last_exit_code"] = None
        app["last_error"] = None
        app["cpu_percent"] = round(random.uniform(0.3, 1.8), 1)
        app["mem_mb"] = round(random.uniform(28.0, 74.0), 1)
        app["_log_at"] = 0.0
        if restart:
            app["restarts"] = int(app.get("restarts") or 0) + 1
            self._append_log(app["id"], ["INFO  restart requested by user"])
        stamp = time.strftime("%H:%M:%S")
        self._append_log(
            app["id"],
            [
                "[" + stamp + "] INFO  starting: " + str(app["command"]),
                "[" + stamp + "] INFO  cwd: " + str(app["path"]),
            ],
        )

    def _halt(self, app: dict, user_stopped: bool) -> None:
        if app["status"] not in ("running", "starting"):
            return
        stamp = time.strftime("%H:%M:%S")
        app["status"] = "stopped"
        app["pid"] = None
        app["started_at"] = None
        app["detected_port"] = None
        app["healthy"] = None
        app["cpu_percent"] = None
        app["mem_mb"] = None
        app["last_exit_code"] = 0
        self._append_log(
            app["id"],
            ["[" + stamp + "] INFO  stopped" + (" by user" if user_stopped else "")],
        )

    # -- logs ---------------------------------------------------------

    def _append_log(self, app_id: str, lines: list[str]) -> None:
        buf = self.logs.setdefault(app_id, [])
        buf.extend(str(line) for line in lines)
        if len(buf) > 400:
            del buf[: len(buf) - 400]

    def logs_tail(self, app_id: str, tail: int) -> dict:
        with self.lock:
            if app_id not in self.apps:
                raise ApiError(404, "unknown app id")
            buf = self.logs.get(app_id, [])
            tail = max(1, min(int(tail or 200), 1000))
            return {"lines": list(buf[-tail:])}

    # -- background simulation ---------------------------------------

    def _tick_loop(self) -> None:
        while not self._stop.wait(1.0):
            try:
                self._tick()
            except Exception:  # pragma: no cover - mock only
                traceback.print_exc()

    def _tick(self) -> None:
        now = time.time()
        with self.lock:
            for app in self.apps.values():
                if app["status"] == "starting":
                    started = app.get("_started_ts") or now
                    if now - started >= 1.0:
                        app["status"] = "running"
                        app["detected_port"] = app.get("port")
                        app["healthy"] = True if app.get("health_url") else None
                        stamp = time.strftime("%H:%M:%S")
                        port = app.get("detected_port")
                        self._append_log(
                            app["id"],
                            [
                                "[" + stamp + "] INFO  ready"
                                + (" — listening on http://localhost:" + str(port) if port else "")
                            ],
                        )
                elif app["status"] == "running":
                    cpu = app.get("cpu_percent")
                    if not isinstance(cpu, (int, float)):
                        cpu = 2.0
                    app["cpu_percent"] = round(
                        max(0.1, min(99.0, cpu + random.uniform(-0.7, 0.8))), 1
                    )
                    mem = app.get("mem_mb")
                    if not isinstance(mem, (int, float)):
                        mem = 100.0
                    app["mem_mb"] = round(max(12.0, mem + random.uniform(-1.4, 1.6)), 1)

                    last = app.get("_log_at") or 0.0
                    if now - last >= 3.5:
                        app["_log_at"] = now
                        stamp = time.strftime("%H:%M:%S")
                        self._append_log(
                            app["id"],
                            ["[" + stamp + "] " + random.choice(RUNNING_LOG_LINES)],
                        )

    def shutdown(self) -> None:
        self._stop.set()


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalhostManagerMock/1.0"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # -- plumbing -----------------------------------------------------

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, Accept, Cache-Control"
        )
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "invalid Content-Length")
        if length <= 0:
            return {}
        if length > 1_000_000:
            raise ApiError(413, "request body too large")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ApiError(400, "invalid JSON body")
        if not isinstance(data, dict):
            raise ApiError(400, "JSON object expected")
        return data

    def _guard(self, handler, *args) -> None:
        try:
            handler(*args)
        except ApiError as exc:
            self._send_json(exc.status, {"detail": exc.message})
        except Exception:
            traceback.print_exc()
            self._send_json(500, {"detail": "internal mock error"})

    @property
    def state(self) -> MockState:
        return self.server.state  # type: ignore[attr-defined]

    # -- HTTP verbs ---------------------------------------------------

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        query = parse_qs(parsed.query)
        if parts and parts[0] == "api":
            self._guard(self._api_get, parts[1:], query)
        else:
            self._guard(self._serve_static, parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        if not parts or parts[0] != "api":
            self._send_json(404, {"detail": "not found"})
            return
        self._guard(self._api_post, parts[1:])

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "apps":
            app_id = parts[2]
            self._guard(self._api_patch, app_id)
        else:
            self._send_json(404, {"detail": "not found"})

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "apps":
            self._guard(self._api_delete, parts[2:])
        else:
            self._send_json(404, {"detail": "not found"})

    # -- API ----------------------------------------------------------

    def _api_delete(self, parts: list[str]) -> None:
        if len(parts) == 1:
            self._send_json(200, self.state.remove(parts[0]))
            return
        if len(parts) == 2 and parts[1] == "logs":
            self._send_json(200, self.state.clear_logs(parts[0]))
            return
        raise ApiError(404, "not found")

    def _api_get(self, parts: list[str], query: dict) -> None:
        if parts == ["health"]:
            self._send_json(200, {"ok": True})
            return

        if parts == ["ai", "status"]:
            self._send_json(200, {"available": False, "cli": None, "version": None, "busy": False})
            return

        if parts == ["apps"]:
            self._send_json(200, self.state.snapshot())
            return

        if parts == ["browse"]:
            p = (query.get("path") or [os.path.expanduser("~")])[0]
            target = os.path.abspath(os.path.expanduser(p))
            if not os.path.isdir(target):
                raise ApiError(400, "path is not a directory")
            entries = []
            try:
                for entry in sorted(os.listdir(target)):
                    if entry.startswith("."):
                        continue
                    full = os.path.join(target, entry)
                    if os.path.isdir(full):
                        entries.append({
                            "name": entry,
                            "path": full,
                            "looks_like_app": bool(detect_command(full).get("command")),
                        })
            except OSError:
                pass
            parent = os.path.dirname(target) if target != "/" else None
            self._send_json(200, {"path": target, "parent": parent, "entries": entries})
            return

        if parts == ["detect"]:
            path = (query.get("path") or [""])[0]
            if not path:
                raise ApiError(400, "path query parameter is required")
            self._send_json(200, detect_command(os.path.expanduser(path)))
            return

        if parts == ["events"]:
            self._serve_events()
            return

        if len(parts) == 2 and parts[0] == "apps":
            self._send_json(200, self.state.get(parts[1]))
            return

        if len(parts) == 3 and parts[0] == "apps" and parts[2] == "logs":
            try:
                tail = int((query.get("tail") or ["200"])[0])
            except ValueError:
                tail = 200
            self._send_json(200, self.state.logs_tail(parts[1], tail))
            return

        if len(parts) == 4 and parts[0] == "apps" and parts[2] == "logs" and parts[3] == "download":
            app_id = parts[1]
            lines = self.state.logs_tail(app_id, 10000).get("lines", [])
            body = "\n".join(lines).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{app_id}.log"')
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return

        raise ApiError(404, "not found")

    def _api_post(self, parts: list[str]) -> None:
        if parts == ["ai", "stop"]:
            self._send_json(200, {"stopped": False})
            return

        if parts == ["ai", "ask"]:
            self._send_json(503, {"detail": "the AI assistant is not available in the mock server"})
            return

        if parts == ["apps"]:
            body = self._read_json()
            self._send_json(200, self.state.create(body))
            return

        if parts == ["pick-folder"]:
            # Native folder pick
            cmd = ["osascript", "-e", "POSIX path of (choose folder)"]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60.0)
                if res.returncode == 0:
                    chosen = res.stdout.strip()
                    self._send_json(200, {"path": chosen if chosen and os.path.isdir(chosen) else None})
                    return
                if "-128" in (res.stderr or ""):  # user cancelled
                    self._send_json(200, {"path": None})
                    return
            except subprocess.TimeoutExpired:
                self._send_json(200, {"path": None})
                return
            except OSError:
                pass
            raise ApiError(501, "native folder picker unavailable")

        if parts == ["apps", "reorder"]:
            ids = self._read_json().get("ids")
            if not isinstance(ids, list):
                raise ApiError(400, "ids must be a list of app ids")
            self._send_json(200, self.state.reorder([str(i) for i in ids]))
            return

        if parts == ["apps", "start-all"]:
            self._send_json(200, self.state.start_all())
            return

        if parts == ["apps", "stop-all"]:
            self._send_json(200, self.state.stop_all())
            return

        if len(parts) == 3 and parts[0] == "apps" and parts[2] in ("start", "stop", "restart"):
            self._send_json(200, self.state.action(parts[1], parts[2]))
            return

        if len(parts) == 3 and parts[0] == "apps" and parts[2] == "open":
            body = self._read_json()
            target = body.get("target")
            app_id = parts[1]
            app = self.state.get(app_id)
            if target == "finder":
                subprocess.run(["open", app["path"]])
            elif target == "terminal":
                subprocess.run(["open", "-a", "Terminal", app["path"]])
            elif target == "browser":
                port = app.get("port") or app.get("detected_port")
                if port:
                    subprocess.run(["open", f"http://127.0.0.1:{port}/"])
            self._send_json(200, {"ok": True, "target": target})
            return

        raise ApiError(404, "not found")

    def _api_patch(self, app_id: str) -> None:
        body = self._read_json()
        self._send_json(200, self.state.update(app_id, body))

    def _serve_events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self._cors()
        self.end_headers()
        self.close_connection = True

        try:
            while True:
                payload = json.dumps(self.state.snapshot(), separators=(",", ":"))
                self.wfile.write(("data: " + payload + "\n\n").encode("utf-8"))
                self.wfile.flush()
                time.sleep(1.0)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    # -- static UI ----------------------------------------------------

    def _serve_static(self, url_path: str) -> None:
        rel = unquote(url_path).lstrip("/")
        if rel == "" or rel.endswith("/"):
            rel += "index.html"

        full = os.path.normpath(os.path.join(UI_DIR, rel))
        if full != UI_DIR and not full.startswith(UI_DIR + os.sep):
            self._send_json(403, {"detail": "forbidden"})
            return

        if os.path.isdir(full):
            full = os.path.join(full, "index.html")

        ext = os.path.splitext(full)[1].lower()
        if ext not in STATIC_TYPES or not os.path.isfile(full):
            self._send_json(404, {"detail": "not found"})
            return

        try:
            with open(full, "rb") as fh:
                body = fh.read()
        except OSError:
            self._send_json(404, {"detail": "not found"})
            return

        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ext in (".html", ".js", ".css"):
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self._cors()
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass


class MockServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler):
        self.state = MockState()
        super().__init__(address, handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Homeport UI mock API")
    parser.add_argument("--port", type=int, default=7778, help="port to listen on (default 7778)")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    args = parser.parse_args(argv)

    try:
        server = MockServer((args.host, args.port), Handler)
    except OSError as exc:
        print("Could not bind " + args.host + ":" + str(args.port) + " — " + str(exc), file=sys.stderr)
        return 1

    print("Homeport mock API")
    print("  dashboard : http://localhost:" + str(args.port) + "/")
    print("  API       : http://localhost:" + str(args.port) + "/api/apps")
    print("  override  : ?api=http://localhost:" + str(args.port))
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nStopping mock server.")
    finally:
        server.state.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
