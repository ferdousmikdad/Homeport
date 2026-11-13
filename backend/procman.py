"""Process management for locally-run apps.

Each app is spawned with ``shell=True`` in its own working directory and its
own session/process group, so the whole tree can be signalled at once.  A
background thread per app drains merged stdout/stderr into both a bounded
in-memory buffer and a persistent rotated log file (``data/logs/<id>.log``).

Public surface (see SPEC.md and SPEC v2):

    ProcessManager(log_lines=1000, log_dir=None)
        .start(cfg) -> int
        .stop(app_id, timeout=8.0) -> bool
        .restart(cfg) -> int
        .is_running(app_id) -> bool
        .info(app_id) -> dict
        .logs(app_id, tail=200) -> list[str]
        .clear_logs(app_id) -> None
        .log_path(app_id) -> str
        .pid(app_id) -> int | None
        .shutdown() -> None

All methods are thread-safe.
"""

from __future__ import annotations

import datetime
import os
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from . import osutil, paths, shellenv

__all__ = ["ProcessManager"]

_DEFAULT_LOG_DIR = os.path.join(paths.DATA_DIR, "logs")
_MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB


@dataclass
class _App:
    """Runtime bookkeeping for one app (not persisted)."""

    app_id: str
    process: subprocess.Popen[str] | None = None
    started_at: float | None = None
    exit_code: int | None = None
    user_stopped: bool = False
    lines: deque[str] = field(default_factory=deque)
    reader: threading.Thread | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)
    exit_marker_written: bool = False

    # -- helpers (caller must hold self.lock) ------------------------------
    @property
    def running(self) -> bool:
        proc = self.process
        return proc is not None and proc.poll() is None

    def sync_exit_code(self) -> None:
        """Record the exit code once the process is gone."""
        proc = self.process
        if proc is None:
            return
        code = proc.poll()
        if code is not None and self.exit_code is None:
            self.exit_code = code


