"""backend/main.py — FastAPI app for the Homeport.

Wires the persisted registry (:mod:`backend.registry`), the process manager
(:mod:`backend.procman`), metric helpers (:mod:`backend.monitor`) and system
routes (:mod:`backend.system_routes`) into the HTTP/SSE API described in
SPEC.md and SPEC v2.

Run with::

    python launch.py        (or run.command / run.sh / run.bat)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import subprocess
import tempfile
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .detect import _free_port as free_port
from . import ai_routes, diagnose, gitinfo, icons, monitor, osutil, paths, proxy, services, wordpress, procman, registry as registry_module, share_routes, system_routes

__all__ = ["app"]

PROJECT_ROOT = paths.SOURCE_ROOT
UI_DIR = paths.UI_DIR
TICK_SECONDS = 1.0
RESTART_WINDOW_SECONDS = 300.0
TAIL_DEFAULT = 500

# ---------------------------------------------------------------------------
# module state
# ---------------------------------------------------------------------------
registry = registry_module.Registry()
pm = procman.ProcessManager()

_states: dict[str, dict] = {}
_restart_times: dict[str, deque[float]] = {}
_restart_counts: dict[str, int] = {}
_errors: dict[str, str | None] = {}
_last_pids: dict[str, int] = {}
_restart_suppressed: set[str] = set()
_subscribers: set[asyncio.Queue[str]] = set()
_notified_crashes: set[str] = set()
_ticker: asyncio.Task | None = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _coerce_optional_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise HTTPException(status_code=400, detail=f"{field} must be an integer")
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field} must be an integer") from None


def _clean_path(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="path is required")
    return os.path.abspath(os.path.expanduser(raw))


def _registered_ports(exclude_id: str | None = None) -> set:
    """Ports already claimed by registered apps, so detection of a new app
    doesn't hand out the same default port (e.g. two Laravel apps on 8000)."""
    return {
        int(app["port"])
        for app in registry.list()
        if app.get("port") and app.get("id") != exclude_id
    }


def _require_dir(path: str) -> str:
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"path is not a directory: {path}")
    return path


