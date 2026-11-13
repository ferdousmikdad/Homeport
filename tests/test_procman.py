"""Tests for backend.procman.ProcessManager (worker A's contract)."""

from __future__ import annotations

import os
import subprocess
import sys
import time

import psutil
import pytest

from backend.procman import ProcessManager

from _helpers import sleep_cmd, wait_until


@pytest.fixture
def pm(tmp_path):
    manager = ProcessManager(log_lines=50, log_dir=str(tmp_path / "logs"))
    try:
        yield manager
    finally:
        manager.shutdown()


def cfg(app_id: str, path, command: str, env: dict[str, str] | None = None) -> dict:
    return {
        "id": app_id,
        "path": str(path),
        "command": command,
        "env": env or {},
    }


def test_start_stop_lifecycle(pm, tmp_path):
    app = cfg("sleeper", tmp_path, sleep_cmd(30))

    pid = pm.start(app)
    assert isinstance(pid, int) and pid > 0
    assert pm.pid("sleeper") == pid
    assert pm.is_running("sleeper") is True

    info = pm.info("sleeper")
    assert info["pid"] == pid
    assert info["running"] is True
    assert info["exit_code"] is None
    assert info["user_stopped"] is False
    assert isinstance(info["started_at"], float)
    assert abs(info["started_at"] - time.time()) < 10

    assert pm.stop("sleeper") is True
    assert pm.is_running("sleeper") is False
    assert pm.pid("sleeper") is None
    finished = pm.info("sleeper")
    assert finished["running"] is False
    assert finished["user_stopped"] is True
    assert finished["exit_code"] is not None

    # Stopping an app that is not running is a no-op, not an error.
    assert pm.stop("sleeper") is False


def test_start_rejects_bad_input(pm, tmp_path):
    with pytest.raises(ValueError, match="path"):
        pm.start(cfg("missing-path", tmp_path / "nope", sleep_cmd(1)))

    file_path = tmp_path / "a-file"
    file_path.write_text("x")
    with pytest.raises(ValueError, match="path"):
        pm.start(cfg("not-a-dir", file_path, sleep_cmd(1)))

    with pytest.raises(ValueError, match="command"):
        pm.start(cfg("no-command", tmp_path, ""))
    with pytest.raises(ValueError, match="command"):
        pm.start(cfg("blank-command", tmp_path, "   "))


def test_double_start_raises(pm, tmp_path):
    app = cfg("twice", tmp_path, sleep_cmd(30))
    pm.start(app)
    with pytest.raises(ValueError, match="already running"):
        pm.start(app)


def test_logs_are_captured_and_tailable(pm, tmp_path):
    app = cfg("logger", tmp_path, sleep_cmd(30))
    script = tmp_path / "log.py"
    script.write_text(
        "import sys\n"
        "for i in range(5):\n"
        "    print(f'line {i}', flush=True)\n"
        "print('to stderr', file=sys.stderr, flush=True)\n"
        "import time; time.sleep(30)\n",
        encoding="utf-8",
    )
    app["command"] = f"{sys.executable} -u {script}"

    pm.start(app)
    assert wait_until(lambda: len(pm.logs("logger")) >= 6), pm.logs("logger")

    lines = pm.logs("logger")
    assert lines[0].startswith("[manager]") and "started pid=" in lines[0]
    app_lines = [l for l in lines if not l.startswith("[manager]")]
    assert app_lines[:5] == [f"line {i}" for i in range(5)]
    assert "to stderr" in app_lines  # stdout and stderr are merged

    assert pm.logs("logger", tail=2) == lines[-2:]
    assert pm.logs("logger", tail=0) == []
    assert len(pm.logs("logger", tail=1)) == 1


def test_ring_buffer_is_bounded(tmp_path):
    manager = ProcessManager(log_lines=3, log_dir=str(tmp_path / "logs"))
    script = tmp_path / "many.py"
    script.write_text(
        "for i in range(10):\n    print(i, flush=True)\nimport time; time.sleep(30)\n",
        encoding="utf-8",
    )
    try:
        manager.start(cfg("bounded", tmp_path, f"{sys.executable} -u {script}"))
        assert wait_until(lambda: len(manager.logs("bounded")) >= 3)
        time.sleep(0.3)
        lines = manager.logs("bounded", tail=100)
        assert len(lines) <= 3
        assert lines[-1] == "9"
    finally:
        manager.shutdown()


def test_env_is_passed_to_child(pm, tmp_path):
    script = tmp_path / "env.py"
    script.write_text(
        "import os, time\nprint('VALUE=' + os.environ['CUSTOM_VAR'], flush=True)\ntime.sleep(30)\n",
        encoding="utf-8",
    )
    pm.start(cfg("env-app", tmp_path, f"{sys.executable} -u {script}", {"CUSTOM_VAR": "hello-42"}))
    assert wait_until(lambda: any("VALUE=hello-42" in line for line in pm.logs("env-app")))


