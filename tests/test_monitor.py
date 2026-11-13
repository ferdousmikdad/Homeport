"""Tests for backend.monitor: pure helpers, detection and probes."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from backend import monitor

from _helpers import wait_until

NOW = 1_000_000.0


# ---------------------------------------------------------------------------
# compute_status
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "info, port_ok, expected",
    [
        # never started / stopped by the user
        ({"running": False, "pid": None, "exit_code": None, "user_stopped": False}, None, "stopped"),
        ({"running": False, "pid": None, "exit_code": None, "user_stopped": True}, False, "stopped"),
        ({"running": False, "pid": 42, "exit_code": 0, "user_stopped": True}, None, "stopped"),
        # died without a user stop -> crashed (regardless of port probe)
        ({"running": False, "pid": 42, "exit_code": 1, "user_stopped": False}, None, "crashed"),
        ({"running": False, "pid": 42, "exit_code": 0, "user_stopped": False}, False, "crashed"),
        # alive, port closed -> starting during the grace period
        ({"running": True, "pid": 42, "started_at": NOW - 1, "user_stopped": False}, False, "starting"),
        ({"running": True, "pid": 42, "started_at": NOW - 29.9, "user_stopped": False}, False, "starting"),
        # grace exhausted while still alive -> running anyway
        ({"running": True, "pid": 42, "started_at": NOW - 30.0, "user_stopped": False}, False, "running"),
        ({"running": True, "pid": 42, "started_at": NOW - 300, "user_stopped": False}, False, "running"),
        # port open or nothing to probe -> running
        ({"running": True, "pid": 42, "started_at": NOW - 1, "user_stopped": False}, True, "running"),
        ({"running": True, "pid": 42, "started_at": NOW - 1, "user_stopped": False}, None, "running"),
    ],
)
def test_compute_status_table(info, port_ok, expected):
    assert monitor.compute_status({"port": 8123}, info, port_ok, NOW) == expected


def test_compute_status_custom_grace_and_missing_started_at():
    info = {"running": True, "pid": 1, "started_at": NOW - 5, "user_stopped": False}
    assert monitor.compute_status({}, info, False, NOW, grace=10) == "starting"
    assert monitor.compute_status({}, info, False, NOW, grace=4) == "running"

    no_start = {"running": True, "pid": 1, "started_at": None}
    assert monitor.compute_status({}, no_start, False, NOW) == "starting"
    assert monitor.compute_status({}, no_start, True, NOW) == "running"


# ---------------------------------------------------------------------------
# should_auto_restart
# ---------------------------------------------------------------------------
CRASHED = {"running": False, "pid": 9, "exit_code": 1, "user_stopped": False}


def test_should_auto_restart_table():
    on = {"auto_restart": True}
    assert monitor.should_auto_restart(on, CRASHED, 0) is True
    assert monitor.should_auto_restart(on, CRASHED, 4) is True
    assert monitor.should_auto_restart(on, CRASHED, 5) is False
    assert monitor.should_auto_restart(on, CRASHED, 99) is False

    assert monitor.should_auto_restart({"auto_restart": False}, CRASHED, 0) is False
    assert monitor.should_auto_restart({}, CRASHED, 0) is False
    assert monitor.should_auto_restart(on, {**CRASHED, "user_stopped": True}, 0) is False
    assert monitor.should_auto_restart(on, {**CRASHED, "running": True}, 0) is False
    # never started -> nothing to restart
    assert monitor.should_auto_restart(on, {"running": False, "pid": None, "exit_code": None}, 0) is False
    # exit code 0 still counts as "exited without a user stop"
    assert monitor.should_auto_restart(on, {**CRASHED, "exit_code": 0}, 0) is True


# ---------------------------------------------------------------------------
# port_open
# ---------------------------------------------------------------------------
def test_port_open_true_and_false():
    server = socket.create_server(("127.0.0.1", 0), backlog=5)
    port = server.getsockname()[1]
    try:
        assert monitor.port_open(port, timeout=1.0) is True
    finally:
        server.close()
    assert monitor.port_open(port, timeout=0.2) is False
    assert monitor.port_open(1, timeout=0.2) is False


# ---------------------------------------------------------------------------
# process_tree_stats / listening_ports
# ---------------------------------------------------------------------------
def _spawn_listener(script_text: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-u", "-c", script_text],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def test_process_tree_stats_sums_root_and_child():
    script = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        "print('ready', flush=True)\n"
        "child.wait()\n"
    )
    proc = _spawn_listener(script)
    try:
        assert proc.stdout.readline().strip() == "ready"
        assert wait_until(lambda: len(monitor._tree_pids(proc.pid)) >= 2)
        stats = monitor.process_tree_stats(proc.pid)
        assert set(stats) == {"cpu_percent", "mem_mb"}
        assert stats["cpu_percent"] >= 0
        assert stats["mem_mb"] > 0
    finally:
        proc.kill()
        proc.wait()


def test_process_tree_stats_gone_pid():
    assert monitor.process_tree_stats(-1234) == {}
    assert monitor.process_tree_stats(0) == {}
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    assert monitor.process_tree_stats(proc.pid) == {}


def test_listening_ports_finds_child_listener():
    script = (
        "import socket, sys, time\n"
        "s = socket.socket()\n"
        "s.bind(('127.0.0.1', 0))\n"
        "s.listen(5)\n"
        "print(s.getsockname()[1], flush=True)\n"
        "time.sleep(30)\n"
    )
    proc = _spawn_listener(script)
    try:
        port = int(proc.stdout.readline().strip())
        assert wait_until(lambda: port in monitor.listening_ports(proc.pid))
        ports = monitor.listening_ports(proc.pid)
        assert port in ports
        assert all(1 <= p <= 65535 for p in ports)
    finally:
        proc.kill()
        proc.wait()
    assert monitor.listening_ports(-1234) == []


def test_listening_ports_includes_descendant():
    script = (
        "import socket, subprocess, sys, time\n"
        "code = \"import socket,time; s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen(5); print(s.getsockname()[1], flush=True); time.sleep(30)\"\n"
        "child = subprocess.Popen([sys.executable, '-u', '-c', code], stdout=subprocess.PIPE, text=True)\n"
        "print(child.stdout.readline().strip(), flush=True)\n"
        "child.wait()\n"
    )
    proc = _spawn_listener(script)
    try:
        port = int(proc.stdout.readline().strip())
        assert wait_until(lambda: port in monitor.listening_ports(proc.pid))
    finally:
        proc.kill()
        proc.wait()


# ---------------------------------------------------------------------------
# http_healthy
# ---------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        code = {"/ok": 200, "/redirect": 302, "/bad": 500, "/missing": 404}.get(self.path, 200)
        self.send_response(code)
        if code == 302:
            self.send_header("Location", "/ok")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


@pytest.fixture
def http_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    "path, expected",
    [("/ok", True), ("/missing", True), ("/bad", False), ("/redirect", True)],
)
def test_http_healthy_status_rules(http_server, path, expected):
    assert asyncio.run(monitor.http_healthy(http_server + path, timeout=2.0)) is expected


def test_http_healthy_unreachable_is_false():
    server = socket.create_server(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.close()
    assert asyncio.run(monitor.http_healthy(f"http://127.0.0.1:{port}/", timeout=0.5)) is False


# ---------------------------------------------------------------------------
# detect_command
# ---------------------------------------------------------------------------
def test_detect_command_python_entry_priority(tmp_path):
    (tmp_path / "main.py").write_text("print('main')")
    (tmp_path / "server.py").write_text("print('server')")
    (tmp_path / "run.py").write_text("print('run')")
    result = monitor.detect_command(str(tmp_path))
    assert result["command"] == "python3 run.py"

    (tmp_path / "run.py").unlink()
    assert monitor.detect_command(str(tmp_path))["command"] == "python3 server.py"


def test_detect_command_npm_scripts(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"start": "node app.js"}}))
    assert monitor.detect_command(str(tmp_path))["command"] == "PORT=3000 npm run start"

    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"dev": "vite", "start": "node app.js"}})
    )
    assert monitor.detect_command(str(tmp_path))["command"] == (
        "npm run dev -- --port 5173 --strictPort"
    )


def test_detect_command_command_file(tmp_path):
    (tmp_path / "b.command").write_text("#!/bin/bash\n")
    (tmp_path / "a.command").write_text("#!/bin/bash\n")
    assert monitor.detect_command(str(tmp_path))["command"] == "bash 'a.command'"


def test_detect_command_nothing_and_missing_dir(tmp_path):
    empty = {"command": None, "port": None, "type": None}
    assert monitor.detect_command(str(tmp_path)) == empty
    assert monitor.detect_command(str(tmp_path / "does-not-exist")) == empty


def test_detect_command_broken_package_json_falls_back(tmp_path):
    (tmp_path / "package.json").write_text("{not json")
    (tmp_path / "main.py").write_text("print('x')")
    assert monitor.detect_command(str(tmp_path))["command"] == "python3 main.py"


def test_detect_command_port_patterns(tmp_path):
    (tmp_path / "README.md").write_text("Open http://localhost:9123/ to use it.\n")
    (tmp_path / "server.py").write_text("print('hi')")
    assert monitor.detect_command(str(tmp_path)) == {
        "command": "python3 server.py",
        "port": 9123,
        "type": "Python",
    }

    other = tmp_path / "other"
    other.mkdir()
    (other / "server.py").write_text("# serve on port 8123\n")
    assert monitor.detect_command(str(other))["port"] == 8123

    third = tmp_path / "third"
    third.mkdir()
    (third / "server.py").write_text('PORT = "8456"\n')
    assert monitor.detect_command(str(third))["port"] == 8456


def test_detect_command_ignores_reserved_ports(tmp_path):
    (tmp_path / "main.py").write_text("PORT = 5432\n# nothing web-ish here\n")
    assert monitor.detect_command(str(tmp_path))["port"] is None


def test_detect_command_skips_huge_files(tmp_path):
    (tmp_path / "main.py").write_text("print('x')")
    (tmp_path / "big.js").write_text("x" * (513 * 1024) + "\nlocalhost:9999\n")
    assert monitor.detect_command(str(tmp_path))["port"] is None