def _clean_health_url(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_env(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="env must be an object")
    return {str(k): str(v) for k, v in value.items()}


def _clean_color(value: Any) -> str:
    text = value.strip().lower() if isinstance(value, str) else value
    if text in (None, ""):
        return ""
    if text not in registry_module.COLORS:
        raise HTTPException(status_code=400, detail="color must be one of: red, green, blue")
    return text


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    return body


_DETECT_TTL = 30.0
_detect_cache: dict[str, tuple[float, int | None]] = {}


def _detected_port(path: str, now: float) -> int | None:
    """detect_command's port for ``path``, cached so the 1s tick doesn't rescan
    the folder every time."""
    hit = _detect_cache.get(path)
    if hit and now - hit[0] < _DETECT_TTL:
        return hit[1]
    port = monitor.detect_command(path).get("port") if os.path.isdir(path) else None
    _detect_cache[path] = (now, port)
    return port


def _cfg_or_404(app_id: str) -> dict:
    cfg = registry.get(app_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"unknown app id: {app_id}")
    return cfg


def _log_tail(app_id: str) -> list[str]:
    try:
        return pm.logs(app_id, tail=10)
    except Exception:
        return []


def _snapshot() -> list[dict]:
    return [dict(_states[cfg["id"]]) for cfg in registry.list() if cfg["id"] in _states]


def _snapshot_json() -> str:
    return json.dumps(_snapshot(), ensure_ascii=False, default=str)


def _broadcast() -> None:
    """Push the current snapshot to every SSE subscriber (never blocks)."""
    if not _subscribers:
        return
    payload = _snapshot_json()
    for queue in list(_subscribers):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass


def _prune_restarts(app_id: str, now: float) -> deque[float]:
    times = _restart_times.setdefault(app_id, deque())
    cutoff = now - RESTART_WINDOW_SECONDS
    while times and times[0] < cutoff:
        times.popleft()
    return times


def _maybe_auto_restart(cfg: dict, now: float) -> None:
    if not cfg.get("auto_restart"):
        return
    app_id = cfg["id"]
    if app_id in _restart_suppressed:
        return
    info = pm.info(app_id)
    times = _prune_restarts(app_id, now)
    if not monitor.should_auto_restart(cfg, info, len(times)):
        return

    times.append(now)
    _restart_counts[app_id] = _restart_counts.get(app_id, 0) + 1
    try:
        pm.start(cfg)
        _errors[app_id] = None
    except Exception as exc:
        _errors[app_id] = f"auto-restart failed: {exc}"
        _last_pids.pop(app_id, None)


async def _build_state(cfg: dict, now: float) -> dict:
    """Collect one AppState for ``cfg`` (metrics + status + health + conflict)."""
    app_id = cfg["id"]
    info = pm.info(app_id)
    pid = info.get("pid")
    if pid:
        _last_pids[app_id] = int(pid)

    stats: dict = {}
    ports: list[int] = []
    if pid:
        stats, ports = await asyncio.gather(
            asyncio.to_thread(monitor.process_tree_stats, int(pid)),
            asyncio.to_thread(monitor.listening_ports, int(pid)),
        )
        stats = stats or {}
        ports = ports or []

    configured_port = cfg.get("port")
    detected_port = None
    if configured_port and int(configured_port) in ports:
        detected_port = int(configured_port)
    elif ports:
        detected_port = int(ports[0])
    check_port = configured_port or detected_port
    port_ok: bool | None = None
    if pid and check_port:
        port_ok = await asyncio.to_thread(monitor.port_open, int(check_port))

    status_info = dict(info)
    if not status_info.get("pid"):
        status_info["pid"] = _last_pids.get(app_id)
    status = monitor.compute_status(cfg, status_info, port_ok, now)

    healthy: bool | None = None
    if cfg.get("health_url") and status == "running":
        healthy = await monitor.http_healthy(str(cfg["health_url"]))

    # Port conflict detection (for stopped/crashed apps with a port configured or detected)
    port_conflict = None
    if not info.get("running"):
        probe_port = configured_port
        if not probe_port and cfg.get("path"):
            probe_port = _detected_port(cfg["path"], now)
        if probe_port and int(probe_port) != 7777:
            # Fast check: only run find_port_owner if port is actually listening
            is_open = await asyncio.to_thread(monitor.port_open, int(probe_port))
            if is_open:
                owner = await asyncio.to_thread(monitor.find_port_owner, int(probe_port))
                if owner and owner.get("pid") != pid:
                    port_conflict = owner

    # last_error calculation on crash
    if status != "crashed":
        _errors[app_id] = None
        _notified_crashes.discard(app_id)
    else:
        if not _errors.get(app_id):
            log_lines = [
                line.strip()
                for line in _log_tail(app_id)
                if line.strip() and not (line.startswith("[manager]") and "exited code=" in line)
            ]
            exit_code = info.get("exit_code")
            exit_prefix = f"exited with code {exit_code}" if exit_code is not None else "crashed"
            last_3 = "\n".join(log_lines[-3:]) if log_lines else ""
            _errors[app_id] = f"{exit_prefix}\n{last_3}".strip() if last_3 else exit_prefix

        # Desktop notification once per crash if notify enabled
        if cfg.get("notify", True) and app_id not in _notified_crashes:
            _notified_crashes.add(app_id)
            osutil.notify("Homeport", f"{cfg['name']} crashed (exit {info.get('exit_code')})")

    started_at = info.get("started_at")
    uptime = None
    if info.get("running") and started_at is not None:
        uptime = round(max(0.0, now - float(started_at)), 1)

    return {
        "id": app_id,
        "name": cfg["name"],
        "path": cfg["path"],
        "command": cfg.get("command") or "",
        "port": configured_port,
        "health_url": cfg.get("health_url"),
        "description": cfg.get("description") or "",
        "category": cfg.get("category") or "",
        "color": cfg.get("color") or "",
        "created_at": cfg.get("created_at"),
        "updated_at": cfg.get("updated_at"),
        "auto_restart": bool(cfg.get("auto_restart")),
        "autostart": bool(cfg.get("autostart", False)),
        "notify": bool(cfg.get("notify", True)),
        "status": status,
        "pid": int(pid) if pid else None,
        "started_at": started_at,
        "uptime_s": uptime,
        "cpu_percent": stats.get("cpu_percent"),
        "mem_mb": stats.get("mem_mb"),
        "detected_port": detected_port,
        "healthy": healthy,
        "restarts": _restart_counts.get(app_id, 0),
        "last_exit_code": info.get("exit_code"),
        "last_error": _errors.get(app_id) if status == "crashed" else None,
        "port_conflict": port_conflict,
        "icon": _icon_url(app_id, cfg.get("path") or ""),
        "share": await _share_state(app_id, bool(info.get("running"))),
        "lan": await _lan_state(app_id, bool(info.get("running"))),
        "git": gitinfo.cached(cfg.get("path") or ""),
        "service": cfg.get("service"),
        "wordpress": _wp_state(cfg),
    }


async def _share_state(app_id: str, running: bool) -> dict | None:
    """The app's public link, if shared; a stopped app stops being shared."""
    tunnels = share_routes.tunnels
    if not tunnels.is_sharing(app_id):
        return None
    if not running:
        await asyncio.to_thread(tunnels.stop, app_id)
        return None
    return tunnels.get(app_id)


async def _lan_state(app_id: str, running: bool) -> dict | None:
    """The app's Wi-Fi preview link; it closes when the app stops."""
    lan = share_routes.lan
    if not lan.is_on(app_id):
        return None
    if not running:
        await lan.stop(app_id)
        return None
    return lan.info(app_id)


def _running_port(app_id: str) -> int | None:
    """Port of a running app (detected listener first), else None."""
    if not pm.is_running(app_id):
        return None
    state = _states.get(app_id) or {}
    port = state.get("detected_port") or state.get("port")
    if not port:
        cfg = registry.get(app_id) or {}
        port = cfg.get("port")
    return int(port) if port else None


def _icon_url(app_id: str, path: str) -> str | None:
    """URL of the project's own icon (favicon/logo), cache-busted by mtime;
    None means the UI draws a generated logo instead."""
    found = icons.find_icon(path)
    if not found:
        return None
    try:
        version = int(os.path.getmtime(found))
    except OSError:
        version = 0
    return f"/api/apps/{app_id}/icon?v={version}"


async def _refresh_all() -> list[dict]:
    """Rebuild the state cache for every registered app (concurrently)."""
    now = time.time()
    cfgs = registry.list()

    for cfg in cfgs:
        _maybe_auto_restart(cfg, now)
    now = time.time()

    states = await asyncio.gather(*(_build_state(cfg, now) for cfg in cfgs))

    known = {cfg["id"] for cfg in cfgs}
    for stale in [app_id for app_id in _states if app_id not in known]:
        _states.pop(stale, None)
    for state in states:
        _states[state["id"]] = state
    return list(states)


async def _tick_loop() -> None:
    while True:
        started = asyncio.get_running_loop().time()
        try:
            await asyncio.to_thread(share_routes.tunnels.stop_expired)
            await _refresh_all()
            _broadcast()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        elapsed = asyncio.get_running_loop().time() - started
        await asyncio.sleep(max(0.05, TICK_SECONDS - elapsed))


# ---------------------------------------------------------------------------
# lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def _lifespan(_app: FastAPI):
    global _ticker, pm
    pm = procman.ProcessManager()
    _states.clear()
    _restart_times.clear()
    _restart_counts.clear()
    _errors.clear()
    _last_pids.clear()
    _restart_suppressed.clear()
    _subscribers.clear()
    _notified_crashes.clear()

    # Wire system routes helpers
    system_routes.get_app_config = lambda aid: registry.get(aid)
    system_routes.get_app_port = lambda aid: _states.get(aid, {}).get("detected_port") or _states.get(aid, {}).get("port")
    ai_routes.get_states = _snapshot
    share_routes.get_app_config = lambda aid: registry.get(aid)
    share_routes.get_running_port = _running_port
    proxy.get_running_port = _running_port
    proxy.app_exists = lambda aid: registry.get(aid) is not None
    proxy.tunnels = share_routes.tunnels

    # Autostart apps on boot
    for cfg in registry.list():
        if cfg.get("autostart"):
            with contextlib.suppress(Exception):
                await asyncio.to_thread(pm.start, cfg)

    with contextlib.suppress(Exception):
        await _refresh_all()
    _ticker = asyncio.create_task(_tick_loop())
    try:
        yield
    finally:
        if _ticker is not None:
            _ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _ticker
            _ticker = None
        with contextlib.suppress(Exception):
            await asyncio.to_thread(share_routes.tunnels.shutdown)
        with contextlib.suppress(Exception):
            await share_routes.lan.stop_all()
        with contextlib.suppress(Exception):
            await asyncio.to_thread(pm.shutdown)
        _states.clear()
        _subscribers.clear()


app = FastAPI(title="Homeport", version="2.0.0", lifespan=_lifespan)


@app.middleware("http")
async def _no_stale_ui(request: Request, call_next):
    """Make browsers re-check the UI files (HTML/CSS/JS) on every load.

    Without this, Chrome heuristically caches style.css/app.js and pairs an
    old copy with a new index.html after an update, which breaks the layout.
    Revalidation is cheap: unchanged files answer 304 via their ETag.
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response
app.include_router(system_routes.router)
app.include_router(ai_routes.router)
app.include_router(share_routes.router)
# Named URLs (<id>.localhost) and password-protected shares, routed by Host.
app.add_middleware(proxy.HostProxyMiddleware)


# ---------------------------------------------------------------------------
# routes — apps
# ---------------------------------------------------------------------------
@app.get("/api/apps")
async def list_apps() -> list[dict]:
    return await _refresh_all()


@app.get("/api/apps/{app_id}")
async def get_app(app_id: str) -> dict:
    cfg = _cfg_or_404(app_id)
    state = await _build_state(cfg, time.time())
    _states[app_id] = state
    return state


@app.post("/api/apps")
async def create_app(request: Request) -> dict:
    body = await _json_body(request)

    name = body.get("name")
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    name = name.strip()

    path = _require_dir(_clean_path(body.get("path")))

    command = body.get("command")
    if command is not None and not isinstance(command, str):
        raise HTTPException(status_code=400, detail="command must be a string")
    command = (command or "").strip()
    # Only pick a fresh free port when we also generate the command (the port
    # is baked into generated commands); a user command keeps the plain guess.
    detected = await asyncio.to_thread(
        monitor.detect_command, path,
        pick_free_port=not command, avoid_ports=_registered_ports(),
    )
    if not command:
        command = (detected.get("command") or "").strip()

    raw_port = body.get("port")
    port = _coerce_optional_int(raw_port, "port") if raw_port not in (None, "") else None
    if port is None:
        port = detected.get("port")
    if port is not None and not (0 <= port <= 65535):
        raise HTTPException(status_code=400, detail="port out of range")

    health_url_value = body.get("health_url")
    if health_url_value is not None and not isinstance(health_url_value, str):
        raise HTTPException(status_code=400, detail="health_url must be a string")

    desc_value = body.get("description")
    if desc_value is not None and not isinstance(desc_value, str):
        raise HTTPException(status_code=400, detail="description must be a string")

    category_value = body.get("category")
    if category_value is not None and not isinstance(category_value, str):
        raise HTTPException(status_code=400, detail="category must be a string")

    payload = {
        "name": name,
        "path": path,
        "command": command,
        "port": port,
        "health_url": _clean_health_url(health_url_value),
        "description": (desc_value or "").strip(),
        "category": (category_value or "").strip(),
        "color": _clean_color(body.get("color")),
        "created_at": body.get("created_at"),
        "updated_at": body.get("updated_at"),
        "auto_restart": bool(body.get("auto_restart", False)),
        "autostart": bool(body.get("autostart", False)),
        "notify": bool(body.get("notify", True)),
        "env": _clean_env(body.get("env")),
    }
    try:
        cfg = registry.add(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    state = await _build_state(cfg, time.time())
    _states[cfg["id"]] = state
    _broadcast()
    return state


@app.patch("/api/apps/{app_id}")
async def update_app(app_id: str, request: Request) -> dict:
    _cfg_or_404(app_id)
    body = await _json_body(request)
    is_running_now = pm.is_running(app_id)

    patch: dict[str, Any] = {}
    if "name" in body:
        name = body.get("name")
        if not isinstance(name, str) or not name.strip():
            raise HTTPException(status_code=400, detail="name cannot be empty")
        patch["name"] = name.strip()
    if "path" in body:
        patch["path"] = _require_dir(_clean_path(body.get("path")))
    if "command" in body:
        command = body.get("command")
        if command is not None and not isinstance(command, str):
            raise HTTPException(status_code=400, detail="command must be a string")
        patch["command"] = (command or "").strip()
    if "port" in body:
        port = _coerce_optional_int(body.get("port"), "port")
        if port is not None and not (0 <= port <= 65535):
            raise HTTPException(status_code=400, detail="port out of range")
        patch["port"] = port
    if "health_url" in body:
        health_url = body.get("health_url")
        if health_url is not None and not isinstance(health_url, str):
            raise HTTPException(status_code=400, detail="health_url must be a string")
        patch["health_url"] = _clean_health_url(health_url)
    if "description" in body:
        desc = body.get("description")
        if desc is not None and not isinstance(desc, str):
            raise HTTPException(status_code=400, detail="description must be a string")
        patch["description"] = (desc or "").strip()
    if "category" in body:
        category = body.get("category")
        if category is not None and not isinstance(category, str):
            raise HTTPException(status_code=400, detail="category must be a string")
        patch["category"] = (category or "").strip()
    if "color" in body:
        patch["color"] = _clean_color(body.get("color"))
    if "created_at" in body:
        patch["created_at"] = body.get("created_at")
    if "updated_at" in body:
        patch["updated_at"] = body.get("updated_at")
    if "auto_restart" in body:
        patch["auto_restart"] = bool(body.get("auto_restart"))
    if "autostart" in body:
        patch["autostart"] = bool(body.get("autostart"))
    if "notify" in body:
        patch["notify"] = bool(body.get("notify"))
    if "env" in body:
        patch["env"] = _clean_env(body.get("env"))

    try:
        cfg = registry.update(app_id, patch)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown app id: {app_id}") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    state = await _build_state(cfg, time.time())
    if is_running_now:
        state["needs_restart"] = True
    _states[cfg["id"]] = state
    _broadcast()
    return state


@app.delete("/api/apps/{app_id}")
async def delete_app(app_id: str) -> dict:
    _cfg_or_404(app_id)
    with contextlib.suppress(Exception):
        await asyncio.to_thread(share_routes.tunnels.stop, app_id)
    with contextlib.suppress(Exception):
        await asyncio.to_thread(pm.stop, app_id)
    if not registry.remove(app_id):
        raise HTTPException(status_code=404, detail=f"unknown app id: {app_id}")

    _states.pop(app_id, None)
    _restart_times.pop(app_id, None)
    _restart_counts.pop(app_id, None)
    _errors.pop(app_id, None)
    _last_pids.pop(app_id, None)
    _restart_suppressed.discard(app_id)
    _notified_crashes.discard(app_id)
    _broadcast()
    return {"ok": True}


# ---------------------------------------------------------------------------
# routes — lifecycle
# ---------------------------------------------------------------------------
@app.post("/api/apps/{app_id}/start")
async def start_app(app_id: str, kill_conflict: int = Query(default=0)) -> dict:
    cfg = _cfg_or_404(app_id)
    if pm.is_running(app_id):
        raise HTTPException(status_code=409, detail=f"app {app_id!r} is already running")

    # Port conflict detection and optional kill
    check_port = cfg.get("port")
    if not check_port and cfg.get("path") and os.path.isdir(cfg["path"]):
        det = monitor.detect_command(cfg["path"])
        check_port = det.get("port")

    if check_port:
        owner = await asyncio.to_thread(monitor.find_port_owner, int(check_port))
        if owner and owner.get("pid") != pm.pid(app_id):
            if kill_conflict == 1:
                try:
                    osutil.kill_pid(owner["pid"])
                    await asyncio.sleep(0.3)
                    if await asyncio.to_thread(monitor.port_open, int(check_port), timeout=0.1):
                        osutil.kill_pid(owner["pid"], force=True)
                        await asyncio.sleep(0.2)
                except Exception:
                    pass
            else:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "port_in_use",
                        "pid": owner["pid"],
                        "command": owner["command"],
                        "cwd": owner["cwd"],
                    },
                )

    try:
        await asyncio.to_thread(pm.start, cfg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    _errors[app_id] = None
    _restart_suppressed.discard(app_id)

    state = await _build_state(cfg, time.time())
    _states[app_id] = state
    _broadcast()
    return state


@app.post("/api/apps/{app_id}/stop")
async def stop_app(app_id: str) -> dict:
    cfg = _cfg_or_404(app_id)
    stopped = False
    with contextlib.suppress(Exception):
        await asyncio.to_thread(share_routes.tunnels.stop, app_id)
    with contextlib.suppress(Exception):
        stopped = await asyncio.to_thread(pm.stop, app_id)
    if stopped:
        _restart_suppressed.discard(app_id)
    else:
        _restart_suppressed.add(app_id)
    _errors[app_id] = None

    state = await _build_state(cfg, time.time())
    _states[app_id] = state
    _broadcast()
    return state


@app.post("/api/apps/{app_id}/restart")
async def restart_app(app_id: str) -> dict:
    cfg = _cfg_or_404(app_id)
    if not (cfg.get("command") or "").strip():
        raise HTTPException(status_code=400, detail="command is required")
    try:
        await asyncio.to_thread(pm.restart, cfg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    _errors[app_id] = None
    _restart_suppressed.discard(app_id)
    _restart_counts[app_id] = _restart_counts.get(app_id, 0) + 1
    _prune_restarts(app_id, time.time()).append(time.time())

    state = await _build_state(cfg, time.time())
    _states[app_id] = state
    _broadcast()
    return state


@app.post("/api/apps/reorder")
async def reorder_apps(request: Request) -> list[dict]:
    body = await _json_body(request)
    ids = body.get("ids")
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise HTTPException(status_code=400, detail="ids must be a list of app ids")
    registry.reorder(ids)
    _broadcast()
    return _snapshot()


@app.post("/api/apps/start-all")
async def start_all_apps() -> list[dict]:
    """Start all registered apps that are currently stopped."""
    for cfg in registry.list():
        app_id = cfg["id"]
        if not pm.is_running(app_id) and (cfg.get("command") or "").strip():
            with contextlib.suppress(Exception):
                await asyncio.to_thread(pm.start, cfg)
                _restart_suppressed.discard(app_id)
    return await _refresh_all()


@app.post("/api/apps/stop-all")
async def stop_all_apps() -> list[dict]:
    """Stop all running registered apps."""
    for cfg in registry.list():
        app_id = cfg["id"]
        if pm.is_running(app_id):
            with contextlib.suppress(Exception):
                await asyncio.to_thread(pm.stop, app_id)
                _restart_suppressed.discard(app_id)
    return await _refresh_all()


@app.post("/api/apps/{app_id}/terminate")
async def terminate_app(app_id: str) -> dict:
    """Terminate an app and kill any process occupying its port, even if started externally."""
    cfg = _cfg_or_404(app_id)
    with contextlib.suppress(Exception):
        await asyncio.to_thread(pm.stop, app_id)
        _restart_suppressed.add(app_id)

    port = cfg.get("port")
    if port and int(port) != 7777:
        pids = await asyncio.to_thread(monitor.find_all_port_pids, int(port))
        protected = {os.getpid(), os.getppid()}
        killed: list[int] = []
        for pid in pids:
            if pid not in protected:
                killed.append(pid)
                with contextlib.suppress(OSError):
                    osutil.kill_pid(pid)
        if killed:
            await asyncio.sleep(0.2)
            for pid in killed:
                with contextlib.suppress(OSError):
                    osutil.kill_pid(pid, force=True)

    state = await _build_state(cfg, time.time())
    _states[app_id] = state
    _broadcast()
    return state


@app.post("/api/apps/terminate-all")
async def terminate_all_apps() -> list[dict]:
    """Forcefully terminate all registered apps, including any external processes
    holding their ports or matching their working directory."""
    # 1. Stop all apps managed by procman
    for cfg in registry.list():
        app_id = cfg["id"]
        _restart_suppressed.add(app_id)
        if pm.is_running(app_id):
            with contextlib.suppress(Exception):
                await asyncio.to_thread(pm.stop, app_id)

    # 2. Identify external processes on registered ports
    killed_pids: set[int] = set()
    protected = {os.getpid(), os.getppid()}

    for cfg in registry.list():
        port = cfg.get("port")
        if port and int(port) != 7777:
            try:
                # Fast check: only inspect if port is actually listening
                if await asyncio.to_thread(monitor.port_open, int(port)):
                    pids = await asyncio.to_thread(monitor.find_all_port_pids, int(port))
                    for pid in pids:
                        if pid not in protected and pid not in killed_pids:
                            killed_pids.add(pid)
                            with contextlib.suppress(OSError):
                                osutil.kill_pid(pid)
            except Exception:
                pass

    if killed_pids:
        await asyncio.sleep(0.3)
        for pid in killed_pids:
            with contextlib.suppress(OSError):
                osutil.kill_pid(pid, force=True)

    return await _refresh_all()


# ---------------------------------------------------------------------------
# routes — logs & utilities
# ---------------------------------------------------------------------------
@app.get("/api/apps/{app_id}/logs")
async def app_logs(
    app_id: str,
    tail: int = Query(default=TAIL_DEFAULT, ge=0, le=50_000),
) -> dict:
    _cfg_or_404(app_id)
    return {"lines": pm.logs(app_id, tail=tail)}


@app.delete("/api/apps/{app_id}/logs")
async def delete_app_logs(app_id: str) -> dict:
    _cfg_or_404(app_id)
    pm.clear_logs(app_id)
    return {"ok": True}


@app.get("/api/apps/{app_id}/icon")
async def app_icon(app_id: str) -> FileResponse:
    cfg = _cfg_or_404(app_id)
    found = icons.find_icon(cfg.get("path") or "")
    if not found:
        raise HTTPException(status_code=404, detail="no icon found for this app")
    ext = os.path.splitext(found)[1].lower()
    return FileResponse(
        found,
        media_type=icons.MEDIA_TYPES.get(ext, "application/octet-stream"),
        headers={"Cache-Control": "max-age=86400"},
    )


@app.get("/api/apps/{app_id}/logs/download")
async def download_app_logs(app_id: str) -> FileResponse:
    _cfg_or_404(app_id)
    path = pm.log_path(app_id)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            pass
    return FileResponse(
        path,
        media_type="text/plain; charset=utf-8",
        filename=f"{app_id}.log",
    )


@app.get("/api/detect")
async def detect(path: str | None = None, exclude_id: str | None = None) -> dict:
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="path is required")
    target = os.path.abspath(os.path.expanduser(path.strip()))
    detected = await asyncio.to_thread(
        monitor.detect_command, target,
        pick_free_port=True, avoid_ports=_registered_ports(exclude_id),
    )
    return {
        "command": detected.get("command"),
        "port": detected.get("port"),
        "type": detected.get("type"),
    }


# ---------------------------------------------------------------------------
# routes — discovery, diagnosis & fixes, git, workspaces
# ---------------------------------------------------------------------------
_SKIP_DISCOVER = {"node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build", "target"}


@app.post("/api/discover")
async def discover(request: Request) -> dict:
    """List the projects inside a folder (and the folder itself) with how to run each."""
    body = await _json_body(request)
    root = _require_dir(_clean_path(body.get("path")))
    registered = {os.path.normcase(os.path.abspath(a["path"])) for a in registry.list()}

    def scan() -> list:
        candidates = [root]
        try:
            for name in sorted(os.listdir(root), key=str.casefold):
                full = os.path.join(root, name)
                if not name.startswith(".") and name not in _SKIP_DISCOVER and os.path.isdir(full):
                    candidates.append(full)
        except OSError as exc:
            raise HTTPException(status_code=400, detail=f"can't read folder: {exc}") from exc
        found = []
        for path in candidates[:300]:
            # the chosen folder only counts if it is a project itself
            det = monitor.detect_command(path, subfolders=path != root)
            if not det.get("command"):
                continue
            base = os.path.basename(path.rstrip(os.sep)) or path
            pretty = " ".join(base.replace("-", " ").replace("_", " ").split())
            found.append({
                "name": pretty[:1].upper() + pretty[1:] if pretty else base,
                "path": path,
                "type": det.get("type"),
                "command": det.get("command"),
                "port": det.get("port"),
                "has_icon": bool(icons.find_icon(path)),
                "registered": os.path.normcase(os.path.abspath(path)) in registered,
            })
        return found

    return {"path": root, "projects": await asyncio.to_thread(scan)}


@app.get("/api/apps/{app_id}/diagnose")
async def diagnose_app(app_id: str) -> dict:
    cfg = _cfg_or_404(app_id)
    info = pm.info(app_id)
    lines = await asyncio.to_thread(pm.logs, app_id, 400)
    state = _states.get(app_id) or {}
    findings = diagnose.diagnose(cfg, lines, info.get("exit_code"), state.get("port_conflict"))
    return {"findings": findings, "ai_available": bool(ai_routes.find_cli()),
            "log_tail": [line for line in lines[-40:]]}


@app.post("/api/apps/{app_id}/fix")
async def fix_app(app_id: str, request: Request) -> dict:
    cfg = _cfg_or_404(app_id)
    body = await _json_body(request)
    action = str(body.get("action") or "")
    if action in ("free_port", "edit"):
        raise HTTPException(status_code=400, detail=f"{action} is done from the dashboard, not here")
    log = lambda line: pm._append_to_file(app_id, line)  # noqa: E731 - small adapter
    try:
        result = await asyncio.to_thread(diagnose.run_fix, cfg, action, log)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.post("/api/apps/{app_id}/pull")
async def pull_app(app_id: str) -> dict:
    """git pull --ff-only, then restart the app if it was running."""
    cfg = _cfg_or_404(app_id)
    try:
        result = await asyncio.to_thread(gitinfo.pull, cfg["path"])
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    pm._append_to_file(app_id, "[homeport] git pull --ff-only")
    for line in result["output"].splitlines()[-50:]:
        pm._append_to_file(app_id, line)
    restarted = False
    if result["ok"] and pm.is_running(app_id) and cfg.get("command"):
        await asyncio.to_thread(pm.restart, cfg)
        restarted = True
    result["restarted"] = restarted
    result["state"] = await _build_state(cfg, time.time())
    _states[app_id] = result["state"]
    _broadcast()
    return result


async def _wait_until_up(app_id: str, timeout: float = 45.0) -> str:
    """Wait for an app to be running (port open) — returns its final status."""
    deadline = time.time() + timeout
    status = "starting"
    while time.time() < deadline:
        cfg = registry.get(app_id)
        if cfg is None:
            return "stopped"
        state = await _build_state(cfg, time.time())
        _states[app_id] = state
        status = state["status"]
        if status in ("running", "crashed", "stopped"):
            return status
        await asyncio.sleep(0.5)
    return status


async def _start_group(ids: list) -> None:
    for app_id in ids:
        if pm.is_running(app_id):
            continue
        try:
            await start_app(app_id, kill_conflict=0)
        except HTTPException as exc:
            pm._append_to_file(app_id, f"[homeport] workspace start skipped: {exc.detail}")
            continue
        if await _wait_until_up(app_id) == "crashed":
            pm._append_to_file(app_id, "[homeport] workspace start stopped: this app crashed")
            break
    _broadcast()


def _group_ids(category: str) -> list:
    key = (category or "").strip()
    return [a["id"] for a in registry.list() if (a.get("category") or "").strip() == key and a.get("command")]


@app.post("/api/groups/start")
async def start_group(request: Request) -> dict:
    """Start every app in a category, in your order, each after the previous is up."""
    body = await _json_body(request)
    ids = _group_ids(str(body.get("category") or ""))
    if not ids:
        raise HTTPException(status_code=404, detail="no apps with a start command in this group")
    asyncio.create_task(_start_group(ids))
    return {"ok": True, "ids": ids}


@app.post("/api/groups/stop")
async def stop_group(request: Request) -> dict:
    body = await _json_body(request)
    ids = _group_ids(str(body.get("category") or ""))
    for app_id in reversed(ids):
        if pm.is_running(app_id):
            with contextlib.suppress(Exception):
                await asyncio.to_thread(share_routes.tunnels.stop, app_id)
                await asyncio.to_thread(pm.stop, app_id)
                _restart_suppressed.add(app_id)
    return {"ok": True, "ids": ids, "apps": await _refresh_all()}


# ---------------------------------------------------------------------------
# routes — databases & services
# ---------------------------------------------------------------------------
_SERVICE_ICONS = {
    # simple monochrome glyphs (not brand logos)
    "database": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#111214" '
                'stroke-width="1.8"><ellipse cx="12" cy="5.5" rx="7.5" ry="3"/><path d="M4.5 5.5v13c0 1.7 3.4 3 7.5 3s7.5-1.3 '
                '7.5-3v-13M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3"/></svg>',
    "bolt": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#111214" stroke-width="1.8" '
            'stroke-linejoin="round"><path d="M13 2.5 4.5 13.5H12l-1 8 8.5-11H12z"/></svg>',
    "leaf": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#111214" stroke-width="1.8" '
            'stroke-linecap="round"><path d="M12 21.5V12M12 2.5c4 3 5.5 6.5 5.5 9.5S15 18 12 19c-3-1-5.5-4-5.5-7S8 5.5 12 2.5z"/></svg>',
    "mail": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#111214" stroke-width="1.8" '
            'stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m3.5 6.5 8.5 6.5 8.5-6.5"/></svg>',
}
_ICON_FOR = {"postgres": "database", "mysql": "database", "redis": "bolt", "mongodb": "leaf", "mailpit": "mail"}


@app.get("/api/services")
async def list_services() -> dict:
    return {"services": await asyncio.to_thread(services.catalog)}


@app.post("/api/services")
async def add_service(request: Request) -> dict:
    """Add a database/dev service as an app (and start it unless start=false)."""
    body = await _json_body(request)
    kind = str(body.get("kind") or "")
    if kind not in services.CATALOG:
        raise HTTPException(status_code=400, detail=f"unknown service: {kind!r}")
    return await _create_service(kind, body.get("mode") or None, bool(body.get("start", True)))


async def _create_service(kind: str, mode: str | None = None, start: bool = True) -> dict:
    meta = services.CATALOG[kind]

    taken_names = {a["name"].casefold() for a in registry.list()}
    name, n = meta["name"], 2
    while name.casefold() in taken_names:
        name, n = f"{meta['name']} {n}", n + 1

    avoid = _registered_ports()
    port = await asyncio.to_thread(free_port, meta["port"], avoid)
    smtp = None
    if meta.get("smtp_port"):
        smtp = await asyncio.to_thread(free_port, meta["smtp_port"], avoid | {port})

    os.makedirs(services.SERVICES_DIR, exist_ok=True)
    cfg = registry.add({"name": name, "path": services.SERVICES_DIR, "command": "",
                        "category": "Services", "description": meta["description"]})
    try:
        plan = await asyncio.to_thread(services.plan, kind, cfg["id"], port, smtp_port=smtp, mode=mode)
    except (LookupError, ValueError) as exc:
        registry.remove(cfg["id"])
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    os.makedirs(os.path.join(plan["path"], "data"), exist_ok=True)
    with contextlib.suppress(OSError):
        with open(os.path.join(plan["path"], "icon.svg"), "w", encoding="utf-8") as fh:
            fh.write(_SERVICE_ICONS[_ICON_FOR[kind]])
    desc = meta["description"] + (" · via Docker" if plan["service"]["mode"] == "docker" else "")
    cfg = registry.update(cfg["id"], {"path": plan["path"], "command": plan["command"], "port": plan["port"],
                                      "service": plan["service"], "description": desc})
    if start:
        with contextlib.suppress(HTTPException):
            return await start_app(cfg["id"], kill_conflict=0)
    state = await _build_state(cfg, time.time())
    _states[cfg["id"]] = state
    return state


# ---------------------------------------------------------------------------
# routes — WordPress mode
# ---------------------------------------------------------------------------
_wp_cache: dict = {}


def _wp_db_service(cfg: dict) -> dict | None:
    """The MySQL/MariaDB service app this WordPress site uses (if any)."""
    link = cfg.get("wordpress") or {}
    svc = registry.get(link.get("service_id") or "") if link.get("service_id") else None
    if svc and (svc.get("service") or {}).get("kind") == "mysql":
        return svc
    return None


def _wp_state(cfg: dict) -> dict | None:
    """Cheap WordPress summary for the card (cached by wp-config mtime)."""
    path = cfg.get("path") or ""
    try:
        stamp = os.path.getmtime(os.path.join(path, "wp-config.php"))
    except OSError:
        stamp = 0.0
    svc = _wp_db_service(cfg)
    expected = f"127.0.0.1:{svc['port']}" if svc else None
    key = (path, stamp, expected, os.path.isfile(os.path.join(path, wordpress.HELPER_REL)))
    hit = _wp_cache.get(cfg["id"])
    if hit and hit[0] == key:
        return hit[1]
    st = wordpress.status(path, expected) if path else None
    if st is not None:
        st["service_id"] = svc["id"] if svc else None
        st["needs_setup"] = st["needs_setup"] or svc is None
    _wp_cache[cfg["id"]] = (key, st)
    return st


@app.get("/api/apps/{app_id}/wordpress")
async def wordpress_status(app_id: str) -> dict:
    cfg = _cfg_or_404(app_id)
    st = _wp_state(cfg)
    if st is None:
        raise HTTPException(status_code=404, detail="this app isn't a WordPress site")
    avail = await asyncio.to_thread(services.availability, "mysql")
    mysqli = await asyncio.to_thread(wordpress.php_has_mysqli)
    return {**st, "mysql_available": avail["native"] or avail["docker"], "php_mysqli": mysqli,
            "mysql_install": services.catalog()[1]["install"]}


@app.post("/api/apps/{app_id}/wordpress/setup")
async def wordpress_setup(app_id: str) -> dict:
    """Database service + database + wp-config.php + live-URL helper."""
    cfg = _cfg_or_404(app_id)
    if not wordpress.is_wordpress(cfg.get("path") or ""):
        raise HTTPException(status_code=400, detail="this folder isn't a WordPress site")

    svc = _wp_db_service(cfg) or next(
        (a for a in registry.list() if (a.get("service") or {}).get("kind") == "mysql"), None)
    if svc is None:
        try:
            svc = registry.get((await _create_service("mysql"))["id"])
        except HTTPException as exc:
            raise HTTPException(status_code=409, detail=f"needs MySQL or MariaDB: {exc.detail}") from exc
    if not pm.is_running(svc["id"]):
        with contextlib.suppress(HTTPException):
            await start_app(svc["id"], kill_conflict=0)
    if await _wait_until_up(svc["id"], timeout=90) != "running":
        raise HTTPException(status_code=409, detail=f"the database service “{svc['name']}” didn't start — see its logs")

    db_name = ("wp_" + re.sub(r"[^a-z0-9]+", "_", app_id.lower())).strip("_")[:64]
    port = int(svc["port"])
    try:
        await asyncio.to_thread(wordpress.create_database, port, db_name)
        await asyncio.to_thread(wordpress.write_config, cfg["path"], db_name, "root", "", f"127.0.0.1:{port}")
        await asyncio.to_thread(wordpress.install_helper, cfg["path"])
    except (RuntimeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    cfg = registry.update(app_id, {"wordpress": {"service_id": svc["id"], "db": db_name}})
    pm._append_to_file(app_id, f"[homeport] WordPress set up: database {db_name} on {svc['name']} (127.0.0.1:{port})")
    if pm.is_running(app_id):
        await asyncio.to_thread(pm.restart, cfg)
    _wp_cache.pop(app_id, None)
    state = await _build_state(cfg, time.time())
    _states[app_id] = state
    _broadcast()
    return state


@app.post("/api/apps/{app_id}/wordpress/import")
async def wordpress_import(app_id: str, request: Request) -> dict:
    """Upload a .sql / .sql.gz backup (raw request body) into the site's database."""
    cfg = _cfg_or_404(app_id)
    link = cfg.get("wordpress") or {}
    svc = _wp_db_service(cfg)
    if not link.get("db") or svc is None:
        raise HTTPException(status_code=409, detail="set up WordPress first (it creates the database)")
    if not pm.is_running(svc["id"]):
        with contextlib.suppress(HTTPException):
            await start_app(svc["id"], kill_conflict=0)
        await _wait_until_up(svc["id"], timeout=90)

    tmp_dir = os.path.join(paths.DATA_DIR, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="import-", suffix=".sql", dir=tmp_dir)
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 2 * 1024 ** 3:
                    raise HTTPException(status_code=413, detail="backup is larger than 2 GB")
                out.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="the uploaded file is empty")
        container = None
        if (svc.get("service") or {}).get("mode") == "docker":
            container = f"homeport-{svc['id']}"
        try:
            how = await asyncio.to_thread(wordpress.import_sql, tmp_path, int(svc["port"]), link["db"],
                                          docker_container=container)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        with contextlib.suppress(OSError):
            os.remove(tmp_path)
    pm._append_to_file(app_id, f"[homeport] imported database backup ({size // 1024} KB, {how})")
    return {"ok": True, "size": size, "how": how}


