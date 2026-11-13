"""backend/updates.py — tell the user when a newer Homeport is out.

Asks GitHub for the latest release at most once a day (and shortly after
start), never sends anything about the user, and can be turned off in
Settings. It only notifies: updating is one click to the right download (the
desktop app), the install command again, or `git pull` (from source).

    GET  /api/update        -> {current, latest, available, url, notes, ...}
    POST /api/update/check  check now
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import sys
import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter

from . import app_settings, osutil, paths
from .version import __version__

router = APIRouter()

REPO = "ferdousmikdad/Homeport"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
DOWNLOAD = f"https://github.com/{REPO}/releases/latest/download/"
CHANGELOG = "https://homeport.ferdousmikdad.com/changelog"
EVERY = 24 * 3600.0
transport: Any = None  # tests use an httpx.MockTransport

_state: dict = {}
_lock = asyncio.Lock()


def _file() -> str:
    return os.path.join(paths.DATA_DIR, "update.json")


def parse(version: str) -> tuple:
    """'v1.2.10' -> (1, 2, 10); anything odd -> (0,)."""
    nums = re.findall(r"\d+", (version or "").split("-")[0].split("+")[0])
    return tuple(int(n) for n in nums[:3]) if nums else (0,)


def newer(latest: str, current: str = __version__) -> bool:
    return parse(latest) > parse(current)


def enabled() -> bool:
    return app_settings.load().get("check_updates") is not False


def install_kind() -> str:
    """'desktop' (installed app), 'script' (install.sh / install.ps1 source copy) or 'source' (a clone)."""
    if paths.FROZEN:
        return "desktop"
    root = os.path.realpath(paths.SOURCE_ROOT)
    for d in (os.environ.get("HOMEPORT_HOME"), os.path.expanduser("~/.homeport/app"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Homeport", "app") if osutil.IS_WINDOWS else None):
        if d and os.path.realpath(d) == root:
            return "script"
    return "source"


def how_to_update(kind: str) -> dict:
    if kind == "desktop":
        if sys.platform == "darwin":
            asset = "Homeport-mac-arm64.dmg"
        elif osutil.IS_WINDOWS:
            asset = "Homeport-Setup-x64.exe"
        else:
            asset = "Homeport-x86_64.AppImage"
        return {"kind": kind, "download": DOWNLOAD + asset}
    if kind == "script":
        cmd = (f"irm https://raw.githubusercontent.com/{REPO}/main/install.ps1 | iex" if osutil.IS_WINDOWS
               else f"curl -fsSL https://raw.githubusercontent.com/{REPO}/main/install.sh | sh")
        return {"kind": kind, "command": cmd}
    return {"kind": kind, "command": "git pull", "folder": paths.SOURCE_ROOT}


def _load_cache() -> dict:
    with contextlib.suppress(OSError, ValueError):
        with open(_file(), encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    return {}


def _save_cache(data: dict) -> None:
    with contextlib.suppress(OSError):
        os.makedirs(paths.DATA_DIR, exist_ok=True)
        with open(_file(), "w", encoding="utf-8") as fh:
            json.dump(data, fh)


def _notes(body: str) -> str:
    """A short, plain excerpt of the release notes (GitHub's auto notes are mostly links)."""
    lines = []
    for line in (body or "").splitlines():
        line = line.strip()
        if not line or line.lower().startswith(("**full changelog", "## new contributors")):
            continue
        line = re.sub(r"\s+by @[\w-]+ in https?://\S+", "", line)
        line = re.sub(r"[*_`#>]+", "", line).strip()
        if line:
            lines.append(line)
    text = "\n".join(lines)
    return text[:800] + ("…" if len(text) > 800 else "")


def public_state() -> dict:
    data = dict(_state or _load_cache())
    latest = data.get("latest")
    return {
        "current": __version__,
        "latest": latest,
        "available": bool(latest and newer(latest)),
        "url": data.get("url"),
        "notes": data.get("notes") or "",
        "published_at": data.get("published_at"),
        "checked_at": data.get("checked_at"),
        "error": data.get("error"),
        "enabled": enabled(),
        "changelog": CHANGELOG + ("#v" + latest.lstrip("v").replace(".", "-") if latest else ""),
        "how": how_to_update(install_kind()),
    }


async def check(force: bool = False) -> dict:
    """Ask GitHub for the latest release (at most once a day unless forced)."""
    global _state
    async with _lock:
        cached = _state or _load_cache()
        if not force and cached.get("checked_at") and time.time() - cached["checked_at"] < EVERY:
            _state = cached
            return public_state()
        data = dict(cached)
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=transport, follow_redirects=True) as c:
                r = await c.get(LATEST_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "Homeport"})
            if r.status_code == 200:
                rel = r.json()
                data.update(latest=str(rel.get("tag_name") or "").lstrip("v") or None, url=rel.get("html_url"),
                            notes=_notes(rel.get("body") or ""), published_at=rel.get("published_at"), error=None)
            elif r.status_code == 404:
                data.update(latest=None, error=None)  # no release yet
            else:
                data["error"] = f"GitHub answered {r.status_code}"
        except httpx.HTTPError as exc:
            data["error"] = f"couldn't reach GitHub ({type(exc).__name__})"
        data["checked_at"] = time.time()
        _state = data
        _save_cache(data)
        return public_state()


async def background_loop() -> None:
    """Started by main.py: first check a minute after start, then daily (if enabled)."""
    await asyncio.sleep(60)
    while True:
        if enabled():
            with contextlib.suppress(Exception):
                await check()
        await asyncio.sleep(6 * 3600)


@router.get("/api/update")
async def get_update() -> dict:
    return public_state()


@router.post("/api/update/check")
async def check_now() -> dict:
    return await check(force=True)
