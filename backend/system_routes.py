"""backend/system_routes.py — folder browsing, native folder picking and desktop opening.

Implements the SPEC v2 system routes:
    GET  /api/browse?path=
    POST /api/pick-folder
    POST /api/pick-file
    POST /api/apps/{id}/open
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from . import detect as _detect
from . import monitor, osutil

router = APIRouter()

# Can be assigned by main.py or registry lookup callable
get_app_config: Callable[[str], dict | None] | None = None
get_app_port: Callable[[str], int | None] | None = None


@router.get("/api/browse")
async def browse(path: str | None = Query(default=None), files: bool = Query(default=False)) -> dict:
    """List subdirectories of `path` (default: home dir), ignoring hidden dirs.

    Reports whether each directory looks like a runnable app (looks_like_app).
    """
    if path is None or not str(path).strip():
        target = os.path.expanduser("~")
    else:
        target = os.path.abspath(os.path.expanduser(str(path).strip()))

    if not os.path.isdir(target):
        raise HTTPException(status_code=400, detail=f"path is not a directory: {target}")

    parent = os.path.dirname(target)
    if not parent or os.path.normcase(parent) == os.path.normcase(target):
        parent = None  # filesystem root ("/" or "C:\\")

    entries: list[dict[str, Any]] = []
    try:
        with os.scandir(target) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                        app_res = monitor.detect_command(entry.path)
                        looks_like_app = bool(app_res.get("command"))
                        entries.append(
                            {
                                "name": entry.name,
                                "path": entry.path,
                                "looks_like_app": looks_like_app,
                            }
                        )
                    elif (files and entry.is_file() and not entry.name.startswith(".")
                          and entry.name.lower().endswith(_detect.FILE_TYPES)):
                        entries.append({"name": entry.name, "path": entry.path, "is_file": True,
                                        "looks_like_app": True})
                except OSError:
                    continue
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"failed to read directory: {exc}") from exc

    entries.sort(key=lambda e: (bool(e.get("is_file")), e["name"].casefold()))
    return {
        "path": target,
        "parent": parent,
        "entries": entries,
    }


@router.post("/api/pick-folder")
async def pick_folder() -> dict:
    """Show the native folder chooser (macOS, Windows, Linux with zenity/kdialog).

    Returns {"path": str | None} (None when cancelled); 501 when no native
    picker exists, so the UI falls back to its in-page browser.
    """
    try:
        return {"path": await asyncio.to_thread(osutil.pick_folder)}
    except osutil.PickerUnavailable as exc:
        raise HTTPException(status_code=501, detail=f"native folder picker unavailable: {exc}") from exc


@router.post("/api/pick-file")
async def pick_file() -> dict:
    """Native "choose file" dialog for single-file apps; same contract as pick-folder."""
    try:
        return {"path": await asyncio.to_thread(osutil.pick_file)}
    except osutil.PickerUnavailable as exc:
        raise HTTPException(status_code=501, detail=f"native file picker unavailable: {exc}") from exc


@router.post("/api/apps/{app_id}/open")
async def open_app_target(app_id: str, request: Request) -> dict:
    """Open app in browser, Finder, or Terminal using macOS `open`."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from None

    target = body.get("target")
    if target not in ("browser", "finder", "terminal", "app", "share"):
        raise HTTPException(
            status_code=400,
            detail="target must be one of 'browser', 'finder', 'terminal', 'app', 'share'",
        )

    if get_app_config is None:
        raise HTTPException(status_code=500, detail="registry handler not configured")

    cfg = get_app_config(app_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"unknown app id: {app_id}")

    if target == "share":
        # the app's public share link (the desktop app can't open it by itself)
        from . import share_routes
        info = share_routes.tunnels.share_info(app_id)
        url = (info or {}).get("url")
        if not url:
            raise HTTPException(status_code=409, detail="this app has no public link right now")
        await asyncio.to_thread(osutil.open_url, url)
        return {"ok": True, "target": "share", "url": url}

    path = cfg.get("path")
    if not path or not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="app path is not a valid directory")

    if target == "finder":
        try:
            await asyncio.to_thread(osutil.open_folder, path)
            return {"ok": True, "target": "finder", "path": path}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"failed to open the folder: {exc}") from exc

    elif target == "terminal":
        try:
            await asyncio.to_thread(osutil.open_terminal, path)
            return {"ok": True, "target": "terminal", "path": path}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"failed to open a terminal: {exc}") from exc

    elif target == "app":
        # The app's named URL (http://<id>.localhost:<homeport port>/) in a new
        # browser tab. Opened by Homeport itself, so popup blockers don't apply.
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", app_id):
            raise HTTPException(status_code=400, detail="app id can't be used in a URL")
        port = request.url.port or 80
        # optional page of the app, e.g. "/pricing" or the feedback review link
        page = body.get("path") or "/"
        if not isinstance(page, str) or not page.startswith("/") or page.startswith("//") \
                or "\\" in page or any(c in page for c in "\r\n\t ") or len(page) > 2000:
            raise HTTPException(status_code=400, detail="path must be a page of the app, like /about")
        url = f"http://{app_id}.localhost:{port}{page}"
        try:
            await asyncio.to_thread(osutil.open_url, url)
            return {"ok": True, "target": "app", "url": url}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"failed to open browser: {exc}") from exc

    elif target == "browser":
        port = None
        if get_app_port is not None:
            port = get_app_port(app_id)
        if port is None:
            port = cfg.get("port")
        if not port:
            raise HTTPException(status_code=400, detail="app has no port configured or detected")
        url = f"http://127.0.0.1:{port}/"
        if cfg.get("entry"):
            from urllib.parse import quote
            url += quote(str(cfg["entry"]))
        try:
            await asyncio.to_thread(osutil.open_url, url)
            return {"ok": True, "target": "browser", "url": url}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"failed to open browser: {exc}") from exc

    raise HTTPException(status_code=400, detail="invalid target")