# Set by launch.py / the desktop app: stops the server (and every app it runs).
request_quit = None


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "platform": osutil.platform_name(), "can_quit": request_quit is not None,
            "desktop": paths.FROZEN}


@app.post("/api/quit")
async def quit_homeport(request: Request) -> dict:
    """Quit Homeport (stops all apps). Only from this computer's own pages."""
    origin = request.headers.get("origin") or ""
    if origin and not re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", origin):
        raise HTTPException(status_code=403, detail="not allowed from this page")
    if request_quit is None:
        raise HTTPException(status_code=501, detail="quit isn't available in this mode — press Ctrl+C in Homeport's window")
    asyncio.get_running_loop().call_later(0.3, request_quit)
    return {"ok": True}


@app.get("/api/events")
async def events(request: Request) -> StreamingResponse:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=16)
    _subscribers.add(queue)

    async def event_stream():
        try:
            if not _states:
                with contextlib.suppress(Exception):
                    await _refresh_all()
            yield f"data: {_snapshot_json()}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                except (asyncio.TimeoutError, TimeoutError):
                    payload = _snapshot_json()
                yield f"data: {payload}\n\n"
        finally:
            _subscribers.discard(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/favicon.ico")
async def favicon() -> FileResponse:
    svg = os.path.join(UI_DIR, "favicon.svg")
    if os.path.exists(svg):
        return FileResponse(svg, media_type="image/svg+xml")
    raise HTTPException(status_code=404)


# ---------------------------------------------------------------------------
# static UI (mounted last so /api/* always wins)
# ---------------------------------------------------------------------------
if os.path.isdir(UI_DIR):
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
