"""backend/monitor.py — process metrics, port probing and helpers.

Contract (from SPEC.md and SPEC v2):

    process_tree_stats(pid) -> {cpu_percent, mem_mb} summed over pid + children; {} if gone
    listening_ports(pid)    -> TCP LISTEN ports of pid + descendants
    port_open(port, host, timeout) -> bool
    await http_healthy(url, timeout) -> bool   # httpx GET, True if status < 500
    compute_status(cfg, info, port_ok, now, grace=30.0) -> str
    should_auto_restart(cfg, info, restarts_in_window) -> bool
    detect_command(path) -> {"command": str|None, "port": int|None}
    find_port_owner(port) -> {"pid": int, "command": str, "cwd": str|None} | None
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time

import psutil

from . import detect as _detect, osutil

# ---------------------------------------------------------------------------
# process tree metrics
# ---------------------------------------------------------------------------


def _tree_pids(pid: int) -> list[int]:
    """pid + all descendants, breadth-first. Survives processes disappearing mid-walk."""
    try:
        if pid is None or int(pid) <= 0:
            return []
        root = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError):
        return []
    out = [pid]
    frontier = [root]
    while frontier:
        nxt: list[psutil.Process] = []
        for proc in frontier:
            try:
                nxt.extend(proc.children())
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, psutil.Error):
                pass
        out.extend(p.pid for p in nxt)
        frontier = nxt
    return out


def process_tree_stats(pid: int) -> dict:
    """{cpu_percent, mem_mb} summed over pid + children; {} if the process is gone."""
    try:
        pids = _tree_pids(pid)
        if not pids:
            return {}
        procs: list[psutil.Process] = []
        for p in pids:
            try:
                proc = psutil.Process(p)
                if proc.is_running():
                    procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if not procs:
            return {}
        cpu = mem = 0.0
        for proc in procs:
            try:
                cpu += proc.cpu_percent(interval=None)
                mem += proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return {"cpu_percent": round(cpu, 2), "mem_mb": round(mem / (1024 * 1024), 1)}
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return {}
    except psutil.Error:
        return {}


def listening_ports(pid: int) -> list[int]:
    """TCP LISTEN port numbers of pid + descendants, sorted, de-duplicated."""
    ports: set[int] = set()
    for p in _tree_pids(pid):
        try:
            for conn in psutil.Process(p).net_connections(kind="inet"):
                laddr = getattr(conn, "laddr", None)
                if conn.status == psutil.CONN_LISTEN and laddr is not None:
                    ports.add(int(laddr.port))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, psutil.Error):
            pass
    return sorted(ports)


# ---------------------------------------------------------------------------
# port / health probing
# ---------------------------------------------------------------------------


def port_open(port: int, host: str = "localhost", timeout: float = 0.5) -> bool:
    """True if a TCP connection to (host, port) succeeds, trying localhost, 127.0.0.1 and ::1."""
    for h in (host, "127.0.0.1", "::1"):
        try:
            with socket.create_connection((h, int(port)), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def find_all_port_pids(port: int | None) -> list[int]:
    """Return all PIDs listening on the given TCP port (any OS)."""
    if not port or not (1 <= int(port) <= 65535):
        return []
    return osutil.listening_pids(int(port))


def find_port_owner(port: int) -> dict | None:
    """Return {pid, command, cwd} of the process listening on TCP `port`, or None."""
    if not port or not (1 <= int(port) <= 65535):
        return None
    for pid in osutil.listening_pids(int(port)):
        try:
            p = psutil.Process(pid)
            cmd = " ".join(p.cmdline()) or p.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"pid": pid, "command": "unknown", "cwd": None}
        cwd = None
        try:
            cwd = p.cwd()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return {"pid": pid, "command": cmd, "cwd": cwd}
    return None


async def http_healthy(url: str, timeout: float = 2.0) -> bool:
    """httpx GET; True if the request succeeds with status < 500. Any other
    outcome (connection error, timeout, 5xx) is False."""
    import httpx  # local import keeps module importable without httpx installed

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            return resp.status_code < 500
    except Exception:
        return False


# ---------------------------------------------------------------------------
# status rules
# ---------------------------------------------------------------------------
# status ∈ "stopped" | "starting" | "running" | "crashed"
# - stopped: user stopped it or never started (no pid for it)
# - crashed: process had been started but exited without a user stop
# - starting: process alive, port not yet open (max `grace` seconds, then
#   "running" anyway if alive)
# - running: alive and (no port configured/detected, or port open)

_STARTING = "starting"
_RUNNING = "running"
_STOPPED = "stopped"
_CRASHED = "crashed"


def compute_status(
    cfg: dict,
    info: dict,
    port_ok: bool | None,
    now: float,
    grace: float = 30.0,
) -> str:
    """Pure function implementing the status rules.

    cfg     : AppConfig          (uses cfg["port"])
    info    : procman.info() dict ({pid, started_at, exit_code, user_stopped, running})
    port_ok : True/False = port probe result; None = nothing to check
              (no configured port and none detected)
    now     : current epoch time
    grace   : seconds a live-but-port-closed process stays "starting"
    """
    if not info.get("running"):
        if info.get("pid") and info.get("exit_code") is not None and not info.get("user_stopped"):
            return _CRASHED
        return _STOPPED

    started_at = info.get("started_at")
    alive_elapsed = (now - started_at) if started_at is not None else 0.0

    if port_ok is False:
        if alive_elapsed < grace:
            return _STARTING
        return _RUNNING
    return _RUNNING


def should_auto_restart(
    cfg: dict,
    info: dict,
    restarts_in_window: int,
) -> bool:
    """Restart only if: auto_restart enabled, crashed (not user-stopped), and
    fewer than 5 restarts in the current 5-minute window."""
    if not cfg.get("auto_restart"):
        return False
    if info.get("running"):
        return False
    if info.get("user_stopped"):
        return False
    if info.get("exit_code") is None and info.get("pid") is None:
        # never started — nothing to restart
        return False
    return restarts_in_window < 5


# ---------------------------------------------------------------------------
# command / port detection
# ---------------------------------------------------------------------------

_PORT_PATTERNS = [
    # 127.0.0.1:8787 | localhost:8787
    re.compile(r"localhost:\s{0,2}(\d{2,5})", re.IGNORECASE),
    # "port 8787" | "Port: 8787" | "port = 8787" | "port is **8787**" |
    # "run.py --port 8787"  (\b before keeps "HPS_PORT"/"TEST_PORT" from matching)
    re.compile(r"\bport\b(?:\s+(?:is|on|at)\b\W{0,4}|[\s:=>,'\"#*]{1,6})(\d{2,5})\b", re.IGNORECASE),
    # PORT = 8787 | PORT="8787" (explicit uppercase assignment)
    re.compile(r"\bPORT\s*=\s*(\d{2,5})\b"),
]

# ports that obviously are not "the port of this web app"
# (DB servers, mail relays, ssh, etc.)
_RESERVED_PORTS = {0, 1, 21, 22, 23, 25, 53, 110, 143, 465, 587, 993, 995,
                   3306, 3389, 5432, 6379, 27017, 11211}


def _scan_text_for_port(text: str) -> int | None:
    """First plausible port number in `text` from the SPEC patterns."""
    for pattern in _PORT_PATTERNS:
        for match in pattern.finditer(text):
            value = int(match.group(1))
            # <1024 are system ports (and "127.0.0.1" would read as 127)
            if value in _RESERVED_PORTS or not (1024 <= value <= 65535):
                continue
            return value
    return None


def _detect_port(path: str) -> int | None:
    """Regex-scan README and small source files for port hints."""
    candidates: list[str] = []
    for name in ("README", "README.md", "README.txt", "readme.md", "Readme.md",
                 "HOW-TO-USE.md", "USAGE.md"):
        p = os.path.join(path, name)
        if os.path.isfile(p):
            candidates.append(p)
    # cheap source scan: top-level .py/.sh/.js/.json and package.json scripts
    try:
        for entry in sorted(os.listdir(path)):
            p = os.path.join(path, entry)
            if os.path.isfile(p) and (
                entry.endswith((".py", ".sh", ".js", ".json", ".toml"))
                or entry.endswith(".command")
            ) and os.path.getsize(p) < 512 * 1024:
                candidates.append(p)
    except OSError:
        pass

    seen: set[str] = set()
    for file_path in candidates:
        if file_path in seen:
            continue
        seen.add(file_path)
        try:
            if os.path.getsize(file_path) > 1024 * 1024:
                continue
            with open(file_path, encoding="utf-8", errors="replace") as fh:
                text = fh.read(1024 * 1024)
        except OSError:
            continue
        port = _scan_text_for_port(text)
        if port is not None:
            return port
    return None


def detect_command(path: str, *, pick_free_port: bool = False, avoid_ports=(), subfolders: bool = True) -> dict:
    """{"command": str|None, "port": int|None, "type": str|None} for an app directory.

    Recognises Laravel, Symfony, PHP, Django, FastAPI, Flask, Streamlit,
    Python scripts, Node (Vite/Next/Nuxt/… via npm/pnpm/yarn/bun), Deno,
    Rails, Go, Rust, Java, .NET, Docker Compose, Makefiles, shell launchers,
    Procfiles and static sites — see backend/detect.py.  The port comes from
    the README/source when documented, else the framework default.
    ``pick_free_port`` skips ports that are busy or listed in ``avoid_ports``.
    """
    if not os.path.isdir(path):
        return {"command": None, "port": None, "type": None}
    return _detect.detect(
        path,
        _detect_port(path),
        pick_free_port=pick_free_port,
        avoid_ports=avoid_ports,
        subfolders=subfolders,
    )