class ProcessManager:
    """Spawn, supervise, stop and collect logs for app processes."""

    def __init__(self, log_lines: int = 1000, log_dir: str | None = None):
        self.log_lines = max(1, int(log_lines))
        self.log_dir = os.path.abspath(log_dir) if log_dir else _DEFAULT_LOG_DIR
        os.makedirs(self.log_dir, exist_ok=True)
        self._apps: dict[str, _App] = {}
        self._lock = threading.RLock()
        self._closed = False

    # ------------------------------------------------------------------
    # log helpers
    # ------------------------------------------------------------------
    def log_path(self, app_id: str) -> str:
        """Return the absolute path to the app's log file."""
        return os.path.join(self.log_dir, f"{app_id}.log")

    def _append_to_file(self, app_id: str, line: str) -> None:
        """Append one line to data/logs/<id>.log, rotating at 5 MB."""
        path = self.log_path(app_id)
        try:
            if os.path.exists(path) and os.path.getsize(path) >= _MAX_LOG_SIZE:
                rot = path + ".1"
                if os.path.exists(rot):
                    os.remove(rot)
                os.rename(path, rot)
        except OSError:
            pass

        try:
            with open(path, "a", encoding="utf-8", errors="replace") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def clear_logs(self, app_id: str) -> None:
        """Clear both on-disk logs and in-memory log lines."""
        path = self.log_path(app_id)
        rot = path + ".1"
        try:
            if os.path.exists(path):
                os.remove(path)
            if os.path.exists(rot):
                os.remove(rot)
        except OSError:
            pass

        app = self._get(app_id)
        if app is not None:
            with app.lock:
                app.lines.clear()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self, cfg: dict) -> int:
        """Spawn ``cfg["command"]`` and return its pid.

        Raises ValueError if the app is already running, if ``cfg["path"]``
        is not an existing directory, or if no command was supplied.
        """
        app_id = str(cfg["id"])
        path = cfg.get("path")
        command = cfg.get("command")

        if not path or not os.path.isdir(str(path)):
            raise ValueError(f"path does not exist or is not a directory: {path!r}")
        if not command or not str(command).strip():
            raise ValueError("command is required")

        with self._lock:
            if self._closed:
                raise ValueError("process manager is shut down")
            app = self._apps.get(app_id)
            if app is None:
                app = _App(app_id=app_id, lines=deque(maxlen=self.log_lines))
                self._apps[app_id] = app

        with app.lock:
            app.sync_exit_code()
            if app.running:
                raise ValueError(f"app {app_id!r} is already running")

            env = os.environ.copy()
            # Sanitize manager-specific virtualenv variables so child apps run in their own clean Python environment
            env.pop("PYTHONPATH", None)
            env.pop("VIRTUAL_ENV", None)
            env.pop("__PYVENV_LAUNCHER__", None)

            # Strip the manager's own .venv/bin from PATH so child apps use their own or system python
            # Use the user's login-shell PATH (+ Herd, nvm, cargo, … dirs) so
            # php/composer/node/pnpm/uv etc. resolve even when the manager was
            # launched from Finder or launchd with macOS's minimal PATH.
            manager_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            manager_venv_bin = os.path.abspath(osutil.venv_bin_dir(os.path.join(manager_root, ".venv")))
            paths = shellenv.user_path().split(os.pathsep)
            norm = os.path.normcase
            cleaned = [p for p in paths if norm(os.path.abspath(p)) != norm(manager_venv_bin)]
            env["PATH"] = os.pathsep.join(cleaned)

            for key, value in (cfg.get("env") or {}).items():
                env[str(key)] = str(value)

            proc = subprocess.Popen(
                str(command),
                shell=True,
                cwd=str(path),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                **osutil.popen_group_kwargs(),
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            app.process = proc
            app.started_at = time.time()
            app.exit_code = None
            app.user_stopped = False
            app.exit_marker_written = False

            # Persistent start marker
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            start_marker = f"[manager] {now_iso} started pid={proc.pid} cmd={command}"
            self._append_to_file(app_id, start_marker)
            app.lines.append(start_marker)

            reader = threading.Thread(
                target=self._read_output,
                args=(app, proc),
                name=f"procman-log-{app_id}",
                daemon=True,
            )
            app.reader = reader
            reader.start()

            return proc.pid

    def stop(self, app_id: str, timeout: float = 8.0) -> bool:
        """Stop the app's whole process group.  False if it was not running."""
        app = self._get(app_id)
        if app is None:
            return False

        with app.lock:
            proc = app.process
            app.sync_exit_code()
            if proc is None or proc.poll() is not None:
                return False
            app.user_stopped = True
            pid = proc.pid
            reader = app.reader

        # Wait outside the lock so the reader thread can keep draining the
        # pipe while the child is being signalled (avoids a full-pipe stall).
        self._terminate(proc, pid, timeout)

        with app.lock:
            app.sync_exit_code()
            self._write_exit_marker(app)

        if reader is not None:
            reader.join(timeout=2.0)
        return True

    def restart(self, cfg: dict) -> int:
        """Stop the app if needed, then start it again and return the new pid."""
        app_id = str(cfg["id"])
        self.stop(app_id)
        return self.start(cfg)

    def shutdown(self) -> None:
        """Stop every managed process (called when the manager exits)."""
        with self._lock:
            self._closed = True
            app_ids = list(self._apps)

        for app_id in app_ids:
            try:
                self.stop(app_id, timeout=5.0)
            except Exception:  # pragma: no cover - never block shutdown
                pass

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def is_running(self, app_id: str) -> bool:
        app = self._get(app_id)
        if app is None:
            return False
        with app.lock:
            app.sync_exit_code()
            return app.running

    def info(self, app_id: str) -> dict:
        """Runtime info: {pid, started_at, exit_code, user_stopped, running}."""
        app = self._get(app_id)
        if app is None:
            return {
                "pid": None,
                "started_at": None,
                "exit_code": None,
                "user_stopped": False,
                "running": False,
            }
        with app.lock:
            app.sync_exit_code()
            proc = app.process
            return {
                "pid": proc.pid if proc is not None and proc.poll() is None else None,
                "started_at": app.started_at,
                "exit_code": app.exit_code,
                "user_stopped": app.user_stopped,
                "running": proc is not None and proc.poll() is None,
            }

    def logs(self, app_id: str, tail: int = 200) -> list[str]:
        """Return up to ``tail`` most recent output lines (oldest first).

        Reads from persistent file tail so history survives manager restarts
        and works while stopped. Falls back to in-memory buffer.
        """
        try:
            tail_n = int(tail)
        except (TypeError, ValueError):
            tail_n = 200

        if tail_n <= 0:
            return []

        if tail_n > self.log_lines:
            tail_n = self.log_lines

        path = self.log_path(app_id)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines = deque(f, maxlen=tail_n)
                return [l.rstrip("\r\n") for l in lines]
            except OSError:
                pass

        app = self._get(app_id)
        if app is None:
            return []
        with app.lock:
            if tail_n >= len(app.lines):
                return list(app.lines)
            return list(app.lines)[-tail_n:]

    def pid(self, app_id: str) -> int | None:
        """Pid of the live process, or None."""
        app = self._get(app_id)
        if app is None:
            return None
        with app.lock:
            app.sync_exit_code()
            proc = app.process
            if proc is None or proc.poll() is not None:
                return None
            return proc.pid

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _get(self, app_id: str) -> _App | None:
        with self._lock:
            return self._apps.get(str(app_id))

    def _write_exit_marker(self, app: _App) -> None:
        """Write exit marker line if not already written."""
        if app.exit_marker_written:
            return
        if app.exit_code is None and app.process is not None:
            app.sync_exit_code()
        if app.exit_code is not None:
            app.exit_marker_written = True
            reason = "stopped by user" if app.user_stopped else "crashed"
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            marker = f"[manager] {now_iso} exited code={app.exit_code} ({reason})"
            self._append_to_file(app.app_id, marker)
            app.lines.append(marker)

    def _read_output(self, app: _App, proc: subprocess.Popen[str]) -> None:
        """Reader thread: copy merged output into file and ring buffer."""
        stream = proc.stdout
        try:
            if stream is not None:
                for line in stream:
                    line_clean = line.rstrip("\r\n")
                    with app.lock:
                        app.lines.append(line_clean)
                    self._append_to_file(app.app_id, line_clean)
        except (OSError, ValueError):
            pass
        finally:
            try:
                code = proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                code = proc.poll()
            with app.lock:
                if app.exit_code is None and code is not None:
                    app.exit_code = code
                self._write_exit_marker(app)
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass

    def _terminate(
        self, proc: subprocess.Popen[str], pid: int, timeout: float
    ) -> None:
        """Stop the whole process tree: politely, then forcibly after ``timeout``."""
        osutil.terminate_tree(proc, timeout)
