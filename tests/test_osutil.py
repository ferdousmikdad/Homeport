"""backend/osutil.py — cross-platform helpers (real checks on this OS,
simulated branches for the others)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

import psutil
import pytest

from backend import monitor, osutil, shellenv, tunnels


def test_venv_paths_per_os():
    assert osutil.venv_python(".venv", windows=True) == os.path.join(".venv", "Scripts", "python.exe")
    assert osutil.venv_python(".venv", windows=False) == os.path.join(".venv", "bin", "python")
    assert osutil.venv_bin_dir("v", windows=True).endswith("Scripts")


def test_platform_name_matches_flags():
    name = osutil.platform_name()
    assert name in ("mac", "windows", "linux") or name == sys.platform
    assert sum([osutil.IS_MAC, osutil.IS_WINDOWS, osutil.IS_LINUX]) <= 1


def test_listening_pids_and_port_owner_find_this_process():
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen()
        port = srv.getsockname()[1]
        assert os.getpid() in osutil.listening_pids(port)
        owner = monitor.find_port_owner(port)
        assert owner and owner["pid"] == os.getpid()
    assert monitor.find_port_owner(1) is None or isinstance(monitor.find_port_owner(1), dict)


def test_terminate_tree_stops_shell_and_grandchildren():
    # a shell that starts a long-running grandchild, like `npm run dev` does
    cmd = f'"{sys.executable}" -c "import time; time.sleep(60)"'
    proc = subprocess.Popen(cmd, shell=True, **osutil.popen_group_kwargs())
    deadline = time.time() + 5
    kids = []
    while time.time() < deadline and not kids:
        kids = psutil.Process(proc.pid).children(recursive=True) or (
            [psutil.Process(proc.pid)] if "python" in psutil.Process(proc.pid).name().lower() else [])
        time.sleep(0.1)
    osutil.terminate_tree(proc, timeout=3)
    assert proc.poll() is not None

    def survivors():
        alive = []
        for k in kids:
            try:
                if k.is_running() and k.status() != psutil.STATUS_ZOMBIE:
                    alive.append(k)
            except psutil.NoSuchProcess:
                pass
        return alive
    # the OS may need a moment to reap them on a slow machine
    deadline = time.time() + 5
    while survivors() and time.time() < deadline:
        time.sleep(0.05)
    assert not survivors()


def test_kill_pid_ignores_missing_process():
    osutil.kill_pid(99999999)  # must not raise
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    osutil.kill_pid(p.pid, force=True)
    assert p.wait(timeout=5) is not None


def test_linux_picker_without_zenity_is_unavailable(monkeypatch):
    monkeypatch.setattr(osutil, "IS_MAC", False)
    monkeypatch.setattr(osutil, "IS_WINDOWS", False)
    monkeypatch.setattr(osutil.shutil, "which", lambda name: None)
    with pytest.raises(osutil.PickerUnavailable):
        osutil.pick_folder()


def test_notify_never_raises(monkeypatch):
    monkeypatch.setattr(osutil.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    osutil.notify("t", "m")


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell PATH lookup")
def test_user_path_keeps_existing_path_dirs():
    parts = shellenv.user_path().split(os.pathsep)
    assert "/usr/bin" in parts


def test_cloudflared_asset_names():
    r = tunnels._release_asset
    assert r("mac", "arm64") == "cloudflared-darwin-arm64.tgz"
    assert r("mac", "x86_64") == "cloudflared-darwin-amd64.tgz"
    assert r("windows", "AMD64") == "cloudflared-windows-amd64.exe"
    assert r("linux", "x86_64") == "cloudflared-linux-amd64"
    assert r("linux", "aarch64") == "cloudflared-linux-arm64"
