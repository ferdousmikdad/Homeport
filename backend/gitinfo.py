"""backend/gitinfo.py — git branch / changes for app cards, and "Pull & restart".

``cached(path)`` never blocks the 1-second dashboard tick: it returns the last
known value and refreshes in a background thread when it is older than TTL.
One ``git status --porcelain=v2 --branch`` call gives branch, ahead/behind and
the number of changed files.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Optional

from . import osutil, shellenv

__all__ = ["cached", "read", "pull"]

_TTL = 8.0
_cache: dict = {}  # path -> (time, info|None)
_busy: set = set()
_lock = threading.Lock()
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _git() -> Optional[str]:
    return shellenv.which("git")


def _run(args: list, cwd: str, timeout: float) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": shellenv.user_path(), "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                          env=env, encoding="utf-8", errors="replace",
                          creationflags=_NO_WINDOW if osutil.IS_WINDOWS else 0)


def read(path: str) -> Optional[dict]:
    """{branch, dirty, ahead, behind, upstream} or None (not a repo / no git)."""
    git = _git()
    if not git or not path or not os.path.isdir(path):
        return None
    try:
        res = _run([git, "status", "--porcelain=v2", "--branch"], path, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    info = {"branch": None, "dirty": 0, "ahead": 0, "behind": 0, "upstream": None}
    for line in res.stdout.splitlines():
        if line.startswith("# branch.head "):
            head = line[len("# branch.head "):].strip()
            info["branch"] = None if head == "(detached)" else head
        elif line.startswith("# branch.upstream "):
            info["upstream"] = line[len("# branch.upstream "):].strip()
        elif line.startswith("# branch.ab "):
            parts = line.split()
            try:
                info["ahead"] = abs(int(parts[2]))
                info["behind"] = abs(int(parts[3]))
            except (IndexError, ValueError):
                pass
        elif line and not line.startswith("#"):
            info["dirty"] += 1
    return info


def _refresh(path: str) -> None:
    try:
        info = read(path)
        with _lock:
            _cache[path] = (time.time(), info)
    finally:
        with _lock:
            _busy.discard(path)


def cached(path: str) -> Optional[dict]:
    with _lock:
        hit = _cache.get(path)
        stale = hit is None or time.time() - hit[0] > _TTL
        if stale and path not in _busy:
            _busy.add(path)
            threading.Thread(target=_refresh, args=(path,), daemon=True).start()
    return hit[1] if hit else None


def invalidate(path: str) -> None:
    with _lock:
        _cache.pop(path, None)


def pull(path: str) -> dict:
    """``git pull --ff-only``: never creates merge commits or overwrites work."""
    git = _git()
    if not git:
        raise RuntimeError("git is not installed")
    if read(path) is None:
        raise RuntimeError("this folder is not a git repository")
    try:
        res = _run([git, "pull", "--ff-only"], path, timeout=120)
    except subprocess.TimeoutExpired:
        raise RuntimeError("git pull timed out") from None
    invalidate(path)
    output = (res.stdout + res.stderr).strip()
    return {"ok": res.returncode == 0, "output": output[-4000:]}