def test_venv_environment_isolation(pm, tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/some/manager/path")
    monkeypatch.setenv("VIRTUAL_ENV", "/some/manager/venv")
    monkeypatch.setenv("__PYVENV_LAUNCHER__", "/some/manager/bin/python")

    script = tmp_path / "check_env.py"
    script.write_text(
        "import os, time\n"
        "has_pp = 'PYTHONPATH' in os.environ\n"
        "has_ve = 'VIRTUAL_ENV' in os.environ\n"
        "has_pl = '__PYVENV_LAUNCHER__' in os.environ\n"
        "print(f'CLEAN={not has_pp and not has_ve and not has_pl}', flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    pm.start(cfg("clean-env-app", tmp_path, f"{sys.executable} -u {script}"))
    assert wait_until(lambda: any("CLEAN=True" in line for line in pm.logs("clean-env-app")))


def test_exit_code_is_recorded_for_crash(pm, tmp_path):
    script = tmp_path / "exit7.py"
    script.write_text("import sys; sys.exit(7)\n", encoding="utf-8")
    pm.start(cfg("crasher", tmp_path, f"{sys.executable} {script}"))

    assert wait_until(lambda: pm.info("crasher")["exit_code"] == 7)
    info = pm.info("crasher")
    assert info["running"] is False
    assert info["user_stopped"] is False
    assert pm.pid("crasher") is None


def test_restart_returns_a_new_pid(pm, tmp_path):
    app = cfg("restarter", tmp_path, sleep_cmd(30))
    first = pm.start(app)
    second = pm.restart(app)

    assert second != first
    assert pm.is_running("restarter")
    assert pm.pid("restarter") == second
    assert pm.info("restarter")["user_stopped"] is False


def test_restart_when_stopped_starts_fresh(pm, tmp_path):
    app = cfg("restart-stopped", tmp_path, sleep_cmd(30))
    pid = pm.restart(app)  # never started: restart must just start it
    assert pm.is_running("restart-stopped")
    assert pm.pid("restart-stopped") == pid


def test_stop_kills_the_whole_process_group(pm, tmp_path):
    script = tmp_path / "tree.py"
    script.write_text(
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print(child.pid, flush=True)\n"
        "child.wait()\n",
        encoding="utf-8",
    )
    pm.start(cfg("tree", tmp_path, f"{sys.executable} -u {script}"))
    assert wait_until(lambda: any(line.isdigit() for line in pm.logs("tree")))

    child_pid = next(int(line) for line in pm.logs("tree") if line.isdigit())
    assert psutil.pid_exists(child_pid)

    assert pm.stop("tree") is True
    assert wait_until(lambda: not _alive(child_pid), timeout=8), "grandchild survived stop"


def _alive(pid: int) -> bool:
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def test_queries_for_unknown_app(pm):
    assert pm.is_running("ghost") is False
    assert pm.pid("ghost") is None
    assert pm.logs("ghost") == []
    assert pm.info("ghost") == {
        "pid": None,
        "started_at": None,
        "exit_code": None,
        "user_stopped": False,
        "running": False,
    }
    assert pm.stop("ghost") is False


def test_shutdown_stops_everything_and_closes_manager(tmp_path):
    manager = ProcessManager()
    manager.start(cfg("one", tmp_path, sleep_cmd(60)))
    manager.start(cfg("two", tmp_path, sleep_cmd(60)))

    manager.shutdown()

    assert manager.is_running("one") is False
    assert manager.is_running("two") is False
    assert manager.info("one")["user_stopped"] is True
    with pytest.raises(ValueError, match="shut down"):
        manager.start(cfg("three", tmp_path, sleep_cmd(1)))


def test_subprocess_output_does_not_block_a_chatty_child(pm, tmp_path):
    """A child that writes far more than a pipe buffer must not deadlock."""
    script = tmp_path / "chatty.py"
    script.write_text(
        "import time\n"
        "for i in range(20000):\n    print('x' * 100)\n"
        "print('done', flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    pm.start(cfg("chatty", tmp_path, f"{sys.executable} -u {script}"))
    # The reader thread drains the pipe while the child writes.
    assert wait_until(lambda: "done" in pm.logs("chatty", tail=5), timeout=15)
    assert pm.is_running("chatty")


def test_procman_v2_persistent_logs_and_markers(tmp_path):
    log_dir = tmp_path / "logs"
    pm1 = ProcessManager(log_dir=str(log_dir))
    # a Python one-liner so the same command works in sh and cmd.exe
    app = cfg("v2app", tmp_path, f'"{sys.executable}" -c "print(\'hello v2\'); raise SystemExit(3)"')

    pm1.start(app)
    assert wait_until(lambda: pm1.info("v2app")["exit_code"] == 3)

    log_file = pm1.log_path("v2app")
    assert os.path.isfile(log_file)

    logs = pm1.logs("v2app", tail=100)
    assert any("[manager]" in line and "started" in line for line in logs)
    assert "hello v2" in logs
    assert any("[manager]" in line and "exited code=3" in line and "crashed" in line for line in logs)

    # Survives restart in a new ProcessManager instance while stopped
    pm2 = ProcessManager(log_dir=str(log_dir))
    logs_after = pm2.logs("v2app", tail=100)
    assert logs_after == logs

    # Test clear_logs
    pm2.clear_logs("v2app")
    assert not os.path.exists(log_file)
    assert pm2.logs("v2app") == []

